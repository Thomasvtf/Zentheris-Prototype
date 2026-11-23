"""I-01 · Integridad: Sensor y zona de hogares distintos.

Esperado: 0 casos (consulta de integridad). Regla: DC-38.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Sin base se comprueba la construcción: el único INSERT de sensores une cada zona y la fuente
principal por el mismo hogar. La consulta de integridad sobre datos reales queda en skip."""

import re
from pathlib import Path
from uuid import uuid4

import pytest

from app.data.households import INSERT_ZONE_SENSORS_SQL, SensorToInsert, insert_zone_sensors
from tests.data.fake_session import FakeResult, FakeSession, assert_bound_only, normalized_sql

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# Consulta de integridad de DC-38: sensores cuya zona y fuente son de hogares distintos.
MISMATCHED_SENSORS_SQL = """
    select count(*) as total
      from sensores_zona s
      join zonas z on z.id = s.zona_id
      join fuentes_principales f on f.id = s.fuente_principal_id
     where z.hogar_id <> f.hogar_id
"""


def test_sensor_insert_joins_zone_and_source_of_the_same_household() -> None:
    """La zona y la fuente salen de las tablas ya filtradas, nunca directo del parámetro."""
    assert normalized_sql(INSERT_ZONE_SENSORS_SQL) == (
        "insert into sensores_zona (id, zona_id, fuente_principal_id, estado) "
        "select s.id, z.id, f.id, 'activo' "
        "from unnest( cast(:sensor_ids as uuid[]), cast(:zona_ids as uuid[]) ) "
        "as s (id, zona_id) "
        "join zonas z on z.id = s.zona_id "
        "join fuentes_principales f on f.hogar_id = z.hogar_id "
        "where z.hogar_id = :hogar_id and f.id = :fuente_id"
    )


def test_count_reveals_zones_rejected_by_the_household_filter() -> None:
    """Una zona de otro hogar no produce fila: el conteo queda por debajo de lo pedido."""
    sensors = [SensorToInsert(id=uuid4(), zona_id=uuid4()) for _ in range(3)]
    session = FakeSession(FakeResult(rowcount=2))

    inserted = insert_zone_sensors(
        session,  # type: ignore[arg-type]
        hogar_id=uuid4(),
        fuente_id=uuid4(),
        sensors=sensors,
    )

    assert inserted == 2
    assert inserted < len(sensors)
    assert_bound_only(*session.calls[0])


def test_no_other_statement_writes_sensors() -> None:
    """El INSERT con filtro de hogar es la única escritura de sensores_zona en la API."""
    pattern = re.compile(r"(insert\s+into|update)\s+(public\.)?sensores_zona", re.IGNORECASE)
    writers = {}
    for path in APP_DIR.rglob("*.py"):
        matches = len(pattern.findall(path.read_text(encoding="utf-8")))
        if matches:
            writers[path.relative_to(APP_DIR).as_posix()] = matches

    assert writers == {"data/households.py": 1}


@pytest.mark.skip(reason="TODO(I-01): requiere Postgres local (MISMATCHED_SENSORS_SQL da 0)")
def test_integrity_query_finds_no_mismatched_sensors() -> None:
    """Tras el onboarding, MISMATCHED_SENSORS_SQL devuelve 0 casos."""
