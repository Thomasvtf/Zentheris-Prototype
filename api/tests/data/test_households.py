"""Pruebas de app.data.households sin base real (RN-IX-09, DC-36; RN-X-03, DC-38).

El borrado en cascada real (I-04) necesita Postgres: está en tests/integrity. Aquí se
comprueba el SQL generado, el FOR UPDATE y que los valores viajan como parámetros.
"""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.data import households
from app.data.households import (
    HouseholdRow,
    SensorToInsert,
    ZoneToInsert,
    delete_household,
    insert_household,
    insert_main_source,
    insert_zone_sensors,
    insert_zones,
    list_household_ids_with_active_sensors,
    lock_household,
)
from tests.data.fake_session import FakeResult, FakeSession, assert_bound_only, normalized_sql
from tests.helpers.personalities import ZONE_KEYS

# Nombres de zona del catálogo de textos (RN-XII-03): ningún texto se escribe a mano.
CATALOG_PATH = Path(__file__).resolve().parents[3] / "docs" / "textos" / "catalogo.es-CO.json"
ZONE_NAMES: dict[str, str] = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["zona"]

# Valores por defecto de la tabla hogares (migración 0002, RN-II-03).
DEFAULT_PERMISSIONS = {
    "permiso_ver_consumo_actual": True,
    "permiso_ver_historial": True,
    "permiso_recibir_alertas": True,
    "permiso_modificar_metas": False,
}


def test_lock_household_selects_the_row_for_update() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert lock_household(session, hogar_id) is None  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql == "select id from hogares where id = :hogar_id for update"


def test_delete_household_deletes_only_that_household() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert delete_household(session, hogar_id) is None  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == "delete from hogares where id = :hogar_id"


def test_statements_are_constants_and_functions_do_not_commit() -> None:
    session = FakeSession()

    lock_household(session, uuid4())  # type: ignore[arg-type]
    delete_household(session, uuid4())  # type: ignore[arg-type]

    assert session.commits == 0
    for statement in (households.LOCK_HOUSEHOLD_SQL, households.DELETE_HOUSEHOLD_SQL):
        assert isinstance(statement, TextClause)
        assert "{" not in str(statement)
        assert "%" not in str(statement)


# --- Fase 4: alta del hogar en el onboarding (RN-X-03) ----------------------------------------


def _insert_household(session: FakeSession, hogar_id: UUID, perfil_id: UUID) -> HouseholdRow:
    return insert_household(
        session,  # type: ignore[arg-type]
        hogar_id=hogar_id,
        nombre="Casa de los Pérez",
        tipo_vivienda="duplex",
        perfil_simulacion_id=perfil_id,
    )


def _zones() -> list[ZoneToInsert]:
    return [ZoneToInsert(id=uuid4(), tipo=tipo, nombre=ZONE_NAMES[tipo]) for tipo in ZONE_KEYS]


def test_insert_household_takes_permissions_from_the_table_defaults() -> None:
    """RN-II-03: los 4 permisos no se envían; llegan por RETURNING con el default de la tabla."""
    hogar_id, perfil_id = uuid4(), uuid4()
    row = {
        "id": str(hogar_id),
        "nombre": "Casa de los Pérez",
        "tipo_vivienda": "duplex",
        **DEFAULT_PERMISSIONS,
    }
    session = FakeSession([row])

    result = _insert_household(session, hogar_id, perfil_id)

    assert result == HouseholdRow(
        id=hogar_id, nombre="Casa de los Pérez", tipo_vivienda="duplex", **DEFAULT_PERMISSIONS
    )
    assert isinstance(result.id, UUID)
    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {
        "hogar_id": hogar_id,
        "nombre": "Casa de los Pérez",
        "tipo_vivienda": "duplex",
        "perfil_simulacion_id": perfil_id,
    }
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "insert into hogares (id, nombre, tipo_vivienda, perfil_simulacion_id) "
        "values (:hogar_id, :nombre, :tipo_vivienda, :perfil_simulacion_id) "
        "returning id, nombre, tipo_vivienda, permiso_ver_consumo_actual, "
        "permiso_ver_historial, permiso_recibir_alertas, permiso_modificar_metas"
    )


def test_insert_household_returns_whatever_the_table_returns() -> None:
    """No hay permisos fijos en el código: si cambia el default, cambia el resultado."""
    hogar_id = uuid4()
    inverted = {name: not value for name, value in DEFAULT_PERMISSIONS.items()}
    session = FakeSession([{"id": hogar_id, "nombre": "Casa", "tipo_vivienda": "casa", **inverted}])

    result = _insert_household(session, hogar_id, uuid4())

    assert {name: getattr(result, name) for name in inverted} == inverted


def test_insert_household_fails_if_the_table_returns_no_row() -> None:
    with pytest.raises(AssertionError, match="exactamente una fila"):
        _insert_household(FakeSession(), uuid4(), uuid4())


def test_insert_zones_sends_all_rows_in_one_statement() -> None:
    hogar_id = uuid4()
    zones = _zones()
    session = FakeSession(FakeResult(rowcount=len(zones)))

    assert insert_zones(session, hogar_id, zones) == 9  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {
        "hogar_id": hogar_id,
        "zona_ids": [str(zone.id) for zone in zones],
        "nombres": [zone.nombre for zone in zones],
        "tipos": [zone.tipo for zone in zones],
    }
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "insert into zonas (id, hogar_id, nombre, tipo, estado) "
        "select z.id, cast(:hogar_id as uuid), z.nombre, z.tipo, 'activa' "
        "from unnest( cast(:zona_ids as uuid[]), cast(:nombres as text[]), "
        "cast(:tipos as text[]) ) as z (id, nombre, tipo)"
    )


def test_insert_main_source_is_active_and_belongs_to_the_household() -> None:
    """RN-X-03: una sola fuente principal por hogar."""
    fuente_id, hogar_id = uuid4(), uuid4()
    nombre = "Fuente principal Casa de los Pérez"
    session = FakeSession()

    insert_main_source(
        session,  # type: ignore[arg-type]
        fuente_id=fuente_id,
        hogar_id=hogar_id,
        nombre=nombre,
    )

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {"fuente_id": fuente_id, "hogar_id": hogar_id, "nombre": nombre}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "insert into fuentes_principales (id, hogar_id, nombre, estado) "
        "values (:fuente_id, :hogar_id, :nombre, 'activa')"
    )


def test_insert_zone_sensors_sends_all_rows_in_one_statement() -> None:
    """DC-38: la unión por hogar se detalla en tests/integrity (I-01)."""
    hogar_id, fuente_id = uuid4(), uuid4()
    sensors = [SensorToInsert(id=uuid4(), zona_id=zone.id) for zone in _zones()]
    session = FakeSession(FakeResult(rowcount=len(sensors)))

    inserted = insert_zone_sensors(
        session,  # type: ignore[arg-type]
        hogar_id=hogar_id,
        fuente_id=fuente_id,
        sensors=sensors,
    )

    assert inserted == 9
    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {
        "hogar_id": hogar_id,
        "fuente_id": fuente_id,
        "sensor_ids": [str(sensor.id) for sensor in sensors],
        "zona_ids": [str(sensor.zona_id) for sensor in sensors],
    }
    assert_bound_only(statement, params)


def test_empty_batches_return_zero_without_sql() -> None:
    session = FakeSession()

    assert insert_zones(session, uuid4(), []) == 0  # type: ignore[arg-type]
    inserted = insert_zone_sensors(
        session,  # type: ignore[arg-type]
        hogar_id=uuid4(),
        fuente_id=uuid4(),
        sensors=[],
    )

    assert inserted == 0
    assert session.calls == []


def test_phase4_functions_do_not_commit() -> None:
    hogar_id = uuid4()
    zones = _zones()
    session = FakeSession(
        [{"id": hogar_id, "nombre": "Casa", "tipo_vivienda": "casa", **DEFAULT_PERMISSIONS}]
    )

    _insert_household(session, hogar_id, uuid4())
    insert_zones(session, hogar_id, zones)  # type: ignore[arg-type]
    insert_main_source(
        session,  # type: ignore[arg-type]
        fuente_id=uuid4(),
        hogar_id=hogar_id,
        nombre="Fuente principal Casa",
    )
    insert_zone_sensors(
        session,  # type: ignore[arg-type]
        hogar_id=hogar_id,
        fuente_id=uuid4(),
        sensors=[SensorToInsert(id=uuid4(), zona_id=zone.id) for zone in zones],
    )

    assert len(session.calls) == 4
    assert session.commits == 0


# --- Fase 5: hogares para la tarea programada (RN-IV-05, DC-34) ------------------------------


def test_households_with_sensors_query_has_no_parameters_and_active_filters() -> None:
    session = FakeSession()

    assert list_household_ids_with_active_sensors(session) == []  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is households.HOUSEHOLDS_WITH_SENSORS_SQL
    assert isinstance(statement, TextClause)
    assert params is None
    assert statement._bindparams == {}
    assert normalized_sql(statement) == (
        "select distinct z.hogar_id from zonas z "
        "join sensores_zona s on s.zona_id = z.id "
        "where z.estado = 'activa' and s.estado = 'activo' "
        "order by z.hogar_id"
    )


def test_households_with_sensors_are_mapped_to_uuid_in_the_query_order() -> None:
    first, second = sorted([uuid4(), uuid4()])
    session = FakeSession([{"hogar_id": first}, {"hogar_id": str(second)}])

    result = list_household_ids_with_active_sensors(session)  # type: ignore[arg-type]

    assert result == [first, second]
    assert all(isinstance(hogar_id, UUID) for hogar_id in result)


def test_households_with_sensors_does_not_commit() -> None:
    session = FakeSession([{"hogar_id": uuid4()}])

    list_household_ids_with_active_sensors(session)  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(households.HOUSEHOLDS_WITH_SENSORS_SQL)
    assert "{" not in sql
    assert "%" not in sql


def test_households_with_sensors_documents_the_pending_rule_for_paused_sensors() -> None:
    source = Path(households.__file__).read_text(encoding="utf-8")
    before_sql = source.split("HOUSEHOLDS_WITH_SENSORS_SQL = text(")[0]

    assert (
        "TODO(pendiente: ¿un sensor pausado o una zona inactiva generan lecturas?"
        in (before_sql.rsplit("\n\n", 1)[1])
    )
