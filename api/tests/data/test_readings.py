"""Pruebas de app.data.readings sin base real (RN-IV-01, RN-IV-05, RN-X-03, DC-33, B-01).

El consumo de cada fila es el promedio horario real de la personalidad (tests/helpers). Que
Postgres rechace de verdad los duplicados necesita base: aquí se comprueba la sentencia.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import psycopg2.extensions
import pytest
from sqlalchemy.dialects.postgresql import psycopg2 as psycopg2_dialect
from sqlalchemy.sql.elements import TextClause

from app.data import readings
from app.data.readings import (
    SensorGapRow,
    get_sensor_gaps,
    insert_readings_batch,
    lock_household_recovery,
)
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


# --- Fase 5: huecos por sensor para recuperar horas (RN-IV-05, DC-34, R-01) ------------------

UNTIL = FIRST_HOUR + timedelta(hours=10)


def _gap_row(**overrides: Any) -> dict[str, Any]:
    """Fila como la entregaría psycopg2: timestamptz[] como lista de datetime con zona."""
    row: dict[str, Any] = {
        "sensor_id": uuid4(),
        "zona_tipo": "cocina",
        "first_hour": FIRST_HOUR,
        "missing_hours": [FIRST_HOUR + timedelta(hours=3), FIRST_HOUR + timedelta(hours=4)],
    }
    row.update(overrides)
    return row


def test_gaps_query_sends_household_and_end_hour_as_parameters() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert get_sensor_gaps(session, hogar_id, UNTIL) == []  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is readings.SENSOR_GAPS_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id, "until": UNTIL}
    assert_bound_only(statement, params)
    compiled = statement.compile(dialect=psycopg2_dialect.dialect())
    assert set(compiled.params) == {"hogar_id", "until"}


def test_gaps_query_filters_by_household_and_active_states() -> None:
    """R-01: solo zonas del hogar; solo sensores 'activo' de zonas 'activa' (RN-IV-07)."""
    sql = normalized_sql(readings.SENSOR_GAPS_SQL)
    where = sql.rsplit(" where ", 1)[1]

    assert "from sensores_zona s join zonas z on z.id = s.zona_id" in sql
    assert "z.hogar_id = :hogar_id" in where
    assert "z.estado = 'activa'" in where
    assert "s.estado = 'activo'" in where
    assert sql.endswith("order by z.tipo, s.id")


def test_gaps_query_reads_min_max_and_count_through_the_unique_index() -> None:
    sql = normalized_sql(readings.SENSOR_GAPS_SQL)

    assert (
        "select min(l.fecha_hora) as first_hour, max(l.fecha_hora) as last_hour, "
        "count(*) as stored_hours from lecturas l where l.sensor_id = s.id"
    ) in sql


def test_gaps_query_has_both_series_start_branches() -> None:
    """Sin huecos internos empieza en max + 1 h (solo horas nuevas); con huecos, en min (A13)."""
    sql = normalized_sql(readings.SENSOR_GAPS_SQL)

    assert (
        "generate_series( case "
        "when st.stored_hours = extract(epoch from st.last_hour - st.first_hour) / 3600 + 1 "
        "then st.last_hour + interval '1 hour' "
        "else st.first_hour "
        "end, cast(:until as timestamptz), interval '1 hour' ) as h (missing_hour)"
    ) in sql


def test_gaps_query_is_an_anti_join_over_the_unique_index() -> None:
    sql = normalized_sql(readings.SENSOR_GAPS_SQL)

    assert (
        "where not exists ( select 1 from lecturas e "
        "where e.sensor_id = s.id and e.fecha_hora = h.missing_hour )"
    ) in sql
    assert "array_agg(h.missing_hour order by h.missing_hour) as missing_hours" in sql


def test_gaps_query_documents_the_pending_rule_for_paused_sensors() -> None:
    source = Path(readings.__file__).read_text(encoding="utf-8")
    comment = source.split("SENSOR_GAPS_SQL = text(")[0].rsplit("\n\n", 1)[1]

    assert "TODO(pendiente: ¿un sensor pausado o una zona inactiva generan lecturas?" in comment
    assert "huecos internos, A13" in comment


def test_gaps_rows_are_mapped_in_the_order_the_query_returns() -> None:
    rows = [
        _gap_row(zona_tipo="cocina"),
        _gap_row(zona_tipo="sala", missing_hours=[UNTIL]),
    ]
    session = FakeSession(rows)

    result = get_sensor_gaps(session, uuid4(), UNTIL)  # type: ignore[arg-type]

    assert result == [
        SensorGapRow(
            sensor_id=rows[0]["sensor_id"],
            zona_tipo="cocina",
            first_hour=FIRST_HOUR,
            missing_hours=[FIRST_HOUR + timedelta(hours=3), FIRST_HOUR + timedelta(hours=4)],
        ),
        SensorGapRow(
            sensor_id=rows[1]["sensor_id"],
            zona_tipo="sala",
            first_hour=FIRST_HOUR,
            missing_hours=[UNTIL],
        ),
    ]
    assert all(type(gap.missing_hours) is list for gap in result)


def test_sensor_without_readings_has_no_first_hour_and_no_gaps() -> None:
    """array_agg sin filas da NULL: se entrega lista vacía, nunca None."""
    session = FakeSession([_gap_row(first_hour=None, missing_hours=None)])

    (gap,) = get_sensor_gaps(session, uuid4(), UNTIL)  # type: ignore[arg-type]

    assert gap.first_hour is None
    assert gap.missing_hours == []


def test_complete_sensor_and_first_hour_after_end_give_empty_list() -> None:
    later = UNTIL + timedelta(hours=1)
    session = FakeSession(
        [
            _gap_row(missing_hours=None),
            _gap_row(zona_tipo="sala", first_hour=later, missing_hours=[]),
        ]
    )

    complete, future = get_sensor_gaps(session, uuid4(), UNTIL)  # type: ignore[arg-type]

    assert complete.first_hour == FIRST_HOUR
    assert complete.missing_hours == []
    assert future.first_hour == later
    assert future.missing_hours == []


def test_gaps_keep_the_hours_as_delivered_with_their_time_zone() -> None:
    """El SQL ya ordena y recorta en :until; Python no reordena ni filtra."""
    h1 = FIRST_HOUR + timedelta(hours=1)
    h3 = (FIRST_HOUR + timedelta(hours=3)).astimezone(UTC)
    session = FakeSession([_gap_row(missing_hours=(h1, h3))])

    (gap,) = get_sensor_gaps(session, uuid4(), UNTIL)  # type: ignore[arg-type]

    assert gap.missing_hours == [h1, h3]
    assert type(gap.missing_hours) is list
    assert all(hour.utcoffset() is not None for hour in gap.missing_hours)


def test_gaps_map_text_sensor_id_to_uuid() -> None:
    sensor_id = uuid4()
    session = FakeSession([_gap_row(sensor_id=str(sensor_id))])

    (gap,) = get_sensor_gaps(session, uuid4(), UNTIL)  # type: ignore[arg-type]

    assert gap.sensor_id == sensor_id
    assert isinstance(gap.sensor_id, UUID)


def test_gaps_reject_naive_end_hour_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(ValueError, match="zona horaria"):
        get_sensor_gaps(session, uuid4(), UNTIL.replace(tzinfo=None))  # type: ignore[arg-type]

    assert session.calls == []


def test_gaps_do_not_commit_and_statement_has_no_python_formatting() -> None:
    session = FakeSession([_gap_row()])

    get_sensor_gaps(session, uuid4(), UNTIL)  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(readings.SENSOR_GAPS_SQL)
    assert "{" not in sql
    assert "%" not in sql


# --- Fase 5: candado de recuperación por hogar (RN-IV-05, DC-34) -----------------------------


def test_recovery_lock_is_a_transaction_advisory_lock_on_the_household() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert lock_household_recovery(session, hogar_id) is None  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is readings.LOCK_HOUSEHOLD_RECOVERY_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "select pg_advisory_xact_lock(hashtextextended(cast(:hogar_id as text), 0))"
    )


def test_recovery_lock_is_released_by_the_transaction_not_a_row_lock() -> None:
    """Candado de transacción (se suelta en commit/rollback): ni de sesión ni FOR UPDATE."""
    sql = normalized_sql(readings.LOCK_HOUSEHOLD_RECOVERY_SQL)

    assert "pg_advisory_xact_lock" in sql
    assert "pg_advisory_lock(" not in sql
    assert "for update" not in sql
    assert "hogares" not in sql


def test_recovery_lock_does_not_commit() -> None:
    session = FakeSession()

    lock_household_recovery(session, uuid4())  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(readings.LOCK_HOUSEHOLD_RECOVERY_SQL)
    assert "{" not in sql
    assert "%" not in sql
