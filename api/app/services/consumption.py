"""Casos de uso de la etiqueta «Consumo».

Fase 6: consumo actual, consumo por zonas y detalle de una zona (RN-XI-01 a RN-XI-09, RN-XII-03,
RN-XII-05 a RN-XII-07, RN-V-01, RN-V-02, RN-IV-05, DC-28, DC-34). Fase 7: historial por periodo
(RN-XIII-01 a RN-XIII-06, DC-29 a DC-31; el cálculo vive en `app.domain.history`). Fuentes de
datos sigue en 501 (fase 10).

Pasos de cada consulta (la seguridad ya corrió en el router); cada caso de uso decide su rango:
1. `_recover`: un único instante (`now` o `datetime.now(UTC)`) y la recuperación de horas
   (`fill_missing_hours_or_continue`). Si la recuperación falla, la consulta sigue con los datos
   guardados y la hora que falte sale `sin_datos` (decisión de Nicolás, 23/11/2026).
2. `list_household_zones` → zonas que cuentan (`zone_rules.counts_for_total`: zona `activa` con
   sensor `activo`; solo ellas suman al total) y, en el detalle, `_find_zone` (404).
3. `_read_series` de las zonas que cuentan en el rango que decide el caso de uso (consumo:
   `reference_window_start(hour_start, window_days)` .. `hour_start`; historial:
   `rng.read_start` .. `rng.end − 1 h`, porque la lectura es inclusiva en ambos extremos).
4. Preferencias, meta y tarifa según haga falta → dominio (`app.domain.states` o
   `app.domain.history`) → esquema.

Costo = kWh × `precio_kwh` de la tarifa vigente en la fecha (Bogotá) de la hora evaluada
(RN-V-01), sin cargo fijo (RN-V-02); sin tarifa o sin kWh, `costo_cop` es null (RN-XI-08), y el
del acumulado también cuando el acumulado está `sin_datos` (null = sin dato, nunca cero). El
nombre de cada zona es el visible de su tipo (RN-XII-03). Solo lectura: no hace commit (la
recuperación termina su propia transacción antes). Los números salen sin redondear (DC-11).

Historial: cada fecha del periodo se cobra con la tarifa vigente en esa fecha (RN-V-01,
RN-XIII-05); el cargo fijo solo entra en la proyección de Mes con filtro General (RN-V-02,
DC-30); `tarifa_vigente` indica si hay tarifa hoy.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlmodel import Session

from app.data import goals as goals_data
from app.data import households as households_data
from app.data import tariffs as tariffs_data
from app.data import users as users_data
from app.data.households import ZoneRow
from app.domain import history, states
from app.domain.formats import zone_name
from app.domain.simulator import TIMEZONE
from app.errors import NOT_FOUND_MESSAGE, ApiError, CodigoError, NotImplementedOperation
from app.schemas.common import IntervaloHora
from app.schemas.consumption import (
    ConsumoActualHogar,
    ConsumoActualHogarActual,
    ConsumoActualHogarAcumuladoHoy,
    ConsumoZonaDetalle,
    ConsumoZonaDetalleEstadoConsumo,
    ConsumoZonaDetalleParticipacion,
    ConsumoZonaItem,
    ConsumoZonas,
    FuentesDatos,
    Historial,
    HistorialComparacion,
    HistorialCosto,
    HistorialParticipacionZona,
    HistorialUltimoPico,
    PuntoSerie,
    PuntoSerieZona,
)
from app.schemas.households import Zona
from app.services import hour_recovery
from app.services._readings import counting_zones as _counting_zones
from app.services._readings import read_series as _read_series
from app.services.thresholds import get_thresholds

ONE_HOUR = timedelta(hours=1)

__all__ = [
    "get_current_consumption",
    "get_data_sources",
    "get_history",
    "get_thresholds",
    "get_zone_consumption",
    "get_zones_consumption",
]


# ------------------------------------------------------------------ casos de uso
def get_current_consumption(
    session: Session, user_id: UUID, hogar_id: UUID, now: datetime | None = None
) -> ConsumoActualHogar:
    """`obtenerConsumoActual`: Cards del Panel principal (RN-XI-01, RN-XI-03, RN-XI-04, RN-XI-08).

    La meta se aplica solo si el usuario eligió `base_comparacion = meta` y el hogar tiene una
    meta activa; si no (o sin preferencias guardadas), la referencia es el promedio.
    """
    moment = _recover(session, hogar_id, now)
    hour_start, hour_end = states.evaluated_hour(moment)
    thresholds = get_thresholds()
    counting = _counting_zones(households_data.list_household_zones(session, hogar_id))
    series = _read_series(
        session,
        hogar_id,
        [zone.id for zone in counting],
        states.reference_window_start(hour_start, thresholds.window_days),
        hour_start,
    )
    goal = _applied_goal(session, user_id, hogar_id)
    price = _price_for_hour(session, hogar_id, hour_start)

    current = states.evaluate_current(series, hour_start, goal, thresholds)
    today = states.evaluate_today(series, moment, goal, thresholds)
    today_cost = None if today.state == "sin_datos" else states.cost(today.energy_kwh, price)
    return ConsumoActualHogar(
        hora=IntervaloHora(inicio=hour_start, fin=hour_end),
        tarifa_vigente=price is not None,
        actual=ConsumoActualHogarActual(
            potencia_kw=current.power_kw,
            costo_cop=states.cost(current.power_kw, price),
            variacion_hora_anterior_pct=current.variation_pct,
            referencia_tipo=current.reference_type,
            referencia_kw=current.reference_kw,
            estado=current.state,
            mensaje_codigo=current.message_code,
        ),
        acumulado_hoy=ConsumoActualHogarAcumuladoHoy(
            energia_kwh=today.energy_kwh,
            costo_cop=today_cost,
            referencia_tipo=today.reference_type,
            referencia_kwh=today.reference_kwh,
            muestra_limite=today.shows_limit,
            estado=today.state,
            mensaje_codigo=today.message_code,
        ),
    )


def get_zones_consumption(
    session: Session, user_id: UUID, hogar_id: UUID, now: datetime | None = None
) -> ConsumoZonas:
    """`obtenerConsumoZonas`: Participación y estado de cada zona en la última hora completa (RN-XI-05, RN-XII-05, RN-XII-06).

    Lista solo las zonas que cuentan, en orden alfabético por nombre visible (RN-XII-03).
    """
    moment = _recover(session, hogar_id, now)
    hour_start, hour_end = states.evaluated_hour(moment)
    thresholds = get_thresholds()
    counting = _counting_zones(households_data.list_household_zones(session, hogar_id))
    counting_ids = [zone.id for zone in counting]
    series = _read_series(
        session,
        hogar_id,
        counting_ids,
        states.reference_window_start(hour_start, thresholds.window_days),
        hour_start,
    )
    price = _price_for_hour(session, hogar_id, hour_start)

    evaluation = states.evaluate_zones(series, counting_ids, hour_start, thresholds)
    items = []
    for zone in sorted(counting, key=_alphabetical):
        result = evaluation.zones[zone.id]
        items.append(
            ConsumoZonaItem(
                zona_id=zone.id,
                tipo=zone.tipo,
                nombre=zone_name(zone.tipo),
                potencia_kw=result.power_kw,
                costo_cop=states.cost(result.power_kw, price),
                participacion_pct=result.share_pct,
                estado_participacion=result.share_state,
            )
        )
    return ConsumoZonas(
        hora=IntervaloHora(inicio=hour_start, fin=hour_end),
        tarifa_vigente=price is not None,
        total_kw=evaluation.total_kw,
        zonas=items,
    )


def get_zone_consumption(
    session: Session, user_id: UUID, hogar_id: UUID, zona_id: UUID, now: datetime | None = None
) -> ConsumoZonaDetalle:
    """`obtenerConsumoZona`: Zona individual (RN-XI-05, RN-XI-06, RN-XII-07).

    404 NO_ENCONTRADO si la zona no es del hogar (antes de leer lecturas). Una zona del hogar que
    no cuenta (inactiva, con el sensor pausado o sin sensor) responde 200 con todo null y estados
    `sin_datos`: no se leen sus lecturas y el dominio no la evalúa.
    """
    moment = _recover(session, hogar_id, now)
    hour_start, hour_end = states.evaluated_hour(moment)
    thresholds = get_thresholds()
    zones = households_data.list_household_zones(session, hogar_id)
    zone = _find_zone(zones, zona_id)
    counting_ids = [row.id for row in _counting_zones(zones)]
    series = _read_series(
        session,
        hogar_id,
        counting_ids,
        states.reference_window_start(hour_start, thresholds.window_days),
        hour_start,
    )
    series.setdefault(zona_id, {})  # zona que no cuenta: sin lecturas; el dominio da sin_datos
    price = _price_for_hour(session, hogar_id, hour_start)

    evaluation = states.evaluate_zones(series, counting_ids, hour_start, thresholds)
    result = evaluation.zones[zona_id]
    return ConsumoZonaDetalle(
        zona=Zona(id=zone.id, tipo=zone.tipo, nombre=zone_name(zone.tipo), estado=zone.estado),
        hora=IntervaloHora(inicio=hour_start, fin=hour_end),
        tarifa_vigente=price is not None,
        potencia_kw=result.power_kw,
        costo_cop=states.cost(result.power_kw, price),
        estado_consumo=ConsumoZonaDetalleEstadoConsumo(
            promedio_misma_hora_kw=result.average_kw,
            variacion_pct=result.variation_pct,
            estado=result.zone_state,
            mensaje_codigo=result.zone_message_code,
        ),
        participacion=ConsumoZonaDetalleParticipacion(
            participacion_pct=result.share_pct,
            total_hogar_kw=evaluation.total_kw,
            estado=result.share_state,
        ),
    )


def get_history(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    periodo: history.Period,
    zona_id: UUID | None,
    now: datetime | None = None,
) -> Historial:
    """`obtenerHistorial`: Historial por periodo, General o de una zona (RN-XIII-01 a RN-XIII-06).

    Recupera primero las horas faltantes (RN-IV-05, DC-34; si falla, sigue con lo guardado). Con
    `zona_id`: 404 NO_ENCONTRADO si la zona no es del hogar (antes de leer lecturas); una zona
    del hogar que no cuenta responde todo sin dato, sin leer sus lecturas. General: las zonas que
    cuentan, en orden alfabético por nombre visible (RN-XII-03); ese orden es el de
    `participacion_zonas` y el de `zonas` en cada punto. Con filtro, ambos son null. Periodos,
    tramo anterior (DC-29), pico (DC-31), costo y proyección (DC-30) los calcula
    `app.domain.history.evaluate_history`.
    """
    moment = _recover(session, hogar_id, now)
    thresholds = get_thresholds()
    zones = households_data.list_household_zones(session, hogar_id)
    if zona_id is not None:
        _find_zone(zones, zona_id)
    rng = history.period_range(periodo, moment, thresholds.window_days)
    counting = _counting_zones(zones)
    if zona_id is None:
        selected = sorted(counting, key=_alphabetical)
    else:
        selected = [zone for zone in counting if zone.id == zona_id]
    series = _read_series(
        session, hogar_id, [zone.id for zone in selected], rng.read_start, rng.end - ONE_HOUR
    )
    if zona_id is not None:
        series.setdefault(zona_id, {})  # zona que no cuenta: sin lecturas → todo sin dato
    first_day = rng.start.astimezone(TIMEZONE).date()
    tariffs = tariffs_data.list_tariffs_between(session, hogar_id, first_day, rng.today)
    periods = [
        history.TariffPeriod(
            t.precio_kwh, t.cargo_fijo_mensual, t.vigente_desde, t.vigente_hasta
        )
        for t in tariffs
    ]

    evaluation = history.evaluate_history(
        series,
        periodo,
        moment,
        thresholds,
        history.tariffs_by_date(periods, first_day, rng.today),
        general=zona_id is None,
    )
    return _to_history(evaluation, zona_id, {zone.id: zone.tipo for zone in counting})


def get_data_sources(user_id: UUID, hogar_id: UUID) -> FuentesDatos:
    """`obtenerFuentesDatos`: Fuente principal y sensores, solo lectura (RN-III-03, RN-XVI-06). TODO(obtenerFuentesDatos)."""
    raise NotImplementedOperation("obtenerFuentesDatos")


# ------------------------------------------------------------------ pasos de lectura
def _recover(session: Session, hogar_id: UUID, now: datetime | None) -> datetime:
    """Instante único de la consulta y recuperación de las horas faltantes (RN-IV-05, DC-34).

    Si la recuperación falla, sigue con los datos guardados (`fill_missing_hours_or_continue`).
    `now` sin zona horaria: `ValueError` antes de tocar la base.
    """
    moment = now if now is not None else datetime.now(UTC)
    hour_recovery.fill_missing_hours_or_continue(session, hogar_id, moment)
    return moment


def _find_zone(zones: Iterable[ZoneRow], zona_id: UUID) -> ZoneRow:
    """La zona `zona_id` entre las del hogar; 404 NO_ENCONTRADO si no es del hogar."""
    for zone in zones:
        if zone.id == zona_id:
            return zone
    raise ApiError(404, CodigoError.NO_ENCONTRADO, NOT_FOUND_MESSAGE)


def _alphabetical(zone: ZoneRow) -> tuple[str, str]:
    """Orden por nombre visible (RN-XII-03) y, a igual nombre, por id."""
    return zone_name(zone.tipo), str(zone.id)


def _applied_goal(session: Session, user_id: UUID, hogar_id: UUID) -> states.GoalInput | None:
    """Meta aplicada: solo con `base_comparacion = meta` y una meta activa (RN-XI-03, RN-V-03)."""
    preferences = users_data.get_preferences(session, user_id)
    if preferences is None or preferences.base_comparacion != "meta":
        return None
    goal = goals_data.get_active_goal(session, hogar_id)
    return None if goal is None else states.GoalInput(monthly_kwh=goal.valor_kwh_mensual)


def _price_for_hour(session: Session, hogar_id: UUID, hour_start: datetime) -> float | None:
    """Precio por kWh vigente en la fecha (Bogotá) de la hora evaluada (RN-V-01, RN-XI-08, DC-39)."""
    day: date = hour_start.astimezone(TIMEZONE).date()
    tariff = tariffs_data.get_current_tariff(session, hogar_id, day)
    return None if tariff is None else tariff.precio_kwh


def _to_history(
    evaluation: history.HistoryEvaluation, zona_id: UUID | None, zone_types: dict[UUID, str]
) -> Historial:
    """Evaluación del dominio → esquema `Historial` del contrato (nombre visible, RN-XII-03)."""
    rng = evaluation.bounds
    shares = None
    if evaluation.zone_shares is not None:
        shares = [
            HistorialParticipacionZona(
                zona_id=share.zona_id,
                nombre=zone_name(zone_types[share.zona_id]),
                energia_kwh=share.energy_kwh,
                participacion_pct=share.share_pct,
            )
            for share in evaluation.zone_shares
        ]
    peak, comparison, cost = evaluation.last_peak, evaluation.comparison, evaluation.cost
    last_peak = None
    if peak is not None:
        last_peak = HistorialUltimoPico(
            inicio=peak.start,
            fin=peak.end,
            energia_kwh=peak.energy_kwh,
            promedio_historico_kwh=peak.average_kwh,
            exceso_pct=peak.excess_pct,
            estado=peak.state,
        )
    return Historial(
        periodo=rng.period,
        zona_id=zona_id,
        inicio=rng.start,
        fin=rng.end,
        granularidad=rng.granularity,
        tarifa_vigente=evaluation.has_tariff,
        total_kwh=evaluation.total_kwh,
        serie=[_to_point(point) for point in evaluation.series],
        participacion_zonas=shares,
        ultimo_pico=last_peak,
        comparacion=HistorialComparacion(
            actual_kwh=comparison.current_kwh,
            anterior_kwh=comparison.previous_kwh,
            variacion_pct=comparison.variation_pct,
            estado=comparison.state,
            mensaje_codigo=comparison.message_code,
        ),
        costo=HistorialCosto(
            costo_cop=cost.cost_cop,
            proyeccion_cierre_cop=cost.projection_cop,
            incluye_cargo_fijo=cost.includes_fixed_charge,
            estado=cost.state,
            mensaje_codigo=cost.message_code,
        ),
    )


def _to_point(point: history.SeriesPoint) -> PuntoSerie:
    """Punto de la serie; `zonas` en el orden de `participacion_zonas` (null con filtro)."""
    zones = None
    if point.zones is not None:
        zones = [
            PuntoSerieZona(zona_id=zone.zona_id, energia_kwh=zone.energy_kwh)
            for zone in point.zones
        ]
    return PuntoSerie(
        inicio=point.start,
        fin=point.end,
        energia_kwh=point.energy_kwh,
        costo_cop=point.cost_cop,
        es_pico_maximo=point.is_max_peak,
        zonas=zones,
    )
