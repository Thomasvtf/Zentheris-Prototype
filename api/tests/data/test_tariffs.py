"""Pruebas de app.data.tariffs sin base real (RN-V-01, RN-V-02, RN-XI-08, DC-39, R-01).

Valores de ejemplo de la pantalla de tarifa (reglas §6.15): 892 COP/kWh, cargo fijo 12.000 y
vigencia desde el 1 de septiembre de 2026. Que la restricción de exclusión impida solapes de
verdad necesita Postgres (tests/integrity/test_i02_overlapping_tariffs.py); aquí se comprueba
la sentencia y el mapeo.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.data import tariffs
from app.data.tariffs import TariffRow, get_current_tariff, list_tariffs_between
from tests.data.fake_session import FakeSession, assert_bound_only, normalized_sql

TODAY = date(2026, 11, 23)
SEPTEMBER_1 = date(2026, 9, 1)


def _tariff_row(**overrides: Any) -> dict[str, Any]:
    """Fila como la entregaría psycopg2: numeric como Decimal y date como date."""
    row: dict[str, Any] = {
        "id": uuid4(),
        "precio_kwh": Decimal("892.00"),
        "cargo_fijo_mensual": Decimal("12000.00"),
        "vigente_desde": SEPTEMBER_1,
        "vigente_hasta": None,
    }
    row.update(overrides)
    return row


def test_current_tariff_sends_household_and_date_as_parameters() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert get_current_tariff(session, hogar_id, TODAY) is None  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is tariffs.CURRENT_TARIFF_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id, "today": TODAY}
    assert_bound_only(statement, params)


def test_current_tariff_sql_is_half_open_and_filtered_by_household() -> None:
    """DC-39: vigencia [desde, hasta), la misma de la restricción de exclusión."""
    assert normalized_sql(tariffs.CURRENT_TARIFF_SQL) == (
        "select id, precio_kwh, cargo_fijo_mensual, vigente_desde, vigente_hasta "
        "from tarifas_hogar "
        "where hogar_id = :hogar_id "
        "and vigente_desde <= :today "
        "and (vigente_hasta is null or vigente_hasta > :today)"
    )


def test_current_tariff_maps_numeric_to_float_and_id_to_uuid() -> None:
    tariff_id = uuid4()
    session = FakeSession([_tariff_row(id=str(tariff_id))])

    tariff = get_current_tariff(session, uuid4(), TODAY)  # type: ignore[arg-type]

    assert tariff == TariffRow(
        id=tariff_id,
        precio_kwh=892.0,
        cargo_fijo_mensual=12000.0,
        vigente_desde=SEPTEMBER_1,
        vigente_hasta=None,
    )
    assert isinstance(tariff.id, UUID)
    assert type(tariff.precio_kwh) is float
    assert type(tariff.cargo_fijo_mensual) is float


def test_current_tariff_without_fixed_charge_keeps_none() -> None:
    """RN-V-02: el cargo fijo es opcional; NULL es «sin dato», nunca cero."""
    session = FakeSession([_tariff_row(cargo_fijo_mensual=None)])

    tariff = get_current_tariff(session, uuid4(), TODAY)  # type: ignore[arg-type]

    assert tariff is not None
    assert tariff.cargo_fijo_mensual is None


def test_current_tariff_keeps_a_closed_validity() -> None:
    session = FakeSession([_tariff_row(vigente_hasta=date(2026, 12, 1))])

    tariff = get_current_tariff(session, uuid4(), TODAY)  # type: ignore[arg-type]

    assert tariff is not None
    assert tariff.vigente_hasta == date(2026, 12, 1)


def test_no_current_tariff_returns_none() -> None:
    """RN-XI-08: sin tarifa vigente el servicio responde tarifa_vigente = false."""
    session = FakeSession([])

    assert get_current_tariff(session, uuid4(), TODAY) is None  # type: ignore[arg-type]


def test_current_tariff_rejects_a_datetime_without_sql() -> None:
    """La fecha de Bogotá la calcula el servicio; un instante no es una fecha."""
    session = FakeSession()
    moment = datetime(2026, 11, 23, tzinfo=UTC)

    with pytest.raises(TypeError, match="date"):
        get_current_tariff(session, uuid4(), moment)  # type: ignore[arg-type]

    assert session.calls == []


def test_current_tariff_does_not_commit_and_has_no_python_formatting() -> None:
    session = FakeSession([_tariff_row()])

    get_current_tariff(session, uuid4(), TODAY)  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(tariffs.CURRENT_TARIFF_SQL)
    assert "{" not in sql
    assert "%" not in sql


# --- list_tariffs_between (obtenerHistorial: el costo de cada fecha usa su tarifa) ---------

NOVEMBER_1 = date(2026, 11, 1)
DECEMBER_1 = date(2026, 12, 1)


def test_tariffs_between_sends_household_and_dates_as_parameters() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert list_tariffs_between(session, hogar_id, NOVEMBER_1, TODAY) == []  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is tariffs.TARIFFS_BETWEEN_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id, "start": NOVEMBER_1, "end": TODAY}
    assert_bound_only(statement, params)


def test_tariffs_between_sql_is_filtered_by_household_half_open_and_ordered() -> None:
    """R-01 y DC-39: solo el hogar pedido; vigencia [desde, hasta) contra [start, end]."""
    assert normalized_sql(tariffs.TARIFFS_BETWEEN_SQL) == (
        "select id, precio_kwh, cargo_fijo_mensual, vigente_desde, vigente_hasta "
        "from tarifas_hogar "
        "where hogar_id = :hogar_id "
        "and vigente_desde <= :end "
        "and (vigente_hasta is null or vigente_hasta > :start) "
        "order by vigente_desde"
    )


def _sql_predicate(desde: date, hasta: date | None, start: date, end: date) -> bool:
    """El WHERE de TARIFFS_BETWEEN_SQL (sin el hogar), escrito en Python."""
    return desde <= end and (hasta is None or hasta > start)


def _touches_some_date(desde: date, hasta: date | None, start: date, end: date) -> bool:
    """La definición: alguna fecha d de [start, end] cumple desde <= d < hasta (DC-39)."""
    days = (end - start).days + 1
    return any(
        desde <= day and (hasta is None or day < hasta)
        for day in (start + timedelta(days=offset) for offset in range(days))
    )


@pytest.mark.parametrize(
    ("desde", "hasta", "start", "end", "expected"),
    [
        # vigente_hasta es exclusivo: la que termina justo en start no cubre start.
        (SEPTEMBER_1, NOVEMBER_1, NOVEMBER_1, TODAY, False),
        (SEPTEMBER_1, date(2026, 11, 2), NOVEMBER_1, TODAY, True),
        # end es inclusivo: la que empieza justo en end cubre end; un día después, no.
        (TODAY, None, NOVEMBER_1, TODAY, True),
        (TODAY + timedelta(days=1), None, NOVEMBER_1, TODAY, False),
        # start es inclusivo: la que empieza en start lo cubre.
        (NOVEMBER_1, DECEMBER_1, NOVEMBER_1, TODAY, True),
        # vigencia abierta (vigente_hasta NULL) que empezó antes.
        (SEPTEMBER_1, None, NOVEMBER_1, TODAY, True),
        # vigencia cerrada dentro del rango y otra que lo cubre entero.
        (date(2026, 11, 10), date(2026, 11, 15), NOVEMBER_1, TODAY, True),
        (SEPTEMBER_1, DECEMBER_1, NOVEMBER_1, TODAY, True),
        # terminada mucho antes.
        (SEPTEMBER_1, date(2026, 10, 1), NOVEMBER_1, TODAY, False),
        # rango de un solo día (periodo «dia»): [TODAY, TODAY].
        (TODAY, date(2026, 11, 24), TODAY, TODAY, True),
        (date(2026, 11, 22), TODAY, TODAY, TODAY, False),
        (date(2026, 11, 24), None, TODAY, TODAY, False),
    ],
)
def test_tariffs_between_predicate_matches_inclusive_range_and_half_open_validity(
    desde: date, hasta: date | None, start: date, end: date, expected: bool
) -> None:
    """El WHERE equivale a «la vigencia toca alguna fecha de [start, end]» en los límites."""
    assert _touches_some_date(desde, hasta, start, end) is expected
    assert _sql_predicate(desde, hasta, start, end) is expected


def test_tariffs_between_maps_every_row_in_order() -> None:
    """Dos vigencias contiguas (la cerrada y la abierta) llegan en el orden de la sentencia."""
    old_id, new_id = uuid4(), uuid4()
    session = FakeSession(
        [
            _tariff_row(id=str(old_id), vigente_hasta=date(2026, 11, 15)),
            _tariff_row(
                id=new_id,
                precio_kwh=Decimal("905.50"),
                cargo_fijo_mensual=None,
                vigente_desde=date(2026, 11, 15),
            ),
        ]
    )

    rows = list_tariffs_between(session, uuid4(), NOVEMBER_1, TODAY)  # type: ignore[arg-type]

    assert rows == [
        TariffRow(
            id=old_id,
            precio_kwh=892.0,
            cargo_fijo_mensual=12000.0,
            vigente_desde=SEPTEMBER_1,
            vigente_hasta=date(2026, 11, 15),
        ),
        TariffRow(
            id=new_id,
            precio_kwh=905.5,
            cargo_fijo_mensual=None,
            vigente_desde=date(2026, 11, 15),
            vigente_hasta=None,
        ),
    ]
    assert all(isinstance(row.id, UUID) for row in rows)
    assert all(type(row.precio_kwh) is float for row in rows)
    assert type(rows[0].cargo_fijo_mensual) is float
    assert rows[1].cargo_fijo_mensual is None  # RN-V-02: sin dato, nunca cero


def test_tariffs_between_accepts_a_single_day() -> None:
    """Periodo «dia»: start == end es válido (no es start > end)."""
    hogar_id = uuid4()
    session = FakeSession([_tariff_row()])

    rows = list_tariffs_between(session, hogar_id, TODAY, TODAY)  # type: ignore[arg-type]

    assert len(rows) == 1
    assert session.calls[0][1] == {"hogar_id": hogar_id, "start": TODAY, "end": TODAY}


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 11, 1, tzinfo=UTC), TODAY),
        (NOVEMBER_1, datetime(2026, 11, 23, tzinfo=UTC)),
        (datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC)),
    ],
)
def test_tariffs_between_rejects_datetimes_without_sql(start: date, end: date) -> None:
    session = FakeSession()

    with pytest.raises(TypeError, match="date"):
        list_tariffs_between(session, uuid4(), start, end)  # type: ignore[arg-type]

    assert session.calls == []


def test_tariffs_between_rejects_start_after_end_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(ValueError, match="posterior"):
        list_tariffs_between(session, uuid4(), TODAY, NOVEMBER_1)  # type: ignore[arg-type]

    assert session.calls == []


def test_tariffs_between_does_not_commit_and_has_no_python_formatting() -> None:
    session = FakeSession([_tariff_row()])

    list_tariffs_between(session, uuid4(), NOVEMBER_1, TODAY)  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(tariffs.TARIFFS_BETWEEN_SQL)
    assert "{" not in sql
    assert "%" not in sql
