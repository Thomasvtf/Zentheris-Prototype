"""Pruebas de app.data.tariffs sin base real (RN-V-01, RN-V-02, RN-XI-08, DC-39, R-01).

Valores de ejemplo de la pantalla de tarifa (reglas §6.15): 892 COP/kWh, cargo fijo 12.000 y
vigencia desde el 1 de septiembre de 2026. Que la restricción de exclusión impida solapes de
verdad necesita Postgres (tests/integrity/test_i02_overlapping_tariffs.py); aquí se comprueba
la sentencia y el mapeo.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.data import tariffs
from app.data.tariffs import TariffRow, get_current_tariff
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
