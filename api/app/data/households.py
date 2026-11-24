"""Consultas de hogares, zonas, fuentes y sensores.

Las demás funciones se escriben en la sesión de cada endpoint (ver
docs/MAPA-DE-INTEGRACION.md). Sentencias constantes con parámetros con nombre; sin commit.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from app.data._convert import as_uuid

# RN-IX-09, DC-36: bloquea la fila del hogar para serializar altas y bajas de miembros.
LOCK_HOUSEHOLD_SQL = text(
    """
    select id
      from hogares
     where id = :hogar_id
       for update
    """
)

# RN-IX-09, DC-36: borra el hogar; el resto de sus datos cae en cascada (I-04).
DELETE_HOUSEHOLD_SQL = text(
    """
    delete from hogares
     where id = :hogar_id
    """
)


def lock_household(session: Session, hogar_id: UUID) -> None:
    """`SELECT ... FOR UPDATE` sobre el hogar hasta el fin de la transacción (RN-IX-09, DC-36).

    Evita que dos bajas simultáneas dejen el hogar sin miembros sin borrarlo. Sin commit.
    """
    session.exec(LOCK_HOUSEHOLD_SQL, params={"hogar_id": hogar_id})


def delete_household(session: Session, hogar_id: UUID) -> None:
    """Borra el hogar y, en cascada, todo lo que depende de él (RN-IX-09, DC-36, I-04).

    Solo se llama cuando el usuario que elimina su cuenta era el único miembro activo.
    Sin commit.
    """
    session.exec(DELETE_HOUSEHOLD_SQL, params={"hogar_id": hogar_id})


# RN-X-03, DC-37: alta del hogar. Los 4 permisos (RN-II-03) son los valores por defecto de la
# tabla: no se envían y vuelven por RETURNING.
INSERT_HOUSEHOLD_SQL = text(
    """
    insert into hogares (id, nombre, tipo_vivienda, perfil_simulacion_id)
    values (:hogar_id, :nombre, :tipo_vivienda, :perfil_simulacion_id)
    returning id,
              nombre,
              tipo_vivienda,
              permiso_ver_consumo_actual,
              permiso_ver_historial,
              permiso_recibir_alertas,
              permiso_modificar_metas
    """
)

# RN-X-03, RN-III-01: todas las zonas del onboarding en una sola sentencia.
INSERT_ZONES_SQL = text(
    """
    insert into zonas (id, hogar_id, nombre, tipo, estado)
    select z.id, cast(:hogar_id as uuid), z.nombre, z.tipo, 'activa'
      from unnest(
             cast(:zona_ids as uuid[]),
             cast(:nombres as text[]),
             cast(:tipos as text[])
           ) as z (id, nombre, tipo)
    """
)

# RN-X-03: la única fuente principal del hogar.
INSERT_MAIN_SOURCE_SQL = text(
    """
    insert into fuentes_principales (id, hogar_id, nombre, estado)
    values (:fuente_id, :hogar_id, :nombre, 'activa')
    """
)

# DC-38, I-01: la zona y la fuente se leen de sus tablas y deben ser del mismo hogar; una zona o
# una fuente de otro hogar no produce fila.
INSERT_ZONE_SENSORS_SQL = text(
    """
    insert into sensores_zona (id, zona_id, fuente_principal_id, estado)
    select s.id, z.id, f.id, 'activo'
      from unnest(
             cast(:sensor_ids as uuid[]),
             cast(:zona_ids as uuid[])
           ) as s (id, zona_id)
      join zonas z on z.id = s.zona_id
      join fuentes_principales f on f.hogar_id = z.hogar_id
     where z.hogar_id = :hogar_id
       and f.id = :fuente_id
    """
)


# RN-IV-05, DC-34: hogares con algo que generar, para la tarea programada. Es la única consulta
# que recorre todos los hogares: solo devuelve ids y cada hogar se procesa después con su propio
# filtro por hogar_id (R-01).
# Decidido el 23/11/2026 (Nicolás): los sensores 'pausado' y las zonas 'inactiva' NO reciben
# lecturas nuevas; por eso solo cuentan hogares con un sensor 'activo' en una zona 'activa'. La
# misma regla en Python es app.domain.zone_rules.counts_for_total.
# TODO(pendiente: ¿al reactivar un sensor o una zona se rellena el periodo en que estuvo
# pausado? En el MVP no hay operación que cambie esos estados)
HOUSEHOLDS_WITH_SENSORS_SQL = text(
    """
    select distinct z.hogar_id
      from zonas z
      join sensores_zona s on s.zona_id = z.id
     where z.estado = 'activa'
       and s.estado = 'activo'
     order by z.hogar_id
    """
)


# RN-XI-01, RN-XI-05, R-01: todas las zonas del hogar con el estado de su sensor (uno por zona,
# RN-X-03). El servicio decide cuáles cuentan (zona 'activa' con sensor 'activo'). LEFT JOIN: una
# zona sin sensor sale con sensor_estado NULL. Usa ix_zonas_hogar y el único sensores_zona.zona_id.
HOUSEHOLD_ZONES_SQL = text(
    """
    select z.id,
           z.tipo,
           z.nombre,
           z.estado,
           s.estado as sensor_estado
      from zonas z
      left join sensores_zona s on s.zona_id = z.id
     where z.hogar_id = :hogar_id
     order by z.nombre, z.id
    """
)


@dataclass(frozen=True)
class HouseholdRow:
    """Fila de hogares con sus 4 permisos generales (RN-II-03, RN-XVII)."""

    id: UUID
    nombre: str
    tipo_vivienda: str
    permiso_ver_consumo_actual: bool
    permiso_ver_historial: bool
    permiso_recibir_alertas: bool
    permiso_modificar_metas: bool


@dataclass(frozen=True)
class ZoneToInsert:
    """Zona nueva del onboarding (RN-III-01): el nombre sale de su tipo."""

    id: UUID
    tipo: str
    nombre: str


@dataclass(frozen=True)
class SensorToInsert:
    """Sensor nuevo de una zona (RN-X-03: uno por zona)."""

    id: UUID
    zona_id: UUID


@dataclass(frozen=True)
class ZoneRow:
    """Zona del hogar con el estado de su sensor (RN-XI-01, RN-XI-05)."""

    id: UUID
    tipo: str
    nombre: str
    estado: Literal["activa", "inactiva"]
    sensor_estado: Literal["activo", "pausado"] | None  # None si la zona no tiene sensor


def insert_household(
    session: Session,
    *,
    hogar_id: UUID,
    nombre: str,
    tipo_vivienda: str,
    perfil_simulacion_id: UUID,
) -> HouseholdRow:
    """Crea el hogar con los permisos por defecto de la tabla (RN-X-03, RN-II-03, DC-37).

    Los permisos devueltos son los de la fila guardada (RETURNING). Sin commit.
    """
    result = session.exec(
        INSERT_HOUSEHOLD_SQL,
        params={
            "hogar_id": hogar_id,
            "nombre": nombre,
            "tipo_vivienda": tipo_vivienda,
            "perfil_simulacion_id": perfil_simulacion_id,
        },
    )
    return _to_household_row(result.mappings().one())


def insert_zones(session: Session, hogar_id: UUID, zones: Sequence[ZoneToInsert]) -> int:
    """Crea las zonas del hogar, activas y en un solo lote (RN-X-03, RN-III-01).

    Devuelve cuántas guardó; lista vacía → 0 sin SQL. Sin commit.
    """
    if not zones:
        return 0
    result = session.exec(
        INSERT_ZONES_SQL,
        params={
            "hogar_id": hogar_id,
            "zona_ids": [str(zone.id) for zone in zones],
            "nombres": [zone.nombre for zone in zones],
            "tipos": [zone.tipo for zone in zones],
        },
    )
    return result.rowcount


def insert_main_source(session: Session, *, fuente_id: UUID, hogar_id: UUID, nombre: str) -> None:
    """Crea la fuente principal activa del hogar, una sola por hogar (RN-X-03). Sin commit."""
    session.exec(
        INSERT_MAIN_SOURCE_SQL,
        params={"fuente_id": fuente_id, "hogar_id": hogar_id, "nombre": nombre},
    )


def insert_zone_sensors(
    session: Session, *, hogar_id: UUID, fuente_id: UUID, sensors: Sequence[SensorToInsert]
) -> int:
    """Crea los sensores activos en un solo lote, solo con zonas y fuente del hogar (DC-38, I-01).

    Devuelve cuántos guardó: si es menor que `len(sensors)`, alguna zona o la fuente no es del
    hogar y el servicio debe revertir. Lista vacía → 0 sin SQL. Sin commit.
    """
    if not sensors:
        return 0
    result = session.exec(
        INSERT_ZONE_SENSORS_SQL,
        params={
            "hogar_id": hogar_id,
            "fuente_id": fuente_id,
            "sensor_ids": [str(sensor.id) for sensor in sensors],
            "zona_ids": [str(sensor.zona_id) for sensor in sensors],
        },
    )
    return result.rowcount


def list_household_ids_with_active_sensors(session: Session) -> list[UUID]:
    """Ids de los hogares con al menos un sensor 'activo' en una zona 'activa' (RN-IV-05, DC-34).

    Ordenados por id. Para la tarea programada: lee todos los hogares con la conexión del
    backend y no devuelve ningún otro dato. Sin commit.
    """
    result = session.exec(HOUSEHOLDS_WITH_SENSORS_SQL)
    return [as_uuid(row["hogar_id"]) for row in result.mappings().all()]


def list_household_zones(session: Session, hogar_id: UUID) -> list[ZoneRow]:
    """Todas las zonas de `hogar_id` con el estado de su sensor (RN-XI-01, RN-XI-05, R-01).

    Incluye zonas inactivas y sensores pausados: el servicio decide cuáles cuentan para el total.
    Orden por nombre y, a igual nombre, por id. Hogar sin zonas → lista vacía. Sin commit.
    """
    result = session.exec(HOUSEHOLD_ZONES_SQL, params={"hogar_id": hogar_id})
    return [_to_zone_row(row) for row in result.mappings().all()]


def _to_household_row(row: Mapping[str, Any]) -> HouseholdRow:
    """Convierte la fila de INSERT_HOUSEHOLD_SQL en HouseholdRow."""
    hogar_id = row["id"]
    return HouseholdRow(
        id=as_uuid(hogar_id),
        nombre=row["nombre"],
        tipo_vivienda=row["tipo_vivienda"],
        permiso_ver_consumo_actual=bool(row["permiso_ver_consumo_actual"]),
        permiso_ver_historial=bool(row["permiso_ver_historial"]),
        permiso_recibir_alertas=bool(row["permiso_recibir_alertas"]),
        permiso_modificar_metas=bool(row["permiso_modificar_metas"]),
    )


def _to_zone_row(row: Mapping[str, Any]) -> ZoneRow:
    """Convierte la fila de HOUSEHOLD_ZONES_SQL en ZoneRow (id a UUID)."""
    return ZoneRow(
        id=as_uuid(row["id"]),
        tipo=row["tipo"],
        nombre=row["nombre"],
        estado=row["estado"],
        sensor_estado=row["sensor_estado"],
    )
