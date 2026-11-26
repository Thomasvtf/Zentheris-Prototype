"""Pruebas de app.data.households sin base real (RN-IX-09, DC-36; RN-X-03, DC-38).

El borrado en cascada real (I-04) necesita Postgres: está en tests/integrity. Aquí se
comprueba el SQL generado, el FOR NO KEY UPDATE y que los valores viajan como parámetros.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.data import households
from app.data.households import (
    HouseholdRow,
    MainSourceRow,
    SensorToInsert,
    ZoneRow,
    ZoneSensorRow,
    ZoneToInsert,
    delete_household,
    get_household,
    get_household_created_at,
    get_main_source,
    insert_household,
    insert_main_source,
    insert_zone_sensors,
    insert_zones,
    list_household_ids_with_active_sensors,
    list_household_zones,
    list_zone_sensors,
    lock_household,
    update_permissions,
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


def test_lock_household_selects_the_row_for_no_key_update() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert lock_household(session, hogar_id) is None  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql == "select id from hogares where id = :hogar_id for no key update"


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


def test_households_with_sensors_documents_the_paused_sensor_decision_and_open_question() -> None:
    """Decidido el 23/11/2026: pausados e inactivas no reciben lecturas; queda el relleno."""
    source = Path(households.__file__).read_text(encoding="utf-8")
    comment = source.split("HOUSEHOLDS_WITH_SENSORS_SQL = text(")[0].rsplit("\n\n", 1)[1]

    assert "Decidido el 23/11/2026" in comment
    assert "NO reciben" in comment
    assert "app.domain.zone_rules.counts_for_total" in comment
    assert "TODO(pendiente: ¿al reactivar un sensor o una zona se rellena el periodo" in comment
    assert "¿un sensor pausado o una zona inactiva generan lecturas?" not in comment


# --- Fase 6: zonas del hogar con el estado de su sensor (RN-XI-01, RN-XI-05, R-01) -----------


def _zone_row(tipo: str, **overrides: object) -> dict[str, object]:
    """Fila como la entregaría psycopg2; el nombre sale del catálogo (RN-XII-03)."""
    row: dict[str, object] = {
        "id": uuid4(),
        "tipo": tipo,
        "nombre": ZONE_NAMES[tipo],
        "estado": "activa",
        "sensor_estado": "activo",
    }
    row.update(overrides)
    return row


def test_household_zones_sends_only_the_household_as_parameter() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert list_household_zones(session, hogar_id) == []  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is households.HOUSEHOLD_ZONES_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)


def test_household_zones_sql_left_joins_the_sensor_and_filters_by_household() -> None:
    """R-01: solo zonas del hogar; LEFT JOIN para no perder una zona sin sensor."""
    assert normalized_sql(households.HOUSEHOLD_ZONES_SQL) == (
        "select z.id, z.tipo, z.nombre, z.estado, s.estado as sensor_estado "
        "from zonas z "
        "left join sensores_zona s on s.zona_id = z.id "
        "where z.hogar_id = :hogar_id "
        "order by z.nombre, z.id"
    )


def test_household_zones_include_inactive_zones_and_paused_sensors() -> None:
    """El servicio decide qué zonas cuentan: la consulta no filtra por estado."""
    sql = normalized_sql(households.HOUSEHOLD_ZONES_SQL)

    assert "'activa'" not in sql
    assert "'activo'" not in sql


def test_household_zones_are_mapped_in_the_query_order() -> None:
    cocina_id, sala_id, garaje_id = uuid4(), uuid4(), uuid4()
    session = FakeSession(
        [
            _zone_row("cocina", id=cocina_id),
            _zone_row("garaje", id=str(garaje_id), estado="inactiva", sensor_estado="pausado"),
            _zone_row("sala", id=sala_id, sensor_estado=None),
        ]
    )

    zones = list_household_zones(session, uuid4())  # type: ignore[arg-type]

    assert zones == [
        ZoneRow(
            id=cocina_id,
            tipo="cocina",
            nombre=ZONE_NAMES["cocina"],
            estado="activa",
            sensor_estado="activo",
        ),
        ZoneRow(
            id=garaje_id,
            tipo="garaje",
            nombre=ZONE_NAMES["garaje"],
            estado="inactiva",
            sensor_estado="pausado",
        ),
        ZoneRow(
            id=sala_id,
            tipo="sala",
            nombre=ZONE_NAMES["sala"],
            estado="activa",
            sensor_estado=None,
        ),
    ]
    assert all(isinstance(zone.id, UUID) for zone in zones)


def test_household_zones_map_all_nine_zone_types() -> None:
    session = FakeSession([_zone_row(tipo) for tipo in ZONE_KEYS])

    zones = list_household_zones(session, uuid4())  # type: ignore[arg-type]

    assert [zone.tipo for zone in zones] == list(ZONE_KEYS)
    assert [zone.nombre for zone in zones] == [ZONE_NAMES[tipo] for tipo in ZONE_KEYS]


def test_household_zones_do_not_commit_and_have_no_python_formatting() -> None:
    session = FakeSession([_zone_row("cocina")])

    list_household_zones(session, uuid4())  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(households.HOUSEHOLD_ZONES_SQL)
    assert "{" not in sql
    assert "%" not in sql


# ------------------------------------------------------------------ alta del hogar (DC-32, RN-XIV-07)


def test_household_created_at_binds_the_household() -> None:
    hogar_id = uuid4()
    created_at = datetime(2026, 10, 3, 17, 12, tzinfo=UTC)
    session = FakeSession([{"created_at": created_at}])

    assert get_household_created_at(session, hogar_id) == created_at  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is households.HOUSEHOLD_CREATED_AT_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == "select created_at from hogares where id = :hogar_id"
    assert session.commits == 0


def test_household_created_at_missing_household_is_none() -> None:
    assert get_household_created_at(FakeSession([]), uuid4()) is None  # type: ignore[arg-type]


# --- Fase 9: hogar y permisos generales (RN-II-03, RN-X-08, RN-XVII) --------------------------

PERMISSION_KEYS = ("ver_consumo_actual", "ver_historial", "recibir_alertas", "modificar_metas")


def _household_db_row(hogar_id: UUID | str, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": hogar_id,
        "nombre": "Casa de prueba",
        "tipo_vivienda": "apartamento",
        **DEFAULT_PERMISSIONS,
    }
    row.update(overrides)
    return row


def test_get_household_binds_the_household_and_maps_permissions() -> None:
    hogar_id = uuid4()
    session = FakeSession([_household_db_row(str(hogar_id), permiso_modificar_metas=True)])

    row = get_household(session, hogar_id)  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is households.HOUSEHOLD_SQL
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "select id, nombre, tipo_vivienda, permiso_ver_consumo_actual, permiso_ver_historial, "
        "permiso_recibir_alertas, permiso_modificar_metas from hogares where id = :hogar_id"
    )
    assert row == HouseholdRow(
        id=hogar_id,
        nombre="Casa de prueba",
        tipo_vivienda="apartamento",
        permiso_ver_consumo_actual=True,
        permiso_ver_historial=True,
        permiso_recibir_alertas=True,
        permiso_modificar_metas=True,
    )
    assert session.commits == 0


def test_get_household_returns_none_without_row() -> None:
    assert get_household(FakeSession(), uuid4()) is None  # type: ignore[arg-type]


def test_permission_keys_map_to_the_hogares_columns() -> None:
    assert dict(households.PERMISSION_COLUMNS) == {key: f"permiso_{key}" for key in PERMISSION_KEYS}
    assert set(households.PERMISSION_COLUMNS.values()) == set(DEFAULT_PERMISSIONS)


def test_update_permissions_is_one_constant_statement_with_coalesce() -> None:
    sql = normalized_sql(households.UPDATE_PERMISSIONS_SQL)

    assert isinstance(households.UPDATE_PERMISSIONS_SQL, TextClause)
    assert "{" not in str(households.UPDATE_PERMISSIONS_SQL)
    assert "%" not in str(households.UPDATE_PERMISSIONS_SQL)
    for key in PERMISSION_KEYS:
        assert f"permiso_{key} = coalesce(:{key}, permiso_{key})" in sql
    assert "where id = :hogar_id returning id, nombre, tipo_vivienda," in sql


def test_update_permissions_sends_only_the_changed_values_and_nulls_for_the_rest() -> None:
    hogar_id = uuid4()
    session = FakeSession([_household_db_row(hogar_id, permiso_recibir_alertas=False)])

    row = update_permissions(session, hogar_id, {"recibir_alertas": False})  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is households.UPDATE_PERMISSIONS_SQL
    assert params == {
        "hogar_id": hogar_id,
        "ver_consumo_actual": None,
        "ver_historial": None,
        "recibir_alertas": False,
        "modificar_metas": None,
    }
    assert_bound_only(statement, params)
    assert row is not None
    assert row.permiso_recibir_alertas is False
    assert row.permiso_ver_historial is True
    assert session.commits == 0


def test_update_permissions_with_every_key() -> None:
    hogar_id = uuid4()
    changes = dict.fromkeys(PERMISSION_KEYS, True)
    session = FakeSession([_household_db_row(hogar_id, permiso_modificar_metas=True)])

    row = update_permissions(session, hogar_id, changes)  # type: ignore[arg-type]

    _statement, params = session.calls[0]
    assert params == {"hogar_id": hogar_id, **changes}
    assert row is not None
    assert row.permiso_modificar_metas is True


def test_update_permissions_returns_none_without_household() -> None:
    assert update_permissions(FakeSession(), uuid4(), {"ver_historial": False}) is None  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"permiso_ver_historial": True},
        {"ver_historial": True, "nombre": "Otro"},
        {"ver_historial": None},
        {"ver_historial": 1},
        {"ver_historial": "true"},
    ],
    ids=["vacío", "nombre de columna", "clave desconocida", "nulo", "entero", "texto"],
)
def test_update_permissions_rejects_invalid_changes_without_sql(changes: dict[str, Any]) -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        update_permissions(session, uuid4(), changes)  # type: ignore[arg-type]

    assert session.calls == []


# ------------------------------------------------------------ fuentes de datos (RN-XVI-06)


def test_main_source_binds_only_the_household() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert get_main_source(session, hogar_id) is None  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is households.MAIN_SOURCE_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "select id, nombre, estado from fuentes_principales where hogar_id = :hogar_id"
    )
    assert session.commits == 0


@pytest.mark.parametrize("estado", ["activa", "inactiva"])
def test_main_source_maps_the_row(estado: str) -> None:
    fuente_id = uuid4()
    session = FakeSession([{"id": str(fuente_id), "nombre": "Medidor principal", "estado": estado}])

    source = get_main_source(session, uuid4())  # type: ignore[arg-type]

    assert source == MainSourceRow(id=fuente_id, nombre="Medidor principal", estado=estado)  # type: ignore[arg-type]
    assert isinstance(source.id, UUID)


def test_zone_sensors_bind_only_the_household() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert list_zone_sensors(session, hogar_id) == []  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is households.ZONE_SENSORS_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert session.commits == 0


def test_zone_sensors_sql_joins_the_zone_filters_by_household_and_orders_by_zone() -> None:
    """R-01 e I-01: el hogar sale de zonas; todos los estados (el dominio decide, RN-III-03)."""
    assert normalized_sql(households.ZONE_SENSORS_SQL) == (
        "select s.id as sensor_id, z.id as zona_id, z.tipo as zona_tipo, "
        "z.estado as zona_estado, s.estado as sensor_estado "
        "from sensores_zona s "
        "join zonas z on z.id = s.zona_id "
        "where z.hogar_id = :hogar_id "
        "order by z.id"
    )
    sql = normalized_sql(households.ZONE_SENSORS_SQL)
    assert "'activa'" not in sql
    assert "'activo'" not in sql


def _sensor_row(tipo: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "sensor_id": uuid4(),
        "zona_id": uuid4(),
        "zona_tipo": tipo,
        "zona_estado": "activa",
        "sensor_estado": "activo",
    }
    row.update(overrides)
    return row


def test_zone_sensors_are_mapped_in_the_query_order_with_every_state() -> None:
    s1, z1, s2, z2 = uuid4(), uuid4(), uuid4(), uuid4()
    session = FakeSession(
        [
            _sensor_row("cocina", sensor_id=str(s1), zona_id=str(z1)),
            _sensor_row(
                "garaje", sensor_id=s2, zona_id=z2, zona_estado="inactiva", sensor_estado="pausado"
            ),
        ]
    )

    sensors = list_zone_sensors(session, uuid4())  # type: ignore[arg-type]

    assert sensors == [
        ZoneSensorRow(
            sensor_id=s1,
            zona_id=z1,
            zona_tipo="cocina",
            zona_estado="activa",
            sensor_estado="activo",
        ),
        ZoneSensorRow(
            sensor_id=s2,
            zona_id=z2,
            zona_tipo="garaje",
            zona_estado="inactiva",
            sensor_estado="pausado",
        ),
    ]
    assert all(isinstance(s.sensor_id, UUID) and isinstance(s.zona_id, UUID) for s in sensors)


def test_zone_sensors_map_all_nine_zone_types() -> None:
    session = FakeSession([_sensor_row(tipo) for tipo in ZONE_KEYS])

    sensors = list_zone_sensors(session, uuid4())  # type: ignore[arg-type]

    assert [sensor.zona_tipo for sensor in sensors] == list(ZONE_KEYS)


@pytest.mark.parametrize("statement", ["MAIN_SOURCE_SQL", "ZONE_SENSORS_SQL"])
def test_data_source_statements_have_no_python_formatting(statement: str) -> None:
    sql = str(getattr(households, statement))
    assert "{" not in sql
    assert "%" not in sql
