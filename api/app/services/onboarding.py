"""Casos de uso de la etiqueta «Onboarding».

Maneja la transacción y llama a domain/ y data/ (api/CLAUDE.md). La sesión llega del router. El
hogar y su backfill se guardan en una sola transacción: o queda todo o no queda nada (RN-X-03).
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from sqlmodel import Session

from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import readings as readings_data
from app.data import simulation_profiles as profiles_data
from app.data.households import HouseholdRow, SensorToInsert, ZoneToInsert
from app.data.memberships import ActiveMembershipExistsError
from app.data.simulation_profiles import SimulationProfileRow
from app.domain.formats import main_source_name, zone_name
from app.domain.simulator import HOURS_BACKFILL, generate_backfill, validate_or_raise
from app.domain.zone_rules import (
    FALLBACK_PERSONALITY,
    ZoneRuleError,
    assign_personality,
    resolve_active_personality,
)
from app.errors import ApiError, CodigoError
from app.schemas.common import Rol
from app.schemas.households import Hogar, Permisos
from app.schemas.onboarding import OnboardingCrear

logger = logging.getLogger(__name__)

# Mensajes técnicos y cortos: la app decide el texto por `codigo`.
MEMBRESIA_ACTIVA_MESSAGE = "El usuario ya pertenece a un hogar activo."
FICHA_NO_CREADA_MESSAGE = "El usuario aún no tiene ficha."
BACKFILL_FAILED_MESSAGE = "No se pudo crear el hogar."


def create_household_onboarding(
    session: Session, user_id: UUID, payload: OnboardingCrear, now: datetime | None = None
) -> Hogar:
    """`crearHogarOnboarding`: crea el hogar con su backfill en una sola transacción.

    RN-X-02, RN-X-03, RN-X-04, RN-IV-01, RN-IV-07, RN-II-01, RN-II-03; DC-33, DC-37, DC-38.
    422 con el código de la regla de zonas, sin tocar la base. 409 `MEMBRESIA_ACTIVA_EXISTENTE`
    si el usuario ya tiene un hogar, también si otra petición suya se adelantó. Cualquier otro
    fallo, incluido el del commit, revierte lo pendiente y responde 500 `BACKFILL_FALLIDO`; la
    causa solo queda en el log (si la conexión cae durante el commit, la base pudo confirmarlo).
    `now` debe llevar zona horaria. No genera alertas ni consejos (DC-35).
    """
    # La lista original, no un conjunto: así se detectan las zonas repetidas.
    zones = [zona.value for zona in payload.zonas]
    try:
        personality = assign_personality(payload.tipo_vivienda.value, zones)
    except ZoneRuleError as exc:
        raise ApiError(422, CodigoError(exc.code), str(exc)) from None

    # Dentro de los `except` solo se anota el fallo. La reversión y la respuesta van fuera: si
    # `rollback` falla con una excepción en curso, SQLAlchemy registra su traza con la excepción
    # original encadenada, y el DETAIL de Postgres lleva ids y el nombre del hogar.
    conflict = False
    missing_profile = False
    try:
        return _create_household(
            session, user_id, payload, zones, personality, now or datetime.now(UTC)
        )
    except ApiError:
        raise
    except ActiveMembershipExistsError:
        conflict = True
    except Exception as exc:  # noqa: BLE001 - RN-X-03: cualquier fallo revierte todo
        missing_profile = _is_missing_profile(exc)
        _log_failure("Onboarding fallido", exc)
    _rollback(session)
    if conflict:
        raise _active_membership_exists() from None
    if missing_profile:
        # La persona aún no creó su ficha: la app la lleva a crearla (contrato 0.2.8).
        raise ApiError(404, CodigoError.FICHA_NO_CREADA, FICHA_NO_CREADA_MESSAGE) from None
    raise ApiError(500, CodigoError.BACKFILL_FALLIDO, BACKFILL_FAILED_MESSAGE) from None


# --- auxiliares ---------------------------------------------------------------------------


def _create_household(
    session: Session,
    user_id: UUID,
    payload: OnboardingCrear,
    zones: Sequence[str],
    personality: str,
    now: datetime,
) -> Hogar:
    """Los pasos de RN-X-03 hasta el commit; si algo lanza, revierte quien llama."""
    started = perf_counter()
    if memberships_data.get_active_membership_of_user(session, user_id) is not None:
        raise _active_membership_exists()
    profile = _active_profile(session, personality)
    params = validate_or_raise(profile.params)

    hogar_id = uuid4()
    household = households_data.insert_household(
        session,
        hogar_id=hogar_id,
        nombre=payload.nombre_hogar,
        tipo_vivienda=payload.tipo_vivienda.value,
        perfil_simulacion_id=profile.id,
    )
    memberships_data.insert_admin_membership(
        session, hogar_id=hogar_id, usuario_id=user_id, joined_at=now
    )
    sensors_by_zone = _insert_zones_and_sensors(session, hogar_id, payload.nombre_hogar, zones)

    generation_started = perf_counter()
    readings = generate_backfill(hogar_id, params, sensors_by_zone, now)
    generated = perf_counter()
    inserted = readings_data.insert_readings_batch(session, readings)
    saved = perf_counter()
    if inserted != HOURS_BACKFILL * len(zones):
        raise RuntimeError("el número de lecturas guardadas no es el esperado")

    # La respuesta se arma antes del commit: después de confirmar ya nada puede fallar.
    hogar = _to_hogar(household)
    session.commit()
    logger.info(
        "Onboarding creado: zonas=%d lecturas=%d generar_ms=%.1f insertar_ms=%.1f total_ms=%.1f",
        len(zones),
        inserted,
        (generated - generation_started) * 1000,
        (saved - generated) * 1000,
        (perf_counter() - started) * 1000,
    )
    return hogar


def _active_profile(session: Session, personality: str) -> SimulationProfileRow:
    """Perfil de la personalidad asignada o el de respaldo (RN-X-04, DC-37)."""
    profiles = profiles_data.get_profiles(session, [personality, FALLBACK_PERSONALITY])
    active = {name: profile.activo for name, profile in profiles.items()}
    return profiles[resolve_active_personality(personality, active)]


def _insert_zones_and_sensors(
    session: Session, hogar_id: UUID, nombre_hogar: str, zones: Sequence[str]
) -> dict[str, UUID]:
    """Zonas, la única fuente principal y un sensor por zona (RN-X-03, DC-38): tipo → sensor."""
    new_zones = [ZoneToInsert(id=uuid4(), tipo=zone, nombre=zone_name(zone)) for zone in zones]
    if households_data.insert_zones(session, hogar_id, new_zones) != len(new_zones):
        raise RuntimeError("el número de zonas guardadas no es el esperado")

    fuente_id = uuid4()
    households_data.insert_main_source(
        session, fuente_id=fuente_id, hogar_id=hogar_id, nombre=main_source_name(nombre_hogar)
    )

    sensors = [SensorToInsert(id=uuid4(), zona_id=zone.id) for zone in new_zones]
    inserted = households_data.insert_zone_sensors(
        session, hogar_id=hogar_id, fuente_id=fuente_id, sensors=sensors
    )
    if inserted != len(sensors):
        raise RuntimeError("el número de sensores guardados no es el esperado")
    return {zone.tipo: sensor.id for zone, sensor in zip(new_zones, sensors, strict=True)}


def _to_hogar(row: HouseholdRow) -> Hogar:
    """Respuesta del contrato, sin la personalidad (RN-X-04). Permisos de la fila (RN-II-03)."""
    return Hogar(
        id=row.id,
        nombre=row.nombre,
        tipo_vivienda=row.tipo_vivienda,
        rol_usuario=Rol.ADMINISTRADOR,
        permisos=Permisos(
            ver_consumo_actual=row.permiso_ver_consumo_actual,
            ver_historial=row.permiso_ver_historial,
            recibir_alertas=row.permiso_recibir_alertas,
            modificar_metas=row.permiso_modificar_metas,
        ),
    )


def _active_membership_exists() -> ApiError:
    return ApiError(409, CodigoError.MEMBRESIA_ACTIVA_EXISTENTE, MEMBRESIA_ACTIVA_MESSAGE)


def _is_missing_profile(exc: Exception) -> bool:
    """True si es el 23503 de `hogar_miembros.usuario_id`: el usuario no tiene fila en `usuarios`."""
    orig = getattr(exc, "orig", None)
    if getattr(orig, "pgcode", None) != "23503":
        return False
    constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
    return constraint == "hogar_miembros_usuario_id_fkey"


def _rollback(session: Session) -> None:
    """Revierte lo pendiente. Si la reversión falla (conexión perdida) solo queda en el log.

    No cambia la respuesta. Si lo que falló fue el commit, la base pudo haberlo confirmado antes
    de perder la conexión: en ese caso el hogar sí existe y un reintento recibe 409.
    """
    try:
        session.rollback()
    except Exception as exc:  # noqa: BLE001 - el fallo solo va al log
        _log_failure("Reversión del onboarding fallida", exc)


def _log_failure(event: str, exc: Exception) -> None:
    """Solo el tipo, el SQLSTATE y la línea de origen.

    Sin el mensaje ni la traza: los errores de Postgres llevan en su DETAIL ids y nombres.
    """
    sqlstate = getattr(getattr(exc, "orig", None), "pgcode", None) or "-"
    logger.error(
        "%s: tipo=%s sqlstate=%s origen=%s", event, type(exc).__name__, sqlstate, _origin(exc)
    )


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
