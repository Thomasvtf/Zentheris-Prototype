"""Casos de uso de la etiqueta «Alertas y consejos» (fase 8).

Reglas: RN-VI-02 a RN-VI-05, RN-XIV-03 a RN-XIV-05, RN-XV-02 a RN-XV-06, DC-34. La autorización
(membresía, rol y permiso) ya la resolvieron las dependencias de `security/` en el router; aquí no
se repite. La generación de alertas y consejos sobre las horas en vivo vive en
`app.services.live_alerts` (la llama `hour_recovery`).

**Consultas** (`list_alerts`, `count_unread_alerts`, `list_tips`): recuperan primero las horas
faltantes con `hour_recovery.fill_missing_hours_or_continue` (RN-IV-05, DC-34; decisión de
Nicolás del 23/11/2026: si la recuperación falla, la consulta responde con lo guardado): 200 con
lo ya guardado y un WARNING sin datos.
**Escrituras** (`mark_alerts_read`, `update_tip_status`): sin recuperación; hacen commit. Si algo
lanza antes, la sesión de la petición se cierra sin commit (rollback).
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlmodel import Session

from app.data import alerts as alerts_data
from app.data import tips as tips_data
from app.data.alerts import UserAlertRow
from app.data.tips import UserTipRow
from app.domain import alert_rules
from app.domain.formats import zone_name
from app.errors import NOT_FOUND_MESSAGE, ApiError, CodigoError
from app.schemas.alerts_tips import (
    Alerta,
    AlertasLista,
    AlertasMarcadas,
    AlertasMarcar,
    AlertasNoLeidas,
    CategoriaAlerta,
    Consejo,
    ConsejoEstadoActualizar,
    ConsejosLista,
)
from app.services import hour_recovery

# RN-XIV-05: una alerta leída se oculta 7 días después de `leida_en`.
READ_ALERT_VISIBLE_DAYS = 7
# RN-XV-03: un consejo completado se oculta 7 días después de `completada_en`.
COMPLETED_TIP_VISIBLE_DAYS = 7


# ------------------------------------------------------------------ casos de uso
def list_alerts(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    categoria: CategoriaAlerta | None,
    limite: int,
    now: datetime | None = None,
) -> AlertasLista:
    """`listarAlertas`: Alertas entregadas al usuario (RN-XIV-01, RN-XIV-04, RN-XIV-05).

    Recupera primero las horas faltantes (RN-IV-05, DC-34; si falla, responde con lo guardado).
    Solo las filas de `alertas_usuario` de esta persona en el hogar, de la más reciente a la más
    antigua, como máximo `limite`; las leídas hace más de 7 días se ocultan (visible si
    `leida_en > now − 7 días`) y las no leídas nunca (RN-XIV-05).
    """
    moment = _recover(session, hogar_id, now)
    rows = alerts_data.list_user_alerts(
        session,
        user_id,
        hogar_id,
        None if categoria is None else categoria.value,
        limite,
        moment - timedelta(days=READ_ALERT_VISIBLE_DAYS),
    )
    return AlertasLista(alertas=[_to_alert(row) for row in rows])


def count_unread_alerts(
    session: Session, user_id: UUID, hogar_id: UUID, now: datetime | None = None
) -> AlertasNoLeidas:
    """`contarAlertasNoLeidas`: Indicador de la campana (RN-XII-02, RN-XIV-05).

    Recupera primero las horas faltantes (RN-IV-05, DC-34): así cuentan las alertas que generen.
    """
    _recover(session, hogar_id, now)
    return AlertasNoLeidas(cantidad=alerts_data.count_unread_alerts(session, user_id, hogar_id))


def mark_alerts_read(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    payload: AlertasMarcar,
    now: datetime | None = None,
) -> AlertasMarcadas:
    """`marcarAlertasLeidas`: Marcar como leídas las alertas visibles al entrar (RN-XIV-03, RN-VI-05).

    Solo las entregas de esta persona, de alertas del hogar y aún sin leer; las demás se ignoran.
    `leida_en` = `now`. Sin recuperación; commit.
    """
    moment = _moment(now)
    marked = alerts_data.mark_alerts_read(session, user_id, hogar_id, payload.alerta_ids, moment)
    session.commit()
    return AlertasMarcadas(marcadas=marked)


def list_tips(
    session: Session, user_id: UUID, hogar_id: UUID, now: datetime | None = None
) -> ConsejosLista:
    """`listarConsejos`: Consejos visibles para el usuario (RN-VI-03, RN-XV-02 a RN-XV-05).

    Recupera primero las horas faltantes (RN-IV-05, DC-34; si falla, responde con lo guardado).
    Pendientes vigentes (7 días desde su creación) por prioridad alta, media, baja; después los
    completados hace menos de 7 días.
    """
    moment = _recover(session, hogar_id, now)
    rows = tips_data.list_user_tips(
        session,
        user_id,
        hogar_id,
        moment - timedelta(days=alert_rules.TIP_VALIDITY_DAYS),
        moment - timedelta(days=COMPLETED_TIP_VISIBLE_DAYS),
    )
    return ConsejosLista(consejos=[_to_tip(row) for row in rows])


def update_tip_status(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    consejo_id: UUID,
    payload: ConsejoEstadoActualizar,
    now: datetime | None = None,
) -> Consejo:
    """`actualizarEstadoConsejo`: Marcar o desmarcar un consejo (RN-XV-03, RN-VI-05).

    404 NO_ENCONTRADO si la persona no tiene fila en `consejos_usuario` para ese consejo del
    hogar (RN-XV-06). `completada` registra `completada_en` = `now`; `pendiente` lo deja null.
    Pedir el estado que ya tiene no cambia nada (no reinicia `completada_en`). Sin recuperación;
    commit.
    """
    moment = _moment(now)
    row = tips_data.get_user_tip(session, user_id, hogar_id, consejo_id)
    if row is None:
        raise _not_found()
    if row.estado == payload.estado:
        return _to_tip(row)
    completed_at = moment if payload.estado == "completada" else None
    if not tips_data.update_user_tip_status(
        session, user_id, hogar_id, consejo_id, payload.estado, completed_at
    ):
        raise _not_found()
    session.commit()
    return _to_tip(replace(row, estado=payload.estado, completada_en=completed_at))


# ------------------------------------------------------------------ auxiliares de las consultas
def _moment(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


def _recover(session: Session, hogar_id: UUID, now: datetime | None) -> datetime:
    """Instante único de la consulta y recuperación de las horas faltantes (RN-IV-05, DC-34).

    Si la recuperación falla, sigue con los datos guardados (`fill_missing_hours_or_continue`).
    `now` sin zona horaria: `ValueError` antes de tocar la base.
    """
    moment = _moment(now)
    hour_recovery.fill_missing_hours_or_continue(session, hogar_id, moment)
    return moment


def _not_found() -> ApiError:
    return ApiError(404, CodigoError.NO_ENCONTRADO, NOT_FOUND_MESSAGE)


def _zone_name(zona_tipo: str | None) -> str | None:
    """Nombre visible de la zona (RN-XII-03); None si no es de una zona."""
    return None if zona_tipo is None else zone_name(zona_tipo)


def _to_alert(row: UserAlertRow) -> Alerta:
    return Alerta(
        id=row.id,
        categoria=CategoriaAlerta(row.categoria),
        severidad=row.severidad,  # type: ignore[arg-type]
        titulo=row.titulo,
        mensaje=row.mensaje,
        zona_id=row.zona_id,
        zona_nombre=_zone_name(row.zona_tipo),
        creada_en=row.created_at,
        leida_en=row.leida_en,
    )


def _to_tip(row: UserTipRow) -> Consejo:
    return Consejo(
        id=row.id,
        categoria=row.categoria,
        prioridad=row.prioridad,  # type: ignore[arg-type]
        titulo=row.titulo,
        descripcion=row.descripcion,
        zona_id=row.zona_id,
        zona_nombre=_zone_name(row.zona_tipo),
        estado=row.estado,  # type: ignore[arg-type]
        completada_en=row.completada_en,
        creado_en=row.created_at,
    )
