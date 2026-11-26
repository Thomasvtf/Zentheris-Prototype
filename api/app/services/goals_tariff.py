"""Casos de uso de la etiqueta «Metas y tarifa» (fase 10).

Reglas: RN-V-01, RN-V-02, RN-V-03, RN-XVI-04, RN-XVI-05, RN-XVII-04, DC-39, DC-41; consultas con
recuperación previa RN-IV-05 y DC-34. Decisiones D3, D4, D6 y D7 de la hoja de la fase 10.

- **Consultas** (`get_goal`, `get_tariff`): sin commit propio. `get_goal` recupera primero las
  horas faltantes con `hour_recovery.fill_missing_hours_or_continue` (si falla, responde con lo
  guardado y un WARNING sin datos), igual que Consejos.
- **Escrituras** (`create_goal`, `create_tariff`): bloquean el hogar (`lock_household`, primer
  nivel del orden de bloqueo del proyecto: hogar → membresía), vuelven a comprobar BAJO BLOQUEO
  la membresía activa y el rol o el permiso (`_lock_and_recheck`, como `_lock_admin` de
  `members_invitations`: por si hubo una salida, una transferencia o un cambio de permisos entre
  la dependencia de `app.security` y el caso de uso), escriben y hacen `session.commit()` al
  final; si algo lanza antes, la sesión de la petición se cierra sin commit (rollback). Sin
  recuperación de horas: guardar una meta o una tarifa no depende de los datos del hogar
  (RN-XVI-05).
- `puede_editar` lo calcula el router (D7): meta, administrador o `permisos.modificar_metas`
  (RN-XVII-04); tarifa, solo administrador (RN-XVI-05).

Fechas: «hoy» es la fecha de Bogotá de `now` (o de `datetime.now(UTC)`), siempre inyectable.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from sqlmodel import Session

from app.data import goals as goals_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import tariffs as tariffs_data
from app.domain import states
from app.domain.formats import first_day_of_month
from app.domain.simulator import TIMEZONE
from app.errors import ERROR_DESCRIPTIONS, NOT_FOUND_MESSAGE, ApiError, CodigoError
from app.schemas.goals_tariff import Meta, MetaCrear, MetaVista, Tarifa, TarifaCrear, TarifaVista
from app.services import hour_recovery
from app.services._readings import counting_zones, read_series
from app.services.thresholds import get_thresholds

VIGENCIA_NO_POSTERIOR_MESSAGE = (
    "El nuevo inicio de vigencia debe ser posterior al de la tarifa vigente."
)
VALIDACION_MESSAGE = "Los datos enviados no cumplen las reglas."
INVALID_YEAR_MONTH_MESSAGE = "Mes y año no válidos."
FUTURE_MONTH_MESSAGE = "No se aceptan meses futuros."
# El mismo mensaje que el guardia de `app.security` (la app decide el texto por `codigo`).
FORBIDDEN_MESSAGE = ERROR_DESCRIPTIONS[403]


# ------------------------------------------------------------------ meta
def get_goal(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    can_edit: bool,
    now: datetime | None = None,
) -> MetaVista:
    """`obtenerMeta`: Meta activa del hogar y promedio de referencia (RN-V-03, RN-XVI-04, D6).

    1. Recuperación de horas (RN-IV-05, DC-34; si falla, sigue con lo guardado).
    2. Meta activa (null si no hay) y `limite_diario_kwh` = meta ÷ días del mes de hoy (Bogotá).
    3. `promedio_diario_30d_kwh`: lecturas de las zonas que cuentan desde las 00:00 Bogotá de
       hace `window_days` días hasta la última hora completa → `states.daily_average` (solo días
       completos anteriores a hoy; null con menos de `min_days_with_data`).
    """
    moment = _recover(session, hogar_id, now)
    today = _bogota_date(moment)
    thresholds = get_thresholds()
    hour_start, _ = states.evaluated_hour(moment)
    counting = counting_zones(households_data.list_household_zones(session, hogar_id))
    series = read_series(
        session,
        hogar_id,
        [zone.id for zone in counting],
        states.reference_window_start(moment, thresholds.window_days),
        hour_start,
    )
    goal = goals_data.get_active_goal(session, hogar_id)
    return MetaVista(
        meta=None if goal is None else _active_goal_to_meta(goal),
        limite_diario_kwh=states.daily_goal_limit(
            None if goal is None else goal.valor_kwh_mensual, today
        ),
        promedio_diario_30d_kwh=states.daily_average(series, today, thresholds),
        puede_editar=can_edit,
    )


def create_goal(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    payload: MetaCrear,
    now: datetime | None = None,
) -> Meta:
    """`crearMeta`: Guardar una meta nueva (RN-V-03, RN-XVI-04, RN-XVII-04, D3).

    Bajo `lock_household` y tras volver a comprobar la membresía activa y el rol o el permiso
    (administrador o `permiso_modificar_metas`; si no: 404 `NO_ENCONTRADO` o 403
    `SIN_PERMISO_MODIFICAR_METAS`, como el guardia): la meta activa anterior pasa a 'inactiva'
    con `fecha_fin` = la `fecha_inicio` de la nueva (fecha de Bogotá de `now`). Si la anterior
    empezó ese mismo día, `fecha_fin` queda null (la restricción `metas_rango_valido` exige
    `fecha_fin > fecha_inicio`; la consulta de la meta vigente en un día desempata por
    `created_at`). Luego la nueva 'activa' y commit. `ActiveGoalExistsError` no debería ocurrir
    bajo el bloqueo: sube (500).
    """
    today = _bogota_date(_now(now))
    _lock_and_recheck(session, user_id, hogar_id, admin_only=False)
    previous = goals_data.get_active_goal(session, hogar_id)
    if previous is not None:
        fecha_fin = today if previous.fecha_inicio < today else None
        goals_data.deactivate_active_goal(session, hogar_id, fecha_fin)
    # TODO(pendiente: 500 genérico no declarado en el contrato; PENDIENTES #29). Si
    # `insert_goal` lanza `ActiveGoalExistsError` (no debería, bajo el bloqueo), sube como 500.
    row = goals_data.insert_goal(
        session,
        hogar_id=hogar_id,
        tipo=payload.tipo.value,
        valor_kwh_mensual=payload.valor_kwh_mensual,
        fecha_inicio=today,
    )
    meta = Meta(
        id=row.id,
        tipo=row.tipo,
        valor_kwh_mensual=row.valor_kwh_mensual,
        estado=row.estado,
        fecha_inicio=row.fecha_inicio,
        fecha_fin=row.fecha_fin,
    )
    session.commit()
    return meta


# ------------------------------------------------------------------ tarifa
def get_tariff(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    can_edit: bool,
    now: datetime | None = None,
) -> TarifaVista:
    """`obtenerTarifa`: la tarifa que aplica hoy (Bogotá), o null (RN-XVI-05, RN-V-01, DC-39, D4).

    Sin recuperación de horas: la tarifa no depende de las lecturas. Sin commit.
    """
    today = _bogota_date(_now(now))
    row = tariffs_data.get_current_tariff(session, hogar_id, today)
    return TarifaVista(tarifa=None if row is None else _to_tarifa(row), puede_editar=can_edit)


def create_tariff(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    payload: TarifaCrear,
    now: datetime | None = None,
) -> Tarifa:
    """`crearTarifa`: Guardar una tarifa nueva (RN-V-01, RN-V-02, RN-XVI-05, DC-39, DC-41, D4).

    `vigente_desde` "YYYY-MM" se guarda el día 1. Antes de tocar la base, 422 `VALIDACION` en
    `body.vigente_desde` si el año es 0000 (el patrón del contrato lo deja pasar) o si es un mes
    futuro: posterior al mes actual de Bogotá de `now` (contrato 0.2.10; así la «tarifa vigente»
    es siempre la abierta). El mes actual sí se acepta.
    Bajo `lock_household`, se vuelve a comprobar que quien llama sigue siendo administrador
    activo (si no: 404 `NO_ENCONTRADO` o 403 `NO_ES_ADMINISTRADOR`, como el guardia). La «tarifa
    vigente» para comparar y cerrar es la abierta (`vigente_hasta` null). Si el nuevo inicio no
    es posterior al de la abierta → 422 `VIGENCIA_NO_POSTERIOR` con `detalles.vigente_desde`
    (YYYY-MM-DD de la abierta). Si no, se cierra la abierta con `vigente_hasta` = nuevo inicio
    (fin excluido), se inserta la nueva abierta y commit. Un choque con
    `tarifas_sin_solapamiento`, con la abierta única o con el rango (`TariffOverlapError`, p. ej.
    una carrera) también da 422 `VIGENCIA_NO_POSTERIOR`, sin commit.
    """
    current_month = _bogota_date(_now(now)).replace(day=1)
    try:
        vigente_desde = first_day_of_month(payload.vigente_desde)
    except ValueError:
        raise _validation_error(["body", "vigente_desde"], INVALID_YEAR_MONTH_MESSAGE) from None
    if vigente_desde > current_month:
        raise _validation_error(["body", "vigente_desde"], FUTURE_MONTH_MESSAGE)
    _lock_and_recheck(session, user_id, hogar_id, admin_only=True)
    open_tariff = tariffs_data.get_open_tariff(session, hogar_id)
    if open_tariff is not None and vigente_desde <= open_tariff.vigente_desde:
        raise _not_later(open_tariff.vigente_desde)
    try:
        if open_tariff is not None:
            tariffs_data.close_tariff(session, hogar_id, open_tariff.id, vigente_desde)
        row = tariffs_data.insert_tariff(
            session,
            hogar_id=hogar_id,
            operador=payload.operador,
            precio_kwh=payload.precio_kwh,
            cargo_fijo_mensual=payload.cargo_fijo_mensual,
            vigente_desde=vigente_desde,
        )
    except tariffs_data.TariffOverlapError:
        raise _not_later(None if open_tariff is None else open_tariff.vigente_desde) from None
    tarifa = _to_tarifa(row)
    session.commit()
    return tarifa


# ------------------------------------------------------------------ auxiliares
def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


def _bogota_date(moment: datetime) -> date:
    """Fecha de Bogotá de `moment`; ValueError si no lleva zona horaria."""
    if moment.utcoffset() is None:
        raise ValueError("`now` debe llevar zona horaria.")
    return moment.astimezone(TIMEZONE).date()


def _lock_and_recheck(
    session: Session, user_id: UUID, hogar_id: UUID, *, admin_only: bool
) -> None:
    """Hogar bloqueado → membresía propia FOR UPDATE → rol o permiso, BAJO BLOQUEO.

    Mismo orden de bloqueo que `members_invitations._lock_admin` (hogar → membresía). Repite lo
    que ya vio la dependencia de `app.security` por si cambió entre medias: sin membresía activa
    → 404 `NO_ENCONTRADO` (RN-I-03); `admin_only` (tarifa, RN-XVI-05) y no administrador → 403
    `NO_ES_ADMINISTRADOR`; meta (RN-XVII-04): ni administrador ni `permiso_modificar_metas` del
    hogar → 403 `SIN_PERMISO_MODIFICAR_METAS`. Los permisos se leen después del bloqueo del
    hogar, que también serializa `actualizarPermisos`.
    """
    households_data.lock_household(session, hogar_id)
    own = memberships_data.get_user_membership_in_household(
        session, hogar_id, user_id, for_update=True
    )
    if own is None:
        raise ApiError(404, CodigoError.NO_ENCONTRADO, NOT_FOUND_MESSAGE)
    if own.rol == "administrador":
        return
    if admin_only:
        raise ApiError(403, CodigoError.NO_ES_ADMINISTRADOR, FORBIDDEN_MESSAGE)
    household = households_data.get_household(session, hogar_id)
    if household is None:
        raise ApiError(404, CodigoError.NO_ENCONTRADO, NOT_FOUND_MESSAGE)
    if not household.permiso_modificar_metas:
        raise ApiError(403, CodigoError.SIN_PERMISO_MODIFICAR_METAS, FORBIDDEN_MESSAGE)


def _recover(session: Session, hogar_id: UUID, now: datetime | None) -> datetime:
    """Instante único de la consulta y recuperación de horas (RN-IV-05, DC-34).

    Si la recuperación falla, sigue con lo guardado (`fill_missing_hours_or_continue`). Vive aquí
    y no en `_readings` para no cerrar el ciclo `hour_recovery` → `live_alerts` → `_readings`.
    """
    moment = _now(now)
    hour_recovery.fill_missing_hours_or_continue(session, hogar_id, moment)
    return moment


def _active_goal_to_meta(goal: goals_data.ActiveGoalRow) -> Meta:
    """La meta activa: estado 'activa' y sin `fecha_fin` (DC-41: a lo sumo una por hogar)."""
    return Meta(
        id=goal.id,
        tipo=goal.tipo,
        valor_kwh_mensual=goal.valor_kwh_mensual,
        estado="activa",
        fecha_inicio=goal.fecha_inicio,
        fecha_fin=None,
    )


def _to_tarifa(row: tariffs_data.TariffRow) -> Tarifa:
    return Tarifa(
        id=row.id,
        operador=row.operador,
        precio_kwh=row.precio_kwh,
        cargo_fijo_mensual=row.cargo_fijo_mensual,
        vigente_desde=row.vigente_desde,
        vigente_hasta=row.vigente_hasta,
    )


def _not_later(open_since: date | None) -> ApiError:
    """422 `VIGENCIA_NO_POSTERIOR`; con la fecha de inicio de la abierta cuando se conoce."""
    detalles = None if open_since is None else {"vigente_desde": open_since.isoformat()}
    return ApiError(
        422, CodigoError.VIGENCIA_NO_POSTERIOR, VIGENCIA_NO_POSTERIOR_MESSAGE, detalles
    )


def _validation_error(location: list[str], message: str) -> ApiError:
    return ApiError(
        422,
        CodigoError.VALIDACION,
        VALIDACION_MESSAGE,
        {"campos": [{"ubicacion": location, "mensaje": message}]},
    )
