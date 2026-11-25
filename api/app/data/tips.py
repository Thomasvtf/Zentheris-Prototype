"""Consultas de consejos (consejos) y de su seguimiento por persona (consejos_usuario).

RN-XV-03, RN-XV-04, RN-XV-05, RN-XV-06, DC-24, RN-VI-03. Sentencias constantes con parámetros con
nombre; sin commit (la transacción es del servicio). Toda consulta filtra por `hogar_id` (R-01).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from app.data._convert import as_uuid

# Estados de consejos_usuario (check consejos_usuario_estado_coherente).
TIP_STATES = ("pendiente", "completada")

# RN-XV-05 (vigencia de 7 días), DC-35 (consejo y aviso con la alerta) y DC-24 (variante alterna;
# la anterior se reconoce por su título): el último consejo (created_at desc, id desc) por
# (regla_origen, zona_id) del hogar. DISTINCT ON trata los zona_id nulos (consejos generales) como iguales. Entra por
# ix_consejos_hogar_fecha.
LATEST_TIPS_SQL = text(
    """
    select distinct on (regla_origen, zona_id)
           regla_origen,
           zona_id,
           titulo,
           created_at
      from consejos
     where hogar_id = :hogar_id
     order by regla_origen, zona_id, created_at desc, id desc
    """
)

# RN-XV-04, DC-24: alta de un consejo con el texto ya resuelto; created_at = momento del evento
# (fin de la hora; cierre: 00:00 del día 1). I-01: una zona de otro hogar no produce fila. La coherencia categoría/zona la garantiza consejos_categoria_coherente.
INSERT_TIP_SQL = text(
    """
    insert into consejos (hogar_id, categoria, prioridad, zona_id, titulo, descripcion,
                          regla_origen, created_at, updated_at)
    select cast(:hogar_id as uuid), :categoria, :prioridad, cast(:zona_id as uuid), :titulo,
           :descripcion, :regla_origen,
           cast(:created_at as timestamptz), cast(:created_at as timestamptz)
     where cast(:zona_id as uuid) is null
        or exists (
             select 1
               from zonas z
              where z.id = cast(:zona_id as uuid)
                and z.hogar_id = cast(:hogar_id as uuid)
           )
    returning id
    """
)

# RN-VI-03, RN-XV-06: una fila 'pendiente' por persona, en una sola sentencia. Solo miembros
# activos del hogar del consejo (R-01); la repetida se descarta por consejos_usuario_unico.
INSERT_TIP_ASSIGNMENTS_SQL = text(
    """
    insert into consejos_usuario (consejo_id, usuario_id, estado, completada_en)
    select c.id, m.usuario_id, 'pendiente', null
      from unnest(cast(:usuario_ids as uuid[])) as u (usuario_id)
      join consejos c on c.id = cast(:consejo_id as uuid)
      join hogar_miembros m on m.hogar_id = c.hogar_id
                           and m.usuario_id = u.usuario_id
                           and m.estado = 'activo'
    on conflict (consejo_id, usuario_id) do nothing
    """
)

# Consejo con el seguimiento de la persona; filtra por usuario y hogar (R-01, RN-VI-03).
_USER_TIP_SELECT = """
    select c.id,
           c.categoria,
           c.prioridad,
           c.titulo,
           c.descripcion,
           c.zona_id,
           z.tipo as zona_tipo,
           cu.estado,
           cu.completada_en,
           c.created_at
      from consejos_usuario cu
      join consejos c on c.id = cu.consejo_id
      left join zonas z on z.id = c.zona_id
     where cu.usuario_id = :usuario_id
       and c.hogar_id = :hogar_id
    """

# RN-XV-03, RN-XV-05: primero las pendientes vigentes (alta, media, baja; luego created_at desc,
# id desc) y después las completadas recientes (completada_en desc, id desc). En las pendientes
# completada_en es nulo (check), así que solo decide id; en las completadas el CASE da nulo.
USER_TIPS_SQL = text(
    _USER_TIP_SELECT
    + """
       and ((cu.estado = 'pendiente' and c.created_at > :pending_created_after)
            or (cu.estado = 'completada' and cu.completada_en > :completed_after))
     order by case cu.estado when 'pendiente' then 0 else 1 end,
              case when cu.estado = 'pendiente' then
                case c.prioridad when 'alta' then 0 when 'media' then 1 else 2 end
              end,
              case when cu.estado = 'pendiente' then c.created_at end desc,
              cu.completada_en desc,
              c.id desc
    """
)

# RN-XV-03: un consejo concreto de la persona en ese hogar.
USER_TIP_SQL = text(_USER_TIP_SELECT + "   and c.id = :consejo_id\n")

# RN-XV-03: cambia el estado del seguimiento de la persona (consejo del hogar).
UPDATE_USER_TIP_STATUS_SQL = text(
    """
    update consejos_usuario cu
       set estado = :estado,
           completada_en = cast(:completada_en as timestamptz),
           updated_at = now()
      from consejos c
     where c.id = cu.consejo_id
       and c.hogar_id = :hogar_id
       and cu.usuario_id = :usuario_id
       and cu.consejo_id = :consejo_id
    """
)


@dataclass(frozen=True)
class TipHistoryRow:
    """Último consejo del hogar de una regla y zona (RN-XV-05, DC-24)."""

    regla_origen: str
    zona_id: UUID | None  # None en los consejos generales
    titulo: str
    created_at: datetime


@dataclass(frozen=True)
class UserTipRow:
    """Consejo con el seguimiento de una persona (RN-XV-03, RN-VI-03)."""

    id: UUID
    categoria: str
    prioridad: str
    titulo: str
    descripcion: str
    zona_id: UUID | None
    zona_tipo: str | None  # None en los consejos generales
    estado: str
    completada_en: datetime | None  # None mientras está pendiente
    created_at: datetime


def list_latest_tips(session: Session, hogar_id: UUID) -> list[TipHistoryRow]:
    """El último consejo por (regla_origen, zona_id) de `hogar_id` (RN-XV-05, DC-24, R-01).

    Para la vigencia de 7 días (RN-XV-05), el consejo con la alerta (DC-35) y la variante alterna
    (DC-24: la anterior se reconoce por su título). Hogar sin consejos → lista vacía. Sin commit.
    """
    result = session.exec(LATEST_TIPS_SQL, params={"hogar_id": hogar_id})
    return [_to_tip_history_row(row) for row in result.mappings().all()]


def insert_tip(
    session: Session,
    *,
    hogar_id: UUID,
    categoria: str,
    prioridad: str,
    zona_id: UUID | None,
    titulo: str,
    descripcion: str,
    regla_origen: str,
    created_at: datetime,
) -> UUID:
    """Crea el consejo del hogar y devuelve su id (RN-XV-04, DC-24).

    created_at y updated_at = `created_at`, el momento del evento (fin de la hora). ValueError, sin SQL, si `created_at` no tiene zona
    horaria; ValueError si `zona_id` no es una zona de `hogar_id` (I-01: la sentencia no inserta).
    Sin commit.
    """
    if created_at.utcoffset() is None:
        raise ValueError("`created_at` debe llevar zona horaria.")
    result = session.exec(
        INSERT_TIP_SQL,
        params={
            "hogar_id": hogar_id,
            "categoria": categoria,
            "prioridad": prioridad,
            "zona_id": zona_id,
            "titulo": titulo,
            "descripcion": descripcion,
            "regla_origen": regla_origen,
            "created_at": created_at,
        },
    )
    row = result.mappings().first()
    if row is None:
        raise ValueError("La zona del consejo no es del hogar.")
    return as_uuid(row["id"])


def insert_tip_assignments(session: Session, consejo_id: UUID, usuario_ids: Sequence[UUID]) -> int:
    """Asigna el consejo, 'pendiente', a cada persona en una sola sentencia (RN-VI-03, RN-XV-06).

    Solo miembros activos del hogar del consejo (R-01); la repetida se descarta (`ON CONFLICT
    (consejo_id, usuario_id) DO NOTHING`). Devuelve cuántas guardó; vacío → 0 sin SQL. Sin commit.
    """
    if not usuario_ids:
        return 0
    result = session.exec(
        INSERT_TIP_ASSIGNMENTS_SQL,
        params={
            "consejo_id": consejo_id,
            "usuario_ids": [str(usuario_id) for usuario_id in usuario_ids],
        },
    )
    return max(result.rowcount, 0)


def list_user_tips(
    session: Session,
    usuario_id: UUID,
    hogar_id: UUID,
    pending_created_after: datetime,
    completed_after: datetime,
) -> list[UserTipRow]:
    """Consejos de la persona en `hogar_id` (RN-XV-03, RN-XV-05, R-01).

    Primero las pendientes con consejo creado después de `pending_created_after`, por prioridad
    (alta, media, baja) y luego created_at desc, id desc; después las completadas después de
    `completed_after`, por completada_en desc, id desc. ValueError si alguna fecha no tiene zona
    horaria (sin SQL). Sin commit.
    """
    if pending_created_after.utcoffset() is None or completed_after.utcoffset() is None:
        raise ValueError("`pending_created_after` y `completed_after` deben llevar zona horaria.")
    result = session.exec(
        USER_TIPS_SQL,
        params={
            "usuario_id": usuario_id,
            "hogar_id": hogar_id,
            "pending_created_after": pending_created_after,
            "completed_after": completed_after,
        },
    )
    return [_to_user_tip_row(row) for row in result.mappings().all()]


def get_user_tip(
    session: Session, usuario_id: UUID, hogar_id: UUID, consejo_id: UUID
) -> UserTipRow | None:
    """El consejo `consejo_id` de la persona en `hogar_id`; None si no tiene esa fila (RN-XV-03).

    Sin filtro de vigencia. Un consejo de otro hogar o de otra persona → None (R-01). Sin commit.
    """
    result = session.exec(
        USER_TIP_SQL,
        params={"usuario_id": usuario_id, "hogar_id": hogar_id, "consejo_id": consejo_id},
    )
    row = result.mappings().first()
    return None if row is None else _to_user_tip_row(row)


def update_user_tip_status(
    session: Session,
    usuario_id: UUID,
    hogar_id: UUID,
    consejo_id: UUID,
    estado: str,
    completada_en: datetime | None,
) -> bool:
    """Cambia el estado del consejo para la persona; True si actualizó su fila (RN-XV-03, R-01).

    Solo la fila de esa persona y de un consejo de `hogar_id`; también updated_at = now().
    ValueError, sin SQL, si `estado` no es 'pendiente' ni 'completada', si no es coherente con
    `completada_en` (pendiente ↔ None, completada ↔ fecha; check consejos_usuario_estado_coherente)
    o si la fecha no tiene zona horaria. Sin commit.
    """
    if estado not in TIP_STATES:
        raise ValueError("`estado` debe ser 'pendiente' o 'completada'.")
    if (estado == "completada") != (completada_en is not None):
        raise ValueError("`completada_en` solo va, y es obligatoria, en 'completada'.")
    if completada_en is not None and completada_en.utcoffset() is None:
        raise ValueError("`completada_en` debe llevar zona horaria.")
    result = session.exec(
        UPDATE_USER_TIP_STATUS_SQL,
        params={
            "usuario_id": usuario_id,
            "hogar_id": hogar_id,
            "consejo_id": consejo_id,
            "estado": estado,
            "completada_en": completada_en,
        },
    )
    return result.rowcount > 0


def _to_tip_history_row(row: Mapping[str, Any]) -> TipHistoryRow:
    """Convierte la fila de LATEST_TIPS_SQL (zona_id nulo en los generales)."""
    zona_id = row["zona_id"]
    return TipHistoryRow(
        regla_origen=row["regla_origen"],
        zona_id=None if zona_id is None else as_uuid(zona_id),
        titulo=row["titulo"],
        created_at=row["created_at"],
    )


def _to_user_tip_row(row: Mapping[str, Any]) -> UserTipRow:
    """Convierte la fila: ids a UUID; zona_id, zona_tipo y completada_en pueden ser NULL."""
    zona_id = row["zona_id"]
    return UserTipRow(
        id=as_uuid(row["id"]),
        categoria=row["categoria"],
        prioridad=row["prioridad"],
        titulo=row["titulo"],
        descripcion=row["descripcion"],
        zona_id=None if zona_id is None else as_uuid(zona_id),
        zona_tipo=row["zona_tipo"],
        estado=row["estado"],
        completada_en=row["completada_en"],
        created_at=row["created_at"],
    )
