"""Consultas de alertas (alertas) y de su entrega y lectura por persona (alertas_usuario).

RN-XIV-05, RN-XIV-08, DC-25, RN-VI-02, RN-VI-04, RN-VI-05. Sentencias constantes con parámetros
con nombre; sin commit (la transacción es del servicio). Toda consulta filtra por `hogar_id`
(R-01): una alerta de otro hogar nunca se devuelve, se cuenta ni se marca.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from app.data._convert import as_uuid

# RN-XIV-08, DC-25, A-01: cuáles de las claves pedidas ya tienen alerta en el hogar. Usa el único
# de alertas.clave_evento.
EXISTING_EVENT_KEYS_SQL = text(
    """
    select clave_evento
      from alertas
     where hogar_id = :hogar_id
       and clave_evento = any(cast(:claves as text[]))
    """
)

# RN-XIV-08, DC-25: alta de una alerta. El único de clave_evento descarta la repetida (carrera
# entre dos recuperaciones del mismo hogar) sin abortar la transacción: no devuelve fila. I-01:
# una zona de otro hogar tampoco produce fila. created_at y updated_at = momento del evento (fin
# de la hora; cierre: 00:00 del día 1).
INSERT_ALERT_SQL = text(
    """
    insert into alertas (hogar_id, categoria, severidad, titulo, mensaje, zona_id,
                         regla_origen, clave_evento, created_at, updated_at)
    select cast(:hogar_id as uuid), :categoria, :severidad, :titulo, :mensaje,
           cast(:zona_id as uuid), :regla_origen, :clave_evento,
           cast(:created_at as timestamptz), cast(:created_at as timestamptz)
     where cast(:zona_id as uuid) is null
        or exists (
             select 1
               from zonas z
              where z.id = cast(:zona_id as uuid)
                and z.hogar_id = cast(:hogar_id as uuid)
           )
    on conflict (clave_evento) do nothing
    returning id
    """
)

# RN-VI-02, RN-VI-04, RN-XIV-06: una entrega sin leer por destinatario, en una sola sentencia. Solo
# miembros activos del hogar de la alerta (R-01); la repetida se descarta por la clave primaria.
INSERT_ALERT_DELIVERIES_SQL = text(
    """
    insert into alertas_usuario (alerta_id, usuario_id)
    select a.id, m.usuario_id
      from unnest(cast(:usuario_ids as uuid[])) as u (usuario_id)
      join alertas a on a.id = cast(:alerta_id as uuid)
      join hogar_miembros m on m.hogar_id = a.hogar_id
                           and m.usuario_id = u.usuario_id
                           and m.estado = 'activo'
    on conflict (alerta_id, usuario_id) do nothing
    """
)

# RN-XIV-05, RN-VI-05, R-01: alertas entregadas a la persona en ese hogar. Las leídas en
# :read_after o antes se ocultan (como consejos); las no leídas, nunca. Entra por ix_alertas_usuario_lectura.
_USER_ALERTS_BASE = """
    select a.id,
           a.categoria,
           a.severidad,
           a.titulo,
           a.mensaje,
           a.zona_id,
           z.tipo as zona_tipo,
           a.created_at,
           au.leida_en
      from alertas_usuario au
      join alertas a on a.id = au.alerta_id
      left join zonas z on z.id = a.zona_id
     where au.usuario_id = :usuario_id
       and a.hogar_id = :hogar_id
       and (au.leida_en is null or au.leida_en > :read_after)
    """
_USER_ALERTS_ORDER = """
     order by a.created_at desc, a.id desc
     limit :limite
    """
USER_ALERTS_SQL = text(_USER_ALERTS_BASE + _USER_ALERTS_ORDER)
USER_ALERTS_BY_CATEGORY_SQL = text(
    _USER_ALERTS_BASE + "   and a.categoria = :categoria\n" + _USER_ALERTS_ORDER
)

# RN-XIV-05, RN-VI-05: cuántas alertas sin leer tiene la persona en ese hogar.
COUNT_UNREAD_ALERTS_SQL = text(
    """
    select count(*) as total
      from alertas_usuario au
      join alertas a on a.id = au.alerta_id
     where au.usuario_id = :usuario_id
       and a.hogar_id = :hogar_id
       and au.leida_en is null
    """
)

# RN-VI-05: marca como leídas solo las entregas de la persona, de alertas de ese hogar y aún sin
# leer (una ya leída conserva su fecha). updated_at lo fija el trigger trg_alertas_usuario.
MARK_ALERTS_READ_SQL = text(
    """
    update alertas_usuario au
       set leida_en = :read_at
      from alertas a
     where a.id = au.alerta_id
       and a.hogar_id = :hogar_id
       and au.usuario_id = :usuario_id
       and au.alerta_id = any(cast(:alerta_ids as uuid[]))
       and au.leida_en is null
    """
)


@dataclass(frozen=True)
class UserAlertRow:
    """Alerta entregada a una persona, con el tipo de su zona y su lectura (RN-XIV, RN-VI-05)."""

    id: UUID
    categoria: str
    severidad: str
    titulo: str
    mensaje: str
    zona_id: UUID | None
    zona_tipo: str | None  # None si la alerta no es de una zona
    created_at: datetime
    leida_en: datetime | None  # None = sin leer


def list_existing_event_keys(session: Session, hogar_id: UUID, keys: Sequence[str]) -> set[str]:
    """Las claves de `keys` que ya tienen alerta en `hogar_id` (RN-XIV-08, DC-25, A-01, R-01).

    `keys` vacío → set() sin SQL. Sin commit.
    """
    if not keys:
        return set()
    result = session.exec(
        EXISTING_EVENT_KEYS_SQL,
        params={"hogar_id": hogar_id, "claves": list(keys)},
    )
    return {row["clave_evento"] for row in result.mappings().all()}


def insert_alert(
    session: Session,
    *,
    hogar_id: UUID,
    categoria: str,
    severidad: str,
    titulo: str,
    mensaje: str,
    zona_id: UUID | None,
    regla_origen: str,
    clave_evento: str,
    created_at: datetime,
) -> UUID | None:
    """Crea la alerta del hogar y devuelve su id (RN-XIV-08, DC-25).

    `ON CONFLICT (clave_evento) DO NOTHING`: None si la clave ya existía (A-01). También None si
    `zona_id` no es una zona de `hogar_id` (I-01). created_at y updated_at = `created_at`, el
    momento del evento (fin de la hora; cierre: 00:00 del día 1).
    ValueError si `created_at` no tiene zona horaria (sin SQL). Sin commit.
    """
    if created_at.utcoffset() is None:
        raise ValueError("`created_at` debe llevar zona horaria.")
    result = session.exec(
        INSERT_ALERT_SQL,
        params={
            "hogar_id": hogar_id,
            "categoria": categoria,
            "severidad": severidad,
            "titulo": titulo,
            "mensaje": mensaje,
            "zona_id": zona_id,
            "regla_origen": regla_origen,
            "clave_evento": clave_evento,
            "created_at": created_at,
        },
    )
    row = result.mappings().first()
    return None if row is None else as_uuid(row["id"])


def insert_alert_deliveries(session: Session, alerta_id: UUID, usuario_ids: Sequence[UUID]) -> int:
    """Entrega la alerta a cada persona, sin leer, en una sola sentencia (RN-VI-02, RN-XIV-06).

    Solo se guardan las de miembros activos del hogar de la alerta (R-01); una entrega repetida
    se descarta (`ON CONFLICT DO NOTHING`). Devuelve cuántas guardó; vacío → 0 sin SQL. Sin commit.
    """
    if not usuario_ids:
        return 0
    result = session.exec(
        INSERT_ALERT_DELIVERIES_SQL,
        params={
            "alerta_id": alerta_id,
            "usuario_ids": [str(usuario_id) for usuario_id in usuario_ids],
        },
    )
    return max(result.rowcount, 0)


def list_user_alerts(
    session: Session,
    usuario_id: UUID,
    hogar_id: UUID,
    categoria: str | None,
    limite: int,
    read_after: datetime,
) -> list[UserAlertRow]:
    """Alertas de la persona en `hogar_id`, de la más reciente a la más antigua (RN-XIV-05, R-01).

    Excluye las leídas en `read_after` o antes: visible si `leida_en is null or leida_en >
    read_after`, igual que consejos (las no leídas siempre salen). `categoria` None → todas.
    Orden created_at desc, id desc; como máximo `limite`. ValueError si `read_after` no tiene zona
    horaria o si `limite < 1` (sin SQL). Sin commit.
    """
    if read_after.utcoffset() is None:
        raise ValueError("`read_after` debe llevar zona horaria.")
    if limite < 1:
        raise ValueError("`limite` debe ser al menos 1.")
    params: dict[str, Any] = {
        "usuario_id": usuario_id,
        "hogar_id": hogar_id,
        "read_after": read_after,
        "limite": limite,
    }
    statement = USER_ALERTS_SQL
    if categoria is not None:
        statement = USER_ALERTS_BY_CATEGORY_SQL
        params["categoria"] = categoria
    result = session.exec(statement, params=params)
    return [_to_user_alert_row(row) for row in result.mappings().all()]


def count_unread_alerts(session: Session, usuario_id: UUID, hogar_id: UUID) -> int:
    """Alertas sin leer de la persona en `hogar_id` (RN-XIV-05, RN-VI-05, R-01). Sin commit."""
    result = session.exec(
        COUNT_UNREAD_ALERTS_SQL,
        params={"usuario_id": usuario_id, "hogar_id": hogar_id},
    )
    row = result.mappings().first()
    return int(row["total"]) if row is not None else 0


def mark_alerts_read(
    session: Session,
    usuario_id: UUID,
    hogar_id: UUID,
    alerta_ids: Sequence[UUID],
    read_at: datetime,
) -> int:
    """Marca como leídas las alertas pedidas de la persona en `hogar_id` (RN-VI-05, R-01).

    Solo filas de esa persona, de alertas de ese hogar y aún sin leer; devuelve cuántas cambió.
    Vacío → 0 sin SQL. ValueError si `read_at` no tiene zona horaria (sin SQL). Sin commit.
    """
    if not alerta_ids:
        return 0
    if read_at.utcoffset() is None:
        raise ValueError("`read_at` debe llevar zona horaria.")
    result = session.exec(
        MARK_ALERTS_READ_SQL,
        params={
            "usuario_id": usuario_id,
            "hogar_id": hogar_id,
            "alerta_ids": [str(alerta_id) for alerta_id in alerta_ids],
            "read_at": read_at,
        },
    )
    return max(result.rowcount, 0)


def _to_user_alert_row(row: Mapping[str, Any]) -> UserAlertRow:
    """Convierte la fila: ids a UUID; zona_id, zona_tipo y leida_en pueden ser NULL."""
    zona_id = row["zona_id"]
    return UserAlertRow(
        id=as_uuid(row["id"]),
        categoria=row["categoria"],
        severidad=row["severidad"],
        titulo=row["titulo"],
        mensaje=row["mensaje"],
        zona_id=None if zona_id is None else as_uuid(zona_id),
        zona_tipo=row["zona_tipo"],
        created_at=row["created_at"],
        leida_en=row["leida_en"],
    )
