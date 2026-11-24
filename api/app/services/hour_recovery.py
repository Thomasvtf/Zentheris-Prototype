"""Recuperación de horas faltantes (RN-IV-05, DC-34).

Render suspende el servidor cuando no hay tráfico (DC-34): al volver, faltan las horas en que
estuvo apagado. Este caso de uso las genera con el simulador, idénticas a las de una generación
continua, y las guarda en una transacción propia. Lo llaman la tarea programada (al arrancar y
cada hora, `fill_missing_hours`) y, en las fases 6-10, las consultas de consumo, historial,
fuentes y alertas al INICIO de su caso de uso, después de la seguridad y antes de cualquier
escritura o bloqueo propio (`fill_missing_hours_or_continue`: si falla, la consulta sigue con los
datos guardados). Hace commit o rollback sobre la sesión que recibe.

Solo se generan lecturas de los sensores de las zonas del hogar (RN-IV-07). Además, solo de los
sensores con estado 'activo' en zonas con estado 'activa' (filtro de `get_sensor_gaps`): decidido
por Nicolás (23/11/2026), los sensores pausados y las zonas inactivas no reciben lecturas nuevas.
No genera alertas ni consejos (DC-35, fase 8).

Concurrencia: cada recuperación toma primero el candado del hogar (`lock_household_recovery`,
pg_advisory_xact_lock), así que dos recuperaciones simultáneas del mismo hogar (tarea de arranque
y una consulta, o varios workers) se serializan: la segunda ve los huecos ya llenos y no genera
nada. El candado se suelta con el commit o el rollback; por eso todos los caminos terminan la
transacción, también los que devuelven 0.
"""

import logging
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from sqlmodel import Session

from app.data import readings as readings_data
from app.data import simulation_profiles as profiles_data
from app.domain.simulator import (
    SensorGaps,
    generate_readings_for_gaps,
    recovery_end_hour,
    validate_or_raise,
)

logger = logging.getLogger(__name__)

HOUR_RECOVERY_FAILED_MESSAGE = "No se pudieron completar las horas faltantes."
RECOVERY_SKIPPED_MESSAGE = "Consulta con los datos guardados: recuperación de horas fallida"
# SQLSTATE de llave foránea: el hogar (o su sensor) se borró entre el listado y la inserción.
FOREIGN_KEY_VIOLATION = "23503"


class HourRecoveryError(Exception):
    """La recuperación falló y se revirtió. Mensaje fijo, sin datos."""

    def __init__(self, message: str = HOUR_RECOVERY_FAILED_MESSAGE) -> None:
        super().__init__(message)


def fill_missing_hours(session: Session, hogar_id: UUID, now: datetime | None = None) -> int:
    """Genera y guarda las horas que faltan del hogar hasta la última hora completa.

    RN-IV-05, DC-34. Devuelve cuántas lecturas nuevas guardó (las que ya existían no cuentan).
    Llámese al INICIO del caso de uso, antes de cualquier escritura o bloqueo propio: termina la
    transacción de `session` (commit si guardó algo; rollback si no, para soltar el candado).
    Hogar inexistente o sin horas faltantes: 0, sin insertar. Cualquier fallo revierte lo
    pendiente y lanza `HourRecoveryError`; la causa solo queda en el log, sin mensaje ni ids (un
    23503, hogar borrado a mitad de camino, va como WARNING; lo demás como ERROR).
    `now` debe llevar zona horaria: si no, `ValueError` antes de tocar la base.

    Las consultas (fases 6-10) no la llaman directamente sino con
    `fill_missing_hours_or_continue`: decidido (Nicolás, 23/11/2026) que si la recuperación falla
    la consulta responde 200 con los datos ya guardados, no 500. La tarea programada sí la llama
    directamente.
    """
    moment = datetime.now(UTC) if now is None else now
    if moment.utcoffset() is None:
        raise ValueError("`now` debe llevar zona horaria.")

    # Como en onboarding: dentro del `except` solo se anota; la reversión va fuera para que una
    # reversión fallida no registre la traza con la excepción original (y su DETAIL) encadenada.
    try:
        return _fill(session, hogar_id, moment)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo revierte y se informa sin datos
        level = logging.WARNING if _sqlstate(exc) == FOREIGN_KEY_VIOLATION else logging.ERROR
        _log_failure("Recuperación de horas fallida", exc, level)
    _rollback(session)
    raise HourRecoveryError() from None


def fill_missing_hours_or_continue(session: Session, hogar_id: UUID, now: datetime) -> int | None:
    """Recuperación para las consultas: si falla, la consulta sigue con los datos ya guardados.

    RN-IV-05, DC-34; decisión de Nicolás (23/11/2026). Llama a `fill_missing_hours` y devuelve
    cuántas lecturas guardó. Si lanza `HourRecoveryError` (ya revertida y registrada sin datos),
    escribe un WARNING sin ids ni mensajes de la base y devuelve None: la hora que falte saldrá
    como `sin_datos`. Nunca lanza `HourRecoveryError`. Un `now` sin zona horaria sigue dando
    `ValueError` (error de programación, no de la base).
    """
    try:
        return fill_missing_hours(session, hogar_id, now)
    except HourRecoveryError:
        logger.warning(RECOVERY_SKIPPED_MESSAGE)
        return None


# --- auxiliares ---------------------------------------------------------------------------


def _fill(session: Session, hogar_id: UUID, now: datetime) -> int:
    """Los pasos hasta terminar la transacción; si algo lanza, revierte quien llama."""
    started = perf_counter()
    # Primero de todo: serializa las recuperaciones del mismo hogar hasta el commit o rollback.
    readings_data.lock_household_recovery(session, hogar_id)
    profile = profiles_data.get_household_profile(session, hogar_id)
    if profile is None:
        session.rollback()  # suelta el candado
        return 0
    params = validate_or_raise(profile.params)

    gaps = readings_data.get_sensor_gaps(session, hogar_id, recovery_end_hour(now))
    gaps_by_zone = {
        gap.zona_tipo: SensorGaps(gap.sensor_id, gap.first_hour, gap.missing_hours) for gap in gaps
    }
    readings = generate_readings_for_gaps(hogar_id, params, gaps_by_zone, now)
    if not readings:
        session.rollback()  # suelta el candado
        return 0

    inserted = readings_data.insert_readings_batch(session, readings)
    if inserted != len(readings):
        # Con el candado nadie más recupera este hogar: alguien escribió lecturas sin tomarlo.
        logger.warning(
            "Recuperación de horas: guardadas=%d generadas=%d (escritura fuera del candado)",
            inserted,
            len(readings),
        )
    # TODO(DC-35): gracias al candado, `readings` son exactamente las horas nuevas que guarda
    # esta transacción (generadas en vivo, nunca el backfill). La fase 8 evaluará las alertas y
    # los consejos solo sobre ellas, aquí, antes del commit.
    session.commit()
    if inserted:
        logger.info(
            "Horas recuperadas: lecturas=%d total_ms=%.1f",
            inserted,
            (perf_counter() - started) * 1000,
        )
    return inserted


def _rollback(session: Session) -> None:
    """Revierte lo pendiente. Si la reversión falla (conexión perdida) solo queda en el log."""
    try:
        session.rollback()
    except Exception as exc:  # noqa: BLE001 - el fallo solo va al log
        _log_failure("Reversión de la recuperación de horas fallida", exc)


def _log_failure(event: str, exc: Exception, level: int = logging.ERROR) -> None:
    """Solo el tipo, el SQLSTATE y la línea de origen.

    Sin el mensaje ni la traza: los errores de Postgres llevan en su DETAIL ids y valores.
    """
    logger.log(
        level,
        "%s: tipo=%s sqlstate=%s origen=%s",
        event,
        type(exc).__name__,
        _sqlstate(exc) or "-",
        _origin(exc),
    )


def _sqlstate(exc: Exception) -> str | None:
    return getattr(getattr(exc, "orig", None), "pgcode", None)


def _origin(exc: Exception) -> str:
    """`módulo:línea` de la última llamada dentro de `app` que aparece en la traza."""
    origin = "-"
    traceback = exc.__traceback__
    while traceback is not None:
        module = traceback.tb_frame.f_globals.get("__name__", "")
        if module.startswith("app."):
            origin = f"{module}:{traceback.tb_lineno}"
        traceback = traceback.tb_next
    return origin
