"""Lectura compartida de los servicios de consumo y de la evaluación de alertas en vivo.

- `counting_zones`: zonas que suman al total del hogar (RN-XI-01, RN-XI-05).
- `read_series`: lecturas horarias por zona en un rango cerrado.
- `ReadingsByZone`: `{zona: {inicio de hora: kWh}}`.

Módulo interno de `app.services` (no lo llaman los routers); lo usan `consumption`,
`goals_tariff` y `live_alerts`. No importa otros servicios: `hour_recovery` importa `live_alerts`, así que
importar aquí `hour_recovery` cerraría el ciclo `hour_recovery` → `live_alerts` → `_readings` →
`hour_recovery`. Por eso la recuperación previa a cada consulta (`_recover`, que llama a
`hour_recovery.fill_missing_hours_or_continue`) se queda en `consumption`, `alerts_tips` y
`goals_tariff`, cada uno con su reloj inyectable.
"""

from collections.abc import Iterable, Sequence
from datetime import datetime
from uuid import UUID

from sqlmodel import Session

from app.data import readings as readings_data
from app.data.households import ZoneRow
from app.domain.zone_rules import counts_for_total

ReadingsByZone = dict[UUID, dict[datetime, float]]


def counting_zones(zones: Iterable[ZoneRow]) -> list[ZoneRow]:
    """Zonas que suman al total del hogar (RN-XI-01, RN-XI-05)."""
    return [zone for zone in zones if counts_for_total(zone.estado, zone.sensor_estado)]


def read_series(
    session: Session, hogar_id: UUID, zone_ids: Sequence[UUID], start: datetime, end: datetime
) -> ReadingsByZone:
    """Lecturas de las zonas en [start, end] como `{zona: {inicio de hora: kWh}}`.

    Cada zona pedida aparece aunque no tenga lecturas (serie vacía: el dominio la trata como sin
    dato, nunca como cero). Dentro de la transacción de la recuperación incluye las lecturas
    recién insertadas.
    """
    series: ReadingsByZone = {zona_id: {} for zona_id in zone_ids}
    for row in readings_data.get_hourly_readings(session, hogar_id, zone_ids, start, end):
        if row.zona_id in series:
            series[row.zona_id][row.fecha_hora] = row.consumo_kwh
    return series
