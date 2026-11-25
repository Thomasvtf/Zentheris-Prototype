"""Reglas de alertas y consejos (RN-XIV-06 a RN-XIV-08, RN-XV-05 a RN-XV-07, DC-24, DC-25, DC-32).

Puro: sin FastAPI, sin SQL, sin archivos y sin reloj. Los textos llegan ya leídos
(`formats.parse_backend_texts`) y los estados de zona ya calculados (`states.evaluate_zone_hours`).
Solo se llama con horas generadas en vivo, nunca con el backfill (DC-35, A-02): eso lo garantiza
`services/`, que es quien decide qué horas pasa.

- Consumo: una alerta por regla, zona y día de Bogotá (`<regla>:<zona_id>:<AAAA-MM-DD>`); elevado
  y crítico son reglas distintas (RN-XIV-08). `created_at` = fin de la hora que la disparó.
- Cierre de mes: `<regla>:<hogar_id>:<AAAA-MM>`; dentro o encima de la referencia del hogar (meta
  activa o promedio de los días completos anteriores, máximo 90, × días del mes).
- Consejos: uno por regla y zona mientras haya uno vigente (7 días, RN-XV-05); la variante nueva
  es la que no usó el anterior (DC-24).
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from app.domain.formats import (
    MONTH_NAMES,
    BackendTexts,
    TipTemplate,
    build_event_key,
    format_hour,
    format_kw,
    format_kwh,
    render_backend_text,
    zone_name,
)
from app.domain.simulator import TIMEZONE
from app.domain.states import (
    HOURS_PER_DAY,
    HourlySeries,
    ZoneHourState,
    days_in_month,
    household_hourly_totals,
)

AlertCategory = Literal["consumo", "consejo", "informacion"]
Severity = Literal["informativa", "advertencia", "critica"]
TipRule = Literal["zona_elevada", "zona_critica", "cierre_mes_encima"]
ReferenceKind = Literal["meta", "promedio"]

TIP_VALIDITY_DAYS = 7
MONTH_CLOSE_MAX_DAYS = 90
# Decimales al comparar el total del mes con su referencia (kWh): quitan el ruido de coma flotante
# de las sumas para que un total igual a la referencia no cuente como exceso (tolerancia 0).
KWH_COMPARE_DECIMALS = 6
# Estado de la zona -> (regla de la alerta, regla del consejo) (RN-XIV-07, RN-XV-07, DC-25).
ZONE_STATE_RULES: Mapping[str, tuple[str, TipRule]] = {
    "elevado": ("consumo_elevado", "zona_elevada"),
    "critico": ("consumo_critico", "zona_critica"),
}
MONTH_CLOSE_INSIDE = "cierre_mes_dentro"
MONTH_CLOSE_ABOVE = "cierre_mes_encima"
NOTICE_ZONE = "nuevo_consejo_zona"
NOTICE_GENERAL = "nuevo_consejo_general"
# TODO(pendiente: frase en config_files): `{referencia}` del cierre de mes. textos-backend solo la
# describe en `_meta.variables_por_clave` («tu meta de N kWh» o «tu promedio de N kWh»).
REFERENCE_PHRASES: Mapping[str, str] = {
    "meta": "tu meta de {kwh} kWh",
    "promedio": "tu promedio de {kwh} kWh",
}


@dataclass(frozen=True)
class ZoneInfo:
    """Zona que cuenta para el hogar."""

    zona_id: UUID
    tipo: str


@dataclass(frozen=True)
class PlannedAlert:
    regla_origen: str
    categoria: AlertCategory
    severidad: Severity
    titulo: str
    mensaje: str
    zona_id: UUID | None
    clave_evento: str
    created_at: datetime


@dataclass(frozen=True)
class TipTrigger:
    """Consejo que pide una alerta recién creada."""

    regla_origen: TipRule
    zona_id: UUID | None
    zona_tipo: str | None
    moment: datetime  # = created_at de la alerta
    month: date | None  # día 1 del mes, solo en el cierre (para {mes})


@dataclass(frozen=True)
class AlertDecision:
    alert: PlannedAlert
    tip_trigger: TipTrigger | None


@dataclass(frozen=True)
class ExistingTip:
    """Último consejo conocido de una regla y zona."""

    regla_origen: str
    zona_id: UUID | None
    titulo: str
    created_at: datetime


@dataclass(frozen=True)
class PlannedTip:
    regla_origen: TipRule
    categoria: Literal["zona", "general"]
    prioridad: Literal["alta", "media", "baja"]
    zona_id: UUID | None
    titulo: str
    descripcion: str
    variante: int
    created_at: datetime
    notice: PlannedAlert  # aviso «Nuevo consejo»; clave_evento "" (la arma el servicio con el id)


@dataclass(frozen=True)
class AlertMember:
    usuario_id: UUID
    rol: Literal["administrador", "miembro"]
    notif_consumo: bool
    notif_consejos: bool


# ------------------------------------------------------------------ utilidades
def _bogota(moment: datetime) -> datetime:
    if moment.utcoffset() is None:
        raise ValueError("se exige una fecha con zona horaria")
    return moment.astimezone(TIMEZONE)


def _require_month(month: date) -> None:
    if month.day != 1:
        raise ValueError("el mes se indica con su día 1")


def _next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def _month_end(month: date) -> datetime:
    """00:00 Bogotá del día 1 del mes siguiente: fin del mes y `created_at` del cierre
    (created_at = momento del evento: fin de la hora; cierre: 00:00 del día 1)."""
    following = _next_month(month)
    return datetime(following.year, following.month, following.day, tzinfo=TIMEZONE)


def _planned(
    template_key: str,
    texts: BackendTexts,
    variables: Mapping[str, object],
    zona_id: UUID | None,
    clave_evento: str,
    created_at: datetime,
) -> PlannedAlert:
    template = texts.alerts[template_key]
    return PlannedAlert(
        regla_origen=template.regla_origen,
        categoria=cast(AlertCategory, template.categoria),
        severidad=cast(Severity, template.severidad),
        titulo=render_backend_text(template.titulo, variables),
        mensaje=render_backend_text(template.mensaje, variables),
        zona_id=zona_id,
        clave_evento=clave_evento,
        created_at=created_at,
    )


# ------------------------------------------------------------------ alertas de consumo
@dataclass(frozen=True)
class _ZoneCandidate:
    item: ZoneHourState
    power_kw: float  # nunca None: una hora sin dato no pide alerta
    zone: ZoneInfo
    alert_rule: str
    tip_rule: TipRule
    start: datetime  # inicio de la hora en Bogotá
    key: str


def _zone_candidates(
    zone_hours: Sequence[ZoneHourState], zones: Mapping[UUID, ZoneInfo]
) -> list[_ZoneCandidate]:
    """Horas que piden alerta de consumo, en orden cronológico (y por zona), con su clave.

    Puede repetir claves (la misma regla, zona y día en varias horas): quien la usa decide.
    """
    candidates: list[_ZoneCandidate] = []
    ordered = sorted(zone_hours, key=lambda item: (_bogota(item.hour_start), item.zona_id))
    for item in ordered:
        rules = ZONE_STATE_RULES.get(item.state)
        zone = zones.get(item.zona_id)
        if rules is None or zone is None or item.power_kw is None:
            continue
        alert_rule, tip_rule = rules
        start = _bogota(item.hour_start)
        key = build_event_key(alert_rule, str(item.zona_id), start.date().isoformat())
        candidate = _ZoneCandidate(item, item.power_kw, zone, alert_rule, tip_rule, start, key)
        candidates.append(candidate)
    return candidates


def zone_alert_keys(
    zone_hours: Sequence[ZoneHourState], zones: Mapping[UUID, ZoneInfo]
) -> list[str]:
    """Claves candidatas de las alertas de consumo (`<regla>:<zona_id>:<AAAA-MM-DD>`, DC-25).

    Sin renderizar textos y sin repetir, en el mismo orden en que `evaluate_alert_rules` las
    decidiría con `existing_keys` vacío. Sirve para consultar de una vez qué claves ya existen.
    """
    return list(dict.fromkeys(candidate.key for candidate in _zone_candidates(zone_hours, zones)))


def evaluate_alert_rules(
    zone_hours: Sequence[ZoneHourState],
    zones: Mapping[UUID, ZoneInfo],
    existing_keys: Collection[str],
    texts: BackendTexts,
) -> list[AlertDecision]:
    """Alertas de consumo de las horas en vivo (RN-XIV-07, RN-XIV-08, DC-25, DC-35).

    Recorre las horas en orden cronológico (y por zona). `elevado` -> `consumo_elevado` con
    consejo `zona_elevada`; `critico` -> `consumo_critico` con consejo `zona_critica`; otros
    estados no generan nada. Clave `<regla>:<zona_id>:<AAAA-MM-DD>` (fecha Bogotá del inicio de la
    hora): si ya está en `existing_keys` o ya se decidió en esta llamada, no se repite (A-01).
    Una zona fuera de `zones` (no cuenta) se ignora. `created_at` = momento del evento: fin de la
    hora que la disparó.
    """
    decisions: list[AlertDecision] = []
    taken = set(existing_keys)
    for candidate in _zone_candidates(zone_hours, zones):
        key, item = candidate.key, candidate.item
        if key in taken:
            continue
        taken.add(key)
        end = candidate.start + timedelta(hours=1)
        variables = {
            "zona": zone_name(candidate.zone.tipo),
            "hora_ini": format_hour(candidate.start),
            "hora_fin": format_hour(end),
            "kw": format_kw(candidate.power_kw),
        }
        alert = _planned(candidate.alert_rule, texts, variables, item.zona_id, key, end)
        trigger = TipTrigger(candidate.tip_rule, item.zona_id, candidate.zone.tipo, end, None)
        decisions.append(AlertDecision(alert, trigger))
    return decisions


# ------------------------------------------------------------------ cierre de mes
def month_close_keys(hogar_id: UUID, month: date) -> tuple[str, str]:
    """(clave dentro, clave encima) del mes: `<regla>:<hogar_id>:<AAAA-MM>` (DC-25)."""
    _require_month(month)
    period = f"{month.year:04d}-{month.month:02d}"
    return (
        build_event_key(MONTH_CLOSE_INSIDE, str(hogar_id), period),
        build_event_key(MONTH_CLOSE_ABOVE, str(hogar_id), period),
    )


def months_to_close(
    live_hour_starts: Collection[datetime], household_created_at: datetime
) -> list[date]:
    """Meses a cerrar (DC-32 y RN-XIV-07, cierre de mes), como su día 1 y en orden ascendente.

    Un mes M se cierra si la hora 23:00 de su último día (Bogotá) está entre las horas en vivo y
    M termina (00:00 del día 1 siguiente) después de `household_created_at`.
    """
    created = _bogota(household_created_at)
    months: set[date] = set()
    for moment in live_hour_starts:
        local = _bogota(moment)
        if local.hour != HOURS_PER_DAY - 1 or local.day != days_in_month(local.date()):
            continue
        month = date(local.year, local.month, 1)
        if _month_end(month) > created:
            months.add(month)
    return sorted(months)


def daily_complete_totals(readings_by_zone: Mapping[UUID, HourlySeries]) -> dict[date, float]:
    """Total del hogar por fecha Bogotá, solo de días con las 24 horas con todas las zonas."""
    by_day: dict[date, list[float]] = {}
    for moment, value in sorted(household_hourly_totals(readings_by_zone).items()):
        by_day.setdefault(moment.date(), []).append(value)
    return {
        day: math.fsum(values) for day, values in by_day.items() if len(values) == HOURS_PER_DAY
    }


def month_total_kwh(readings_by_zone: Mapping[UUID, HourlySeries], month: date) -> float:
    """Suma de los totales horarios del hogar (horas con todas las zonas) dentro del mes."""
    _require_month(month)
    return math.fsum(
        value
        for moment, value in household_hourly_totals(readings_by_zone).items()
        if (moment.year, moment.month) == (month.year, month.month)
    )


def month_close_reference(
    daily_totals: Mapping[date, float],
    month: date,
    goal_kwh: float | None,
    max_days: int = MONTH_CLOSE_MAX_DAYS,
) -> tuple[float | None, ReferenceKind]:
    """Referencia del cierre (RN-XIV-07, DC-32).

    Con meta activa el último día del mes: (`goal_kwh`, "meta"). Si no: media de los últimos
    `max_days` días completos ANTERIORES al mes × días del mes, "promedio"; (None, "promedio")
    si no hay ninguno.

    TODO(pendiente: cierre de mes sin referencia — sin meta y sin días completos anteriores no se
    crea alerta; RN-XIV-07/DC-32 no lo definen).
    """
    _require_month(month)
    if goal_kwh is not None:
        return goal_kwh, "meta"
    previous = sorted(day for day in daily_totals if day < month)[-max_days:]
    if not previous or max_days <= 0:
        return None, "promedio"
    average = math.fsum(daily_totals[day] for day in previous) / len(previous)
    return average * days_in_month(month), "promedio"


def evaluate_month_close(
    hogar_id: UUID,
    month: date,
    total_kwh: float,
    reference_kwh: float | None,
    reference_type: ReferenceKind,
    existing_keys: Collection[str],
    texts: BackendTexts,
) -> AlertDecision | None:
    """Alerta de cierre del mes (RN-XIV-07, DC-32).

    None sin referencia o si ya existe la clave dentro o la clave encima del mes. Encima si el
    total supera la referencia (tolerancia 0; ambos redondeados a `KWH_COMPARE_DECIMALS` para no
    confundir ruido de coma flotante con un exceso): `cierre_mes_encima` y consejo general del
    cierre. Si no, `cierre_mes_dentro` sin consejo. `created_at` = momento del evento (cierre:
    00:00 Bogotá del día 1 siguiente).

    TODO(pendiente: cierre de mes sin referencia — sin meta y sin días completos anteriores no se
    crea alerta; RN-XIV-07/DC-32 no lo definen).
    """
    inside_key, above_key = month_close_keys(hogar_id, month)
    if reference_kwh is None or inside_key in existing_keys or above_key in existing_keys:
        return None
    above = round(total_kwh, KWH_COMPARE_DECIMALS) > round(reference_kwh, KWH_COMPARE_DECIMALS)
    created_at = _month_end(month)
    variables = {
        "mes": MONTH_NAMES[month.month],
        "kwh": format_kwh(total_kwh),
        "referencia": REFERENCE_PHRASES[reference_type].format(kwh=format_kwh(reference_kwh)),
    }
    if above:
        alert = _planned(MONTH_CLOSE_ABOVE, texts, variables, None, above_key, created_at)
        trigger = TipTrigger(MONTH_CLOSE_ABOVE, None, None, created_at, month)
        return AlertDecision(alert, trigger)
    alert = _planned(MONTH_CLOSE_INSIDE, texts, variables, None, inside_key, created_at)
    return AlertDecision(alert, None)


# ------------------------------------------------------------------ consejos
def _tip_group(texts: BackendTexts, regla: str, zona_tipo: str | None) -> list[TipTemplate]:
    group = sorted(
        (t for t in texts.tips if (t.regla_origen, t.zona) == (regla, zona_tipo)),
        key=lambda t: t.variante,
    )
    if not group:
        raise ValueError(f"no hay plantillas de consejo para {regla}/{zona_tipo}")
    return group


def _next_variant(group: Sequence[TipTemplate], previous_title: str | None) -> TipTemplate:
    """DC-24 (variante alterna; la anterior se reconoce por su título); sin anterior
    reconocido, la primera."""
    for position, template in enumerate(group):
        if template.titulo == previous_title:
            return group[(position + 1) % len(group)]
    return group[0]


def _check_trigger(trigger: TipTrigger) -> None:
    if trigger.regla_origen == MONTH_CLOSE_ABOVE:
        if trigger.month is None or trigger.zona_id is not None:
            raise ValueError("el consejo del cierre necesita el mes y no lleva zona")
        _require_month(trigger.month)
    elif trigger.zona_id is None or trigger.zona_tipo is None:
        raise ValueError("un consejo de zona necesita zona_id y zona_tipo")


def build_tips(
    triggers: Sequence[TipTrigger],
    existing_tips: Sequence[ExistingTip],
    texts: BackendTexts,
) -> list[PlannedTip]:
    """Consejos que piden las alertas recién creadas (RN-XV-07).

    RN-XV-05 (vigencia de 7 días), DC-35 (consejo y aviso con la alerta) y DC-24 (variante
    alterna; la anterior se reconoce por su título).

    En orden cronológico de `moment`. Si hay un consejo de la misma regla y zona (existente o
    planeado aquí) con `created_at + 7 días > moment`, no se crea otro. Si no, el consejo usa la
    variante que no usó el último de esa regla y zona (reconocido por su título en el catálogo
    de la regla y el tipo de zona) y trae su aviso «Nuevo consejo» con el mismo `created_at`.
    """
    for trigger in triggers:
        _check_trigger(trigger)
    latest: dict[tuple[str, UUID | None], tuple[datetime, str]] = {}
    for tip in existing_tips:
        key = (tip.regla_origen, tip.zona_id)
        if key not in latest or tip.created_at > latest[key][0]:
            latest[key] = (tip.created_at, tip.titulo)
    validity = timedelta(days=TIP_VALIDITY_DAYS)
    planned: list[PlannedTip] = []
    for trigger in sorted(triggers, key=lambda item: _bogota(item.moment)):
        key = (trigger.regla_origen, trigger.zona_id)
        previous = latest.get(key)
        if previous is not None and previous[0] + validity > trigger.moment:
            continue
        group = _tip_group(texts, trigger.regla_origen, trigger.zona_tipo)
        template = _next_variant(group, previous[1] if previous else None)
        planned.append(_plan_tip(trigger, template, texts))
        latest[key] = (trigger.moment, template.titulo)
    return planned


def _plan_tip(trigger: TipTrigger, template: TipTemplate, texts: BackendTexts) -> PlannedTip:
    variables: dict[str, object] = {}
    if trigger.month is not None:
        variables["mes"] = MONTH_NAMES[trigger.month.month]
    if trigger.zona_tipo is not None:
        notice = _planned(
            NOTICE_ZONE,
            texts,
            {"zona": zone_name(trigger.zona_tipo)},
            trigger.zona_id,
            "",
            trigger.moment,
        )
        categoria: Literal["zona", "general"] = "zona"
    else:
        notice = _planned(NOTICE_GENERAL, texts, {}, None, "", trigger.moment)
        categoria = "general"
    return PlannedTip(
        regla_origen=trigger.regla_origen,
        categoria=categoria,
        prioridad=cast(Literal["alta", "media", "baja"], template.prioridad),
        zona_id=trigger.zona_id,
        titulo=render_backend_text(template.titulo, variables),
        descripcion=render_backend_text(template.descripcion, variables),
        variante=template.variante,
        created_at=trigger.moment,
        notice=notice,
    )


# ------------------------------------------------------------------ entrega
def alert_recipients(
    categoria: AlertCategory, members: Sequence[AlertMember], permiso_recibir_alertas: bool
) -> list[UUID]:
    """Destinatarios de una alerta (RN-VI-02, RN-XIV-06: entrega), en el orden de entrada.

    `members` son los miembros activos. Recibe quien es administrador o, si no, cuando el hogar
    da `permiso_recibir_alertas`; y además tiene encendido el interruptor de la categoría
    (`notif_consejos` para consejo; `notif_consumo` para consumo e información).
    """
    recipients: list[UUID] = []
    for member in members:
        allowed = member.rol == "administrador" or permiso_recibir_alertas
        switch = member.notif_consejos if categoria == "consejo" else member.notif_consumo
        if allowed and switch:
            recipients.append(member.usuario_id)
    return recipients
