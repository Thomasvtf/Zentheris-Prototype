"""Pruebas de app.data.simulation_profiles sin base real (RN-X-04, RN-IV-01, DC-37, DC-45).

Los perfiles salen del consolidado oficial (`docs/datos/perfiles`, SHA-256 comprobado): se
simula cómo los entrega Postgres (NUMERIC como Decimal, JSONB como dict o texto) y se exige
que `params` quede idéntico al archivo, porque cambiarlo cambia las lecturas (RN-IV-04).
"""

import json
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.data import simulation_profiles
from app.data.simulation_profiles import (
    JSON_FIELDS,
    NUMERIC_FIELDS,
    SimulationProfileRow,
    get_household_profile,
    get_profiles,
)
from tests.data.fake_session import FakeSession, assert_bound_only, normalized_sql
from tests.helpers.personalities import PERSONALITY_ORDER, PROFILES_PATH, load_personalities

PROFILE_FIELDS = {"nombre", "activo", *NUMERIC_FIELDS, *JSON_FIELDS}


@pytest.fixture(scope="module")
def profiles() -> dict[str, dict[str, Any]]:
    """Los 5 perfiles del consolidado; `load_personalities` comprueba antes el SHA-256."""
    load_personalities()
    items = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    return {item["nombre"]: item for item in items}


def _db_row(
    profile: dict[str, Any], *, json_as_text: bool = False, **overrides: Any
) -> dict[str, Any]:
    """La fila tal como la entregaría psycopg2: NUMERIC(…, 4) como Decimal."""
    row: dict[str, Any] = {
        "id": uuid4(),
        "nombre": profile["nombre"],
        "activo": profile["activo"],
    }
    for field in NUMERIC_FIELDS:
        row[field] = Decimal(str(profile[field])).quantize(Decimal("0.0001"))
    for field in JSON_FIELDS:
        row[field] = json.dumps(profile[field]) if json_as_text else profile[field]
    row.update(overrides)
    return row


def test_expected_fields_are_exactly_those_of_the_official_file(
    profiles: dict[str, dict[str, Any]],
) -> None:
    for profile in profiles.values():
        assert set(profile) == PROFILE_FIELDS


def test_queries_by_name_with_a_single_bound_statement() -> None:
    session = FakeSession()

    assert get_profiles(session, PERSONALITY_ORDER) == {}  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {"nombres": list(PERSONALITY_ORDER)}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql.endswith("from perfiles_simulacion where nombre = any(cast(:nombres as text[]))")
    selected = sql.removeprefix("select ").split(" from ")[0].split(", ")
    assert set(selected) == {"id", *PROFILE_FIELDS}
    assert len(selected) == len(PROFILE_FIELDS) + 1


def test_inactive_profiles_are_not_filtered_out(profiles: dict[str, dict[str, Any]]) -> None:
    """El respaldo de RN-X-04 lo decide el dominio: la consulta no filtra por `activo`."""
    session = FakeSession([_db_row(profiles["Consumo amplio"], activo=False)])

    result = get_profiles(session, ["Consumo amplio"])  # type: ignore[arg-type]

    assert result["Consumo amplio"].activo is False
    assert result["Consumo amplio"].params["activo"] is False
    assert "activo" not in normalized_sql(session.calls[0][0]).split(" where ")[1]


@pytest.mark.parametrize("json_as_text", [False, True])
def test_params_equal_the_official_file_for_the_five_personalities(
    profiles: dict[str, dict[str, Any]], json_as_text: bool
) -> None:
    rows = [_db_row(profile, json_as_text=json_as_text) for profile in profiles.values()]
    session = FakeSession(rows)

    result = get_profiles(session, PERSONALITY_ORDER)  # type: ignore[arg-type]

    assert set(result) == set(PERSONALITY_ORDER)
    for row in rows:
        profile = result[row["nombre"]]
        assert isinstance(profile, SimulationProfileRow)
        assert profile.id == row["id"]
        assert profile.nombre == row["nombre"]
        assert profile.activo is True
        assert profile.params == profiles[row["nombre"]]
        assert set(profile.params) == PROFILE_FIELDS
        for field in NUMERIC_FIELDS:
            assert type(profile.params[field]) is float
        for field in JSON_FIELDS:
            assert type(profile.params[field]) is dict


def test_maps_string_uuid_to_uuid(profiles: dict[str, dict[str, Any]]) -> None:
    profile_id = uuid4()
    session = FakeSession([_db_row(profiles["Consumo eficiente"], id=str(profile_id))])

    result = get_profiles(session, ["Consumo eficiente"])  # type: ignore[arg-type]

    assert result["Consumo eficiente"].id == profile_id
    assert isinstance(result["Consumo eficiente"].id, UUID)


def test_missing_profiles_are_absent_from_the_result(profiles: dict[str, dict[str, Any]]) -> None:
    session = FakeSession([_db_row(profiles["Consumo eficiente"])])

    result = get_profiles(
        session,  # type: ignore[arg-type]
        ["Consumo amplio", "Consumo eficiente"],
    )

    assert list(result) == ["Consumo eficiente"]


def test_without_names_returns_empty_without_sql() -> None:
    session = FakeSession()

    assert get_profiles(session, []) == {}  # type: ignore[arg-type]
    assert session.calls == []


def test_does_not_commit_and_statement_has_no_python_formatting(
    profiles: dict[str, dict[str, Any]],
) -> None:
    session = FakeSession([_db_row(profiles["Consumo eficiente"])])

    get_profiles(session, ["Consumo eficiente"])  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(simulation_profiles.PROFILES_BY_NAME_SQL)
    assert "{" not in sql
    assert "%" not in sql


# --- Fase 5: perfil asignado al hogar (RN-IV-05, DC-37) --------------------------------------


def _selected_columns(statement: Any) -> list[str]:
    sql = normalized_sql(statement)
    return sql.removeprefix("select ").split(" from ")[0].split(", ")


def test_household_profile_joins_the_assigned_profile_of_that_household() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert get_household_profile(session, hogar_id) is None  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is simulation_profiles.HOUSEHOLD_PROFILE_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert normalized_sql(statement).endswith(
        "from hogares h join perfiles_simulacion p on p.id = h.perfil_simulacion_id "
        "where h.id = :hogar_id"
    )


def test_household_profile_selects_the_same_columns_as_by_name() -> None:
    columns = _selected_columns(simulation_profiles.HOUSEHOLD_PROFILE_SQL)

    assert all(column.startswith("p.") for column in columns)
    assert [column.removeprefix("p.") for column in columns] == _selected_columns(
        simulation_profiles.PROFILES_BY_NAME_SQL
    )


@pytest.mark.parametrize("json_as_text", [False, True])
@pytest.mark.parametrize("name", PERSONALITY_ORDER)
def test_household_profile_params_equal_the_official_file(
    profiles: dict[str, dict[str, Any]], name: str, json_as_text: bool
) -> None:
    """NUMERIC llega como Decimal y sale como float; JSONB como dict (RN-IV-04)."""
    row = _db_row(profiles[name], json_as_text=json_as_text)
    session = FakeSession([row])

    result = get_household_profile(session, uuid4())  # type: ignore[arg-type]

    assert isinstance(result, SimulationProfileRow)
    assert result.id == row["id"]
    assert result.nombre == name
    assert result.params == profiles[name]
    for field in NUMERIC_FIELDS:
        assert type(result.params[field]) is float
    for field in JSON_FIELDS:
        assert type(result.params[field]) is dict


def test_household_profile_is_returned_even_if_inactive(
    profiles: dict[str, dict[str, Any]],
) -> None:
    """La serie del hogar no cambia aunque el perfil se desactive: no se filtra por `activo`."""
    profile_id = uuid4()
    session = FakeSession([_db_row(profiles["Consumo amplio"], id=str(profile_id), activo=False)])

    result = get_household_profile(session, uuid4())  # type: ignore[arg-type]

    assert result is not None
    assert result.activo is False
    assert result.id == profile_id
    assert isinstance(result.id, UUID)
    where = normalized_sql(session.calls[0][0]).split(" where ")[1]
    assert "activo" not in where


def test_household_profile_does_not_commit_and_has_no_python_formatting(
    profiles: dict[str, dict[str, Any]],
) -> None:
    session = FakeSession([_db_row(profiles["Consumo eficiente"])])

    get_household_profile(session, uuid4())  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(simulation_profiles.HOUSEHOLD_PROFILE_SQL)
    assert "{" not in sql
    assert "%" not in sql


def test_both_profile_queries_are_built_from_the_single_column_list() -> None:
    """Una sola lista de columnas (PROFILE_COLUMNS); el SQL sigue siendo constante."""
    assert _selected_columns(simulation_profiles.PROFILES_BY_NAME_SQL) == list(
        simulation_profiles.PROFILE_COLUMNS
    )
    assert _selected_columns(simulation_profiles.HOUSEHOLD_PROFILE_SQL) == [
        "p." + column for column in simulation_profiles.PROFILE_COLUMNS
    ]
    assert set(simulation_profiles.PROFILE_COLUMNS) == {"id", *PROFILE_FIELDS}
