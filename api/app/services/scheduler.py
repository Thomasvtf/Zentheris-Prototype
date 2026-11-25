"""Tarea programada de generación horaria (RN-IV-05, DC-34).

Mientras la API está activa, una tarea de APScheduler genera cada hora (minuto 0, hora de
Bogotá) las lecturas nuevas de todos los hogares; también corre al arrancar, para recuperar las
horas en que Render tuvo el servidor suspendido. Cada hogar va en su propia sesión y transacción
(`hour_recovery.fill_missing_hours`): el fallo de uno no detiene a los demás.

Varias copias: con varios workers de uvicorn o varias instancias de la API, cada una arranca su
propio planificador y la tarea corre en todas. Es seguro: el candado por hogar de
`fill_missing_hours` (pg_advisory_xact_lock) serializa las recuperaciones del mismo hogar y
ON CONFLICT DO NOTHING descarta cualquier repetido; solo se gasta trabajo de más. Por eso en
Render la API debe arrancarse con un solo worker.

Alertas, consejos y cierre de mes (fase 8, DC-35, DC-32): los evalúa la propia recuperación de
cada hogar sobre las horas que acaba de generar (`hour_recovery`, dentro de un SAVEPOINT); así la
tarea horaria también dispara el cierre de mes cuando genera la hora 23:00 del último día.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import NamedTuple
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.config import Settings
from app.data import households as households_data
from app.data.database import get_engine
from app.domain.simulator import TIMEZONE
from app.services import hour_recovery
from app.services.hour_recovery import HourRecoveryError

logger = logging.getLogger(__name__)

HOURLY_JOB_ID = "generacion_horaria"
# Si la tarea se atrasa (servidor ocupado), aún corre dentro de este margen; si no, la siguiente
# recupera todo igual (coalesce: varias ejecuciones atrasadas cuentan como una).
MISFIRE_GRACE_SECONDS = 15 * 60


class GenerationSummary(NamedTuple):
    """Resultado de una corrida de la generación horaria."""

    households: int  # hogares revisados
    readings: int  # lecturas nuevas guardadas
    failures: int  # hogares cuya recuperación falló (o 1 si falló el listado)


def run_hourly_generation(
    now: datetime | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> GenerationSummary:
    """Genera las horas nuevas de todos los hogares con sensores activos (RN-IV-05).

    Una sesión para listar los hogares y una sesión (con su transacción) por hogar. El fallo de
    un hogar se cuenta, se registra sin ids y se sigue con los demás. Si un hogar se borró entre
    el listado y su recuperación: o no tiene perfil (cuenta 0, sin fallo) o la inserción da un
    23503 de llave foránea, que `fill_missing_hours` registra como WARNING y aquí cuenta como
    fallo (lo más simple: no se distingue de los demás). Si falla el listado se
    registra y se devuelve `GenerationSummary(0, 0, 1)`: ningún hogar revisado y un fallo.
    Nunca lanza. Un solo `now` para toda la corrida.
    """
    moment = datetime.now(UTC) if now is None else now
    make_session = session_factory or _default_session

    try:
        household_ids = _list_households(make_session)
    except Exception as exc:  # noqa: BLE001 - la tarea programada nunca lanza
        logger.error("Generación horaria: no se pudo listar los hogares: tipo=%s", _kind(exc))
        return GenerationSummary(0, 0, 1)

    readings = 0
    failures = 0
    for hogar_id in household_ids:
        try:
            session = make_session()
            try:
                readings += hour_recovery.fill_missing_hours(session, hogar_id, moment)
            finally:
                session.close()
        except HourRecoveryError:
            failures += 1  # fill_missing_hours ya revirtió y lo registró
        except Exception as exc:  # noqa: BLE001 - un hogar no detiene a los demás
            failures += 1
            logger.error("Generación horaria: un hogar falló: tipo=%s", _kind(exc))

    summary = GenerationSummary(len(household_ids), readings, failures)
    logger.info(
        "Generación horaria: hogares=%d lecturas=%d fallos=%d",
        summary.households,
        summary.readings,
        summary.failures,
    )
    return summary


def create_scheduler() -> BackgroundScheduler:
    """Planificador con la tarea `HOURLY_JOB_ID` (minuto 0, hora de Bogotá). No lo arranca.

    `next_run_time` es ahora: así también corre al arrancar (RN-IV-05). Una sola instancia a la
    vez y las ejecuciones atrasadas se juntan en una.
    """
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        run_hourly_generation,
        trigger=CronTrigger(minute=0, timezone=TIMEZONE),
        id=HOURLY_JOB_ID,
        name=HOURLY_JOB_ID,
        next_run_time=datetime.now(TIMEZONE),
        coalesce=True,
        max_instances=1,
        misfire_grace_time=MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    return scheduler


def start_scheduler(settings: Settings) -> BackgroundScheduler | None:
    """Arranca la tarea programada si hay base de datos; si no, WARNING y None."""
    if settings.database_url is None:
        logger.warning("Sin DATABASE_URL: la generación horaria no se programa.")
        return None
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Generación horaria programada (minuto 0, %s).", TIMEZONE.key)
    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler | None) -> None:
    """Detiene el planificador sin bloquear el apagado de la API.

    `wait=False` no espera aquí, pero la corrida en curso sigue en su hilo: Python espera a que
    termine al salir del proceso. Si Render corta el proceso antes, la transacción del hogar en
    curso queda sin commit y Postgres la revierte (y suelta su candado); la siguiente corrida
    recupera esas horas.
    """
    if scheduler is None:
        return
    scheduler.shutdown(wait=False)


# --- auxiliares ---------------------------------------------------------------------------


def _default_session() -> Session:
    return Session(get_engine())


def _list_households(make_session: Callable[[], Session]) -> list[UUID]:
    session = make_session()
    try:
        return households_data.list_household_ids_with_active_sensors(session)
    finally:
        session.close()


def _kind(exc: Exception) -> str:
    """Tipo y SQLSTATE, sin el mensaje (puede llevar ids o valores)."""
    sqlstate = getattr(getattr(exc, "orig", None), "pgcode", None) or "-"
    return f"{type(exc).__name__} sqlstate={sqlstate}"
