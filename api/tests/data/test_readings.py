"""Pruebas de app.data.readings sin base real (RN-IV-01, RN-IV-05, RN-X-03, DC-33, B-01).

El consumo de cada fila es el promedio horario real de la personalidad (tests/helpers). Que
Postgres rechace de verdad los duplicados necesita base: aquí se comprueba la sentencia.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import psycopg2.extensions
import pytest
from sqlalchemy.dialects.postgresql import psycopg2 as psycopg2_dialect
from sqlalchemy.sql.elements import TextClause

from app.data import readings
from app.data.readings import insert_readings_batch
from tests.data.fake_session import FakeResult, FakeSession, assert_bound_only, normalized_sql
from tests.helpers.personalities import ZONE_KEYS, load_personalities

BOGOTA = ZoneInfo("America/Bogota")
BACKFILL_HOURS = 720  # 30 días (RN-IV-01)
FIRST_HOUR = datetime(2026, 10, 1, 0, 0, tzinfo=BOGOTA)
PARAM_NAMES = {"sensor_ids", "fechas_hora", "consumos_kwh", "calidades"}


def _readings(zones: tuple[str, ...], hours: int = BACKFILL_HOURS) -> list[dict[str, Any]]:
    """Lecturas de *Consumo amplio* (contempla las 9 zonas) con 4 decimales, como la tabla."""
    personality = load_personalities()["Consumo amplio"]
    rows = []
    for zone in zones:
        sensor_id = uuid4()
        for offset in range(hours):
            moment = FIRST_HOUR + timedelta(hours=offset)
            kwh = personality.zone_kwh_for_hour(zone, moment.hour)
            rows.append(
                {
                    "sensor_id": sensor_id,
                    "fecha_hora": moment,
                    "consumo_kwh": Decimal(str(kwh)).quantize(Decimal("0.0001")),
                    "calidad": "simulada",
                }
            )
    return rows


def test_b01_nine_zones_go_in_a_single_statement() -> None:
    """B-01, DC-33: dúplex de 9 zonas × 720 h = 6.480 filas en UNA sentencia."""
    rows = _readings(ZONE_KEYS)
    assert len(rows) == 6480
    session = FakeSession(FakeResult(rowcount=6480))

    assert insert_readings_batch(session, rows) == 6480  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert isinstance(params, dict)  # un dict: una lista de dicts sería executemany
    assert {name: len(values) for name, values in params.items()} == dict.fromkeys(
        PARAM_NAMES, 6480
    )
    assert len(set(zip(params["sensor_ids"], params["fechas_hora"], strict=True))) == 6480
    assert set(params["calidades"]) == {"simulada"}


def test_sql_inserts_from_unnest_and_ignores_duplicates() -> None:
    """RN-IV-05: ON CONFLICT (sensor_id, fecha_hora) DO NOTHING."""
    session = FakeSession(FakeResult(rowcount=24))

    insert_readings_batch(session, _readings(("cocina",), hours=24))  # type: ignore[arg-type]

    assert normalized_sql(session.calls[0][0]) == (
        "insert into lecturas (sensor_id, fecha_hora, consumo_kwh, calidad) "
        "select l.sensor_id, l.fecha_hora, l.consumo_kwh, l.calidad "
        "from unnest( cast(:sensor_ids as uuid[]), cast(:fechas_hora as timestamptz[]), "
        "cast(:consumos_kwh as numeric[]), cast(:calidades as text[]) "
        ") as l (sensor_id, fecha_hora, consumo_kwh, calidad) "
        "on conflict (sensor_id, fecha_hora) do nothing"
    )


def test_values_travel_only_as_aligned_parameters() -> None:
    rows = _readings(("cocina", "sala"), hours=24)
    session = FakeSession(FakeResult(rowcount=48))

    insert_readings_batch(session, rows)  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params is not None
    assert_bound_only(statement, params)
    assert params["sensor_ids"] == [str(row["sensor_id"]) for row in rows]
    assert params["fechas_hora"] == [row["fecha_hora"] for row in rows]
    assert params["consumos_kwh"] == [row["consumo_kwh"] for row in rows]
    assert params["calidades"] == [row["calidad"] for row in rows]


def test_parameters_are_adapted_by_psycopg2_to_arrays() -> None:
    """psycopg2 convierte cada lista en ARRAY[...]: la sentencia no necesita execute_values."""
    session = FakeSession(FakeResult(rowcount=24))

    insert_readings_batch(session, _readings(("cocina",), hours=24))  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params is not None
    compiled = statement.compile(dialect=psycopg2_dialect.dialect())
    assert set(compiled.params) == PARAM_NAMES
    for values in params.values():
        assert psycopg2.extensions.adapt(values).getquoted().startswith(b"ARRAY[")


def test_returns_only_the_inserted_rows() -> None:
    """Si ya existían lecturas, el conteo es el de las filas realmente guardadas."""
    session = FakeSession(FakeResult(rowcount=20))
    rows = _readings(("sala",), hours=24)

    result = insert_readings_batch(session, rows)  # type: ignore[arg-type]

    assert result == 20
    assert type(result) is int


def test_empty_batch_returns_zero_without_sql() -> None:
    session = FakeSession()

    assert insert_readings_batch(session, []) == 0  # type: ignore[arg-type]
    assert session.calls == []


def test_naive_timestamp_is_rejected_before_sql() -> None:
    """Sin zona horaria, Postgres usaría la de su sesión y correría las horas."""
    rows = _readings(("sala",), hours=2)
    rows[1]["fecha_hora"] = rows[1]["fecha_hora"].replace(tzinfo=None)
    session = FakeSession()

    with pytest.raises(ValueError, match="zona horaria"):
        insert_readings_batch(session, rows)  # type: ignore[arg-type]

    assert session.calls == []


def test_accepts_sensor_ids_as_text() -> None:
    rows = _readings(("sala",), hours=1)
    sensor_id: UUID = rows[0]["sensor_id"]
    rows[0]["sensor_id"] = str(sensor_id)
    session = FakeSession(FakeResult(rowcount=1))

    insert_readings_batch(session, rows)  # type: ignore[arg-type]

    params = session.calls[0][1]
    assert params is not None
    assert params["sensor_ids"] == [str(sensor_id)]


def test_does_not_commit_and_statement_has_no_python_formatting() -> None:
    session = FakeSession(FakeResult(rowcount=24))

    insert_readings_batch(session, _readings(("sala",), hours=24))  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(readings.INSERT_READINGS_BATCH_SQL)
    assert "{" not in sql
    assert "%" not in sql
