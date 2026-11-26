"""Evaluación de las alertas y los consejos de las horas generadas en vivo (fase 8).

Reglas: RN-VI-02, RN-VI-03, RN-XIV-06 a RN-XIV-08, RN-XV-05 a RN-XV-07, DC-24, DC-25, DC-32,
DC-35. Solo la llama `hour_recovery._fill`, antes del commit y solo con las horas que acaba de
generar (DC-35: alertas solo sobre horas en vivo; se evalúan en un SAVEPOINT para que un fallo no
impida guardar las lecturas). Nunca la llama el onboarding: el backfill no genera alertas ni
consejos (DC-35, A-02). No hace commit ni rollback. No importa `hour_recovery` ni
`alerts_tips` (sin ciclos de importación).

Pasos de `evaluate_live_hours`:
1. Zonas que cuentan (`list_household_zones` + `counts_for_total`).
2. Lecturas de esas zonas desde `reference_window_start(primera hora, window_days)` (o desde
   90 días antes del primer mes a cerrar) hasta la última hora en vivo.
3. Estado de zona por hora (`states.evaluate_zone_hours`) → claves candidatas
   (`alert_rules.zone_alert_keys` y `month_close_keys`) → claves ya guardadas → alertas de consumo
   (`alert_rules.evaluate_alert_rules`, una por regla, zona y día, A-01).
4. Cierre de mes (`months_to_close` + `evaluate_month_close`; DC-32 y RN-XIV-07): referencia =
   meta vigente el último día del mes o promedio de los días completos anteriores (máximo 90).
5. Alta de cada alerta y su entrega (`alert_recipients`; RN-VI-02, RN-XIV-06). Si `insert_alert`
   devuelve None (la clave ya existía: carrera), no se crea su consejo.
6. Consejos (`build_tips`; RN-XV-05: vigencia de 7 días; DC-35: consejo y aviso con la alerta;
   DC-24: variante alterna, la anterior se reconoce por su título) con una fila `pendiente` por
   miembro (RN-VI-03, RN-XV-06) y el aviso «Nuevo consejo» (`nuevo_consejo:<consejo_id>`) con su
   entrega.
Cada evento lleva `created_at` = momento del evento (fin de la hora; cierre: 00:00 del día 1).
Los textos salen de `config_files/textos-backend.es-CO.json` y se guardan resueltos.

**Miembros que llegaron después del evento.** La recuperación puede generar horas de hace días:
la entrega de una alerta (`alertas_usuario`) y la fila de un consejo (`consejos_usuario`) solo
son para los miembros activos con `fecha_ingreso <= created_at` del evento (RN-XV-06: un miembro
que ingresa después no recibe consejos anteriores; RN-VI-02: sin efecto retroactivo).
Limitación: el permiso del hogar (`permiso_recibir_alertas`) y los interruptores de cada miembro
(`notif_consumo`, `notif_consejos`) no guardan historial, así que se usan sus valores actuales,
no los que tenían en el momento del evento. Tampoco se entrega a quien estaba en el evento pero
ya no es miembro activo.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlmodel import Session

from app.data import alerts as alerts_data
from app.data import goals as goals_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import tips as tips_data
from app.data.memberships import AlertMemberRow
from app.domain import alert_rules, states
from app.domain.alert_rules import (
    AlertDecision,
    ExistingTip,
    PlannedAlert,
    TipTrigger,
    ZoneInfo,
)
from app.domain.formats import BackendTexts, build_event_key
from app.domain.simulator import TIMEZONE
from app.services._alert_delivery import insert_planned_alert, present_members
from app.services._readings import ReadingsByZone, counting_zones, read_series
from app.services.backend_texts import get_backend_texts
from app.services.thresholds import get_thresholds

logger = logging.getLogger(__name__)

# Regla de la clave del aviso «Nuevo consejo»: `nuevo_consejo:<consejo_id>` (DC-25, DC-35).
NEW_TIP_NOTICE_RULE = "nuevo_consejo"


@dataclass(frozen=True)
class LiveEvaluationSummary:
    """Lo que creó una evaluación en vivo: alertas (incluidos los avisos) y consejos."""

    alerts: int
    tips: int


NOTHING = LiveEvaluationSummary(alerts=0, tips=0)


def evaluate_live_hours(
    session: Session,
    hogar_id: UUID,
    live_hours_by_zone_type: Mapping[str, Sequence[datetime]],
) -> LiveEvaluationSummary:
    """Alertas y consejos de las horas recién generadas en vivo (DC-35, A-01, A-04).

    `live_hours_by_zone_type`: por tipo de zona, los inicios de hora (con zona horaria) que acaba
    de guardar la recuperación. Solo se evalúan esas horas (nunca el backfill) y solo en las zonas
    que cuentan. No recibe la hora actual: cada evento se fecha con su hora (fin de la hora;
    cierre: 00:00 del día 1), y el cierre de mes se decide con las mismas horas. Sin commit ni
    rollback: lo maneja `hour_recovery` (SAVEPOINT).
    """
    if not any(live_hours_by_zone_type.values()):
        return NOTHING

    thresholds = get_thresholds()
    texts = get_backend_texts()
    counting = counting_zones(households_data.list_household_zones(session, hogar_id))
    zone_by_type = {zone.tipo: zone.id for zone in counting}
    hour_starts_by_zone = {
        zone_by_type[tipo]: sorted(set(hours))
        for tipo, hours in live_hours_by_zone_type.items()
        if tipo in zone_by_type and hours
    }
    live_hours = sorted({hour for hours in hour_starts_by_zone.values() for hour in hours})
    if not live_hours:
        return NOTHING

    created_at = households_data.get_household_created_at(session, hogar_id)
    months = [] if created_at is None else alert_rules.months_to_close(live_hours, created_at)
    start = states.reference_window_start(live_hours[0], thresholds.window_days)
    if months:
        start = min(start, _month_close_read_start(months[0]))
    series = read_series(session, hogar_id, [zone.id for zone in counting], start, live_hours[-1])

    zones = {zone.id: ZoneInfo(zone.id, zone.tipo) for zone in counting}
    zone_hours = states.evaluate_zone_hours(series, hour_starts_by_zone, thresholds)
    candidate_keys = alert_rules.zone_alert_keys(zone_hours, zones)
    for month in months:
        candidate_keys.extend(alert_rules.month_close_keys(hogar_id, month))
    existing = alerts_data.list_existing_event_keys(session, hogar_id, candidate_keys)

    decisions = alert_rules.evaluate_alert_rules(zone_hours, zones, existing, texts)
    decisions.extend(_month_close_decisions(session, hogar_id, months, series, existing, texts))
    if not decisions:
        return NOTHING

    summary = _store_decisions(session, hogar_id, decisions, texts)
    logger.info(
        "Alertas evaluadas: horas=%d alertas=%d consejos=%d",
        len(live_hours),
        summary.alerts,
        summary.tips,
    )
    return summary


# ------------------------------------------------------------------ pasos de la evaluación
def _month_close_read_start(first_month: date) -> datetime:
    """00:00 Bogotá de 90 días antes del primer mes a cerrar (referencia del cierre, DC-32)."""
    first = first_month - timedelta(days=alert_rules.MONTH_CLOSE_MAX_DAYS)
    return datetime(first.year, first.month, first.day, tzinfo=TIMEZONE)


def _month_close_decisions(
    session: Session,
    hogar_id: UUID,
    months: Sequence[date],
    series: ReadingsByZone,
    existing: set[str],
    texts: BackendTexts,
) -> list[AlertDecision]:
    """Cierre de cada mes (DC-32 y RN-XIV-07). Sin referencia → sin alerta."""
    if not months:
        return []
    daily = alert_rules.daily_complete_totals(series)
    decisions = []
    for month in months:
        last_day = month.replace(day=states.days_in_month(month))
        goal = goals_data.get_goal_active_on(session, hogar_id, last_day)
        reference, kind = alert_rules.month_close_reference(
            daily, month, None if goal is None else goal.valor_kwh_mensual
        )
        decision = alert_rules.evaluate_month_close(
            hogar_id,
            month,
            alert_rules.month_total_kwh(series, month),
            reference,
            kind,
            existing,
            texts,
        )
        if decision is not None:
            decisions.append(decision)
    return decisions


def _store_decisions(
    session: Session, hogar_id: UUID, decisions: Sequence[AlertDecision], texts: BackendTexts
) -> LiveEvaluationSummary:
    """Alta de alertas, entregas, consejos, filas por miembro y avisos.

    RN-VI-02, RN-XIV-06 (entrega) y RN-VI-03, RN-XV-06 (consejos): cada evento solo llega a los
    miembros que ya estaban en el hogar cuando ocurrió (`fecha_ingreso <= created_at`).
    """
    members = memberships_data.list_alert_members(session, hogar_id)
    permission = bool(memberships_data.get_alert_permission(session, hogar_id))
    alerts = 0
    triggers: list[TipTrigger] = []
    for decision in decisions:
        if _store_alert(session, hogar_id, decision.alert, members, permission) is None:
            continue  # la clave ya existía: tampoco se crea su consejo
        alerts += 1
        if decision.tip_trigger is not None:
            triggers.append(decision.tip_trigger)
    if not triggers:
        return LiveEvaluationSummary(alerts=alerts, tips=0)

    existing_tips = [
        ExistingTip(row.regla_origen, row.zona_id, row.titulo, row.created_at)
        for row in tips_data.list_latest_tips(session, hogar_id)
    ]
    planned = alert_rules.build_tips(triggers, existing_tips, texts)
    for tip in planned:
        consejo_id = tips_data.insert_tip(
            session,
            hogar_id=hogar_id,
            categoria=tip.categoria,
            prioridad=tip.prioridad,
            zona_id=tip.zona_id,
            titulo=tip.titulo,
            descripcion=tip.descripcion,
            regla_origen=tip.regla_origen,
            created_at=tip.created_at,
        )
        assigned = [member.usuario_id for member in present_members(members, tip.created_at)]
        tips_data.insert_tip_assignments(session, consejo_id, assigned)
        notice = replace(
            tip.notice, clave_evento=build_event_key(NEW_TIP_NOTICE_RULE, str(consejo_id))
        )
        if _store_alert(session, hogar_id, notice, members, permission) is not None:
            alerts += 1
    return LiveEvaluationSummary(alerts=alerts, tips=len(planned))


def _store_alert(
    session: Session,
    hogar_id: UUID,
    alert: PlannedAlert,
    members: Sequence[AlertMemberRow],
    permission: bool,
) -> UUID | None:
    """Inserta la alerta y la entrega a quien corresponda (RN-VI-02, RN-XIV-06).

    Solo a los miembros con `fecha_ingreso <= alert.created_at`; entre ellos, `alert_recipients`
    aplica el permiso del hogar y el interruptor de la categoría (valores actuales).
    """
    alerta_id = insert_planned_alert(session, hogar_id, alert)
    if alerta_id is not None:
        present = present_members(members, alert.created_at)
        recipients = alert_rules.alert_recipients(alert.categoria, present, permission)
        alerts_data.insert_alert_deliveries(session, alerta_id, recipients)
    return alerta_id
