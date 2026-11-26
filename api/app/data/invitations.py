"""Consultas de invitaciones_hogar (RN-X-05, RN-X-06, RN-II-01, RN-II-02, DC-41, DC-42).

Solo se guarda el hash del token (RN-X-05): ninguna consulta devuelve `token_hash` y el token en
claro nunca llega a esta capa. Las comparaciones del correo usan `lower()` en ambos lados, igual
que el índice único parcial uq_invitacion_pendiente_hogar_correo (DC-41).

Frontera de vencimiento (RN-X-05: «expirada cuando expira_en es anterior a la hora actual»):
vencida si `expira_en < now`; vigente si `expira_en >= now`.

Sentencias constantes `sqlalchemy.text` con parámetros con nombre; sin commit (la transacción es
del servicio). El correo y el hash nunca se escriben en logs ni en mensajes de error (S-01; el
motor usa `hide_parameters=True`, ver app/data/database.py).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.data._convert import as_uuid

# SQLSTATE de Postgres para violación de unicidad.
_UNIQUE_VIOLATION = "23505"
# Índice único parcial de la migración 0003 (DC-41: una pendiente por hogar y correo).
PENDING_INVITATION_INDEX = "uq_invitacion_pendiente_hogar_correo"

# Estados a los que puede pasar una invitación pendiente (RN-X-05, RN-X-06, DC-42).
RESOLVED_STATES = frozenset({"aceptada", "rechazada", "expirada", "revocada"})

# Columnas de InvitationRow (sin token_hash, RN-X-05).
_INVITATION_COLUMNS = """
    select id,
           hogar_id,
           correo_invitado,
           invitado_por,
           estado,
           expira_en,
           respondida_en,
           created_at
      from invitaciones_hogar
    """

# DC-42, RN-X-05: las pendientes vencidas (expira_en < now) del hogar para ese correo pasan a
# 'expirada' antes de invitar.
EXPIRE_STALE_PENDING_SQL = text(
    """
    update invitaciones_hogar
       set estado = 'expirada'
     where hogar_id = :hogar_id
       and lower(correo_invitado) = lower(:correo)
       and estado = 'pendiente'
       and expira_en < :now
    """
)

# DC-42: igual en todos los hogares, para las invitaciones recibidas por ese correo.
EXPIRE_STALE_PENDING_FOR_EMAIL_SQL = text(
    """
    update invitaciones_hogar
       set estado = 'expirada'
     where lower(correo_invitado) = lower(:correo)
       and estado = 'pendiente'
       and expira_en < :now
    """
)

# DC-41: ¿hay una pendiente vigente del hogar para ese correo? (usa el índice único parcial).
HAS_PENDING_INVITATION_SQL = text(
    """
    select 1 as existe
      from invitaciones_hogar
     where hogar_id = :hogar_id
       and lower(correo_invitado) = lower(:correo)
       and estado = 'pendiente'
       and expira_en >= :now
     limit 1
    """
)

# RN-II-02: pendientes vigentes del hogar (cuentan para el límite de 5 junto con los activos).
COUNT_PENDING_INVITATIONS_SQL = text(
    """
    select count(*) as total
      from invitaciones_hogar
     where hogar_id = :hogar_id
       and estado = 'pendiente'
       and expira_en >= :now
    """
)

# RN-X-05, DC-41: invitación nueva en 'pendiente' con el hash del token (nunca el token).
INSERT_INVITATION_SQL = text(
    """
    insert into invitaciones_hogar
           (hogar_id, correo_invitado, invitado_por, token_hash, estado, expira_en, created_at)
    values (:hogar_id, :correo_invitado, :invitado_por, :token_hash, 'pendiente', :expira_en,
            :created_at)
    returning id,
              hogar_id,
              correo_invitado,
              invitado_por,
              estado,
              expira_en,
              respondida_en,
              created_at
    """
)

# RN-X-05, R-01: pendientes vigentes del hogar, las más recientes primero.
LIST_PENDING_INVITATIONS_SQL = text(
    _INVITATION_COLUMNS
    + """
     where hogar_id = :hogar_id
       and estado = 'pendiente'
       and expira_en >= :now
     order by created_at desc, id
    """
)

# RN-X-05, RN-X-06: una invitación por id (el servicio comprueba hogar o correo).
_INVITATION_BY_ID = (
    _INVITATION_COLUMNS
    + """
     where id = :invitacion_id
    """
)
INVITATION_BY_ID_SQL = text(_INVITATION_BY_ID)
# Igual, bloqueando la fila hasta el fin de la transacción (revocar, aceptar, rechazar).
INVITATION_BY_ID_FOR_UPDATE_SQL = text(_INVITATION_BY_ID + " for update")

# RN-X-05: búsqueda por el hash del token del enlace (token_hash es único).
INVITATION_BY_TOKEN_HASH_SQL = text(
    _INVITATION_COLUMNS
    + """
     where token_hash = :token_hash
    """
)

# RN-X-06, DC-42: solo una invitación todavía pendiente cambia de estado.
SET_INVITATION_STATE_SQL = text(
    """
    update invitaciones_hogar
       set estado = :estado,
           respondida_en = :respondida_en
     where id = :invitacion_id
       and estado = 'pendiente'
    returning id
    """
)

# RN-X-06: proyección de una invitación recibida con el nombre del hogar y de quien invitó. Si
# quien invitó eliminó su cuenta (invitado_por nulo, DC-36), se usa el nombre del administrador
# activo actual del hogar (como máximo uno por uq_miembros_admin_activo).
# TODO(pendiente: nombre de invitado_por_nombre cuando invitado_por es null (DC-36); el contrato
# lo exige y ninguna fuente lo define; hoy: el administrador activo actual)
_RECEIVED_INVITATION_SELECT = """
    select i.id,
           i.hogar_id,
           h.nombre as hogar_nombre,
           coalesce(u.nombre_completo, adm.nombre_completo) as invitado_por_nombre,
           i.expira_en
      from invitaciones_hogar i
      join hogares h on h.id = i.hogar_id
      left join usuarios u on u.id = i.invitado_por
      left join lateral (
             select ua.nombre_completo
               from hogar_miembros m
               join usuarios ua on ua.id = m.usuario_id
              where m.hogar_id = i.hogar_id
                and m.rol = 'administrador'
                and m.estado = 'activo'
              limit 1
           ) adm on true
    """

# RN-X-06, DC-42: pendientes vigentes dirigidas al correo de la persona autenticada.
LIST_RECEIVED_INVITATIONS_SQL = text(
    _RECEIVED_INVITATION_SELECT
    + """
     where lower(i.correo_invitado) = lower(:correo)
       and i.estado = 'pendiente'
       and i.expira_en >= :now
     order by i.created_at desc, i.id
    """
)

# RN-X-06: misma proyección por id (el servicio ya comprobó correo, estado y vigencia).
RECEIVED_INVITATION_BY_ID_SQL = text(
    _RECEIVED_INVITATION_SELECT
    + """
     where i.id = :invitacion_id
    """
)


InvitationState = Literal["pendiente", "aceptada", "rechazada", "expirada", "revocada"]
ResolvedInvitationState = Literal["aceptada", "rechazada", "expirada", "revocada"]


@dataclass(frozen=True)
class InvitationRow:
    """Fila de invitaciones_hogar sin el hash del token (RN-X-05)."""

    id: UUID
    hogar_id: UUID
    correo_invitado: str
    invitado_por: UUID | None  # None si quien invitó eliminó su cuenta (DC-36)
    estado: InvitationState
    expira_en: datetime
    respondida_en: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ReceivedInvitationRow:
    """Invitación recibida con el nombre del hogar y de quien invitó (RN-X-06)."""

    id: UUID
    hogar_id: UUID
    hogar_nombre: str
    invitado_por_nombre: str | None  # None si no hay invitador ni administrador con ficha
    expira_en: datetime


class PendingInvitationExistsError(Exception):
    """Ya hay una invitación pendiente del hogar para ese correo (23505 del índice DC-41).

    Caso: dos invitaciones simultáneas al mismo correo. El servicio la traduce a 409.
    """


def expire_stale_pending(session: Session, hogar_id: UUID, correo: str, now: datetime) -> int:
    """Pasa a 'expirada' las pendientes vencidas (`expira_en < now`) del hogar para el correo.

    DC-42: se ejecuta antes de comprobar si ya hay una pendiente, para que una vencida no bloquee
    una invitación nueva por el índice único. Compara `lower()` en ambos lados (DC-41). Filtra por
    hogar (R-01). Devuelve cuántas filas cambió. Sin commit.
    """
    result = session.exec(
        EXPIRE_STALE_PENDING_SQL,
        params={"hogar_id": hogar_id, "correo": correo, "now": now},
    )
    return result.rowcount


def expire_stale_pending_for_email(session: Session, correo: str, now: datetime) -> int:
    """Como `expire_stale_pending`, pero en todos los hogares (listar recibidas, DC-42).

    Solo toca invitaciones dirigidas al correo de la persona autenticada. Devuelve cuántas filas
    cambió. Sin commit.
    """
    result = session.exec(
        EXPIRE_STALE_PENDING_FOR_EMAIL_SQL,
        params={"correo": correo, "now": now},
    )
    return result.rowcount


def has_pending_invitation(session: Session, hogar_id: UUID, correo: str, now: datetime) -> bool:
    """True si el hogar tiene una pendiente vigente (`expira_en >= now`) para el correo (DC-41)."""
    result = session.exec(
        HAS_PENDING_INVITATION_SQL,
        params={"hogar_id": hogar_id, "correo": correo, "now": now},
    )
    return result.mappings().first() is not None


def count_pending_invitations(session: Session, hogar_id: UUID, now: datetime) -> int:
    """Pendientes vigentes (`expira_en >= now`) del hogar (RN-II-02: límite de 5 con los activos)."""
    result = session.exec(
        COUNT_PENDING_INVITATIONS_SQL,
        params={"hogar_id": hogar_id, "now": now},
    )
    row = result.mappings().first()
    return int(row["total"]) if row is not None else 0


def insert_invitation(
    session: Session,
    *,
    hogar_id: UUID,
    correo_invitado: str,
    invitado_por: UUID,
    token_hash: str,
    expira_en: datetime,
    created_at: datetime,
) -> InvitationRow:
    """Crea la invitación en 'pendiente' con el hash del token (RN-X-05, DC-41).

    El correo se guarda tal como llega (el servicio ya lo normalizó con strip y lower).
    PendingInvitationExistsError si viola uq_invitacion_pendiente_hogar_correo (SQLSTATE 23505);
    cualquier otra IntegrityError sube tal cual. La transacción queda abortada. Sin commit.
    """
    try:
        result = session.exec(
            INSERT_INVITATION_SQL,
            params={
                "hogar_id": hogar_id,
                "correo_invitado": correo_invitado,
                "invitado_por": invitado_por,
                "token_hash": token_hash,
                "expira_en": expira_en,
                "created_at": created_at,
            },
        )
    except IntegrityError as exc:
        if _violates_pending_invitation_index(exc):
            # `from None`: el detalle de Postgres lleva el correo invitado (S-01).
            raise PendingInvitationExistsError(
                "Ya hay una invitación pendiente para ese correo."
            ) from None
        raise
    return _to_invitation_row(result.mappings().one())


def list_pending_invitations(
    session: Session, hogar_id: UUID, now: datetime
) -> list[InvitationRow]:
    """Pendientes vigentes (`expira_en >= now`) del hogar, recientes primero y luego por id.

    RN-X-05, R-01: filtra por hogar. Sin commit.
    """
    result = session.exec(
        LIST_PENDING_INVITATIONS_SQL,
        params={"hogar_id": hogar_id, "now": now},
    )
    return [_to_invitation_row(row) for row in result.mappings().all()]


def get_invitation(
    session: Session, invitacion_id: UUID, *, for_update: bool = False
) -> InvitationRow | None:
    """La invitación con ese id (cualquier estado); None si no existe (RN-X-05, RN-X-06).

    No filtra por hogar ni por correo: el servicio compara `hogar_id` (revocar) o el correo
    (aceptar, rechazar) antes de responder. Con `for_update=True` bloquea la fila. Sin commit.
    """
    statement = INVITATION_BY_ID_FOR_UPDATE_SQL if for_update else INVITATION_BY_ID_SQL
    result = session.exec(statement, params={"invitacion_id": invitacion_id})
    row = result.mappings().first()
    return None if row is None else _to_invitation_row(row)


def get_invitation_by_token_hash(session: Session, token_hash: str) -> InvitationRow | None:
    """La invitación cuyo `token_hash` coincide (RN-X-05); None si no existe. Sin commit."""
    result = session.exec(INVITATION_BY_TOKEN_HASH_SQL, params={"token_hash": token_hash})
    row = result.mappings().first()
    return None if row is None else _to_invitation_row(row)


def set_invitation_state(
    session: Session,
    invitacion_id: UUID,
    estado: ResolvedInvitationState,
    respondida_en: datetime | None,
) -> bool:
    """Cambia el estado de una invitación que sigue 'pendiente' (RN-X-06, DC-42).

    `UPDATE ... WHERE id = :invitacion_id AND estado = 'pendiente'`: True si cambió una fila.
    ValueError si `estado` no es aceptada, rechazada, expirada o revocada. Sin commit.
    """
    if estado not in RESOLVED_STATES:
        raise ValueError("Estado de invitación no permitido.")
    result = session.exec(
        SET_INVITATION_STATE_SQL,
        params={"invitacion_id": invitacion_id, "estado": estado, "respondida_en": respondida_en},
    )
    return result.mappings().first() is not None


def list_received_invitations(
    session: Session, correo: str, now: datetime
) -> list[ReceivedInvitationRow]:
    """Pendientes vigentes (`expira_en >= now`) dirigidas a `correo`, recientes primero (RN-X-06).

    El correo se compara con lower() en ambos lados. Une hogares (nombre). `invitado_por_nombre` es el nombre de quien invitó o, si eliminó su
    cuenta, el del administrador activo actual del hogar. Sin commit.
    """
    result = session.exec(
        LIST_RECEIVED_INVITATIONS_SQL,
        params={"correo": correo, "now": now},
    )
    return [_to_received_invitation_row(row) for row in result.mappings().all()]


def get_received_invitation(session: Session, invitacion_id: UUID) -> ReceivedInvitationRow | None:
    """La misma proyección que `list_received_invitations` para un id; None si no existe.

    No filtra por estado ni correo: el servicio ya lo comprobó (RN-X-06). Sin commit.
    """
    result = session.exec(RECEIVED_INVITATION_BY_ID_SQL, params={"invitacion_id": invitacion_id})
    row = result.mappings().first()
    return None if row is None else _to_received_invitation_row(row)


def _violates_pending_invitation_index(exc: IntegrityError) -> bool:
    """True si el error es el 23505 de uq_invitacion_pendiente_hogar_correo.

    El nombre sale de `diag.constraint_name`; si el controlador no lo trae, del mensaje.
    """
    if getattr(exc.orig, "pgcode", None) != _UNIQUE_VIOLATION:
        return False
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name is not None:
        return constraint_name == PENDING_INVITATION_INDEX
    return PENDING_INVITATION_INDEX in str(exc.orig)


def _to_invitation_row(row: Mapping[str, Any]) -> InvitationRow:
    """Convierte una fila de invitaciones_hogar en InvitationRow (ids a UUID)."""
    invitado_por = row["invitado_por"]
    return InvitationRow(
        id=as_uuid(row["id"]),
        hogar_id=as_uuid(row["hogar_id"]),
        correo_invitado=row["correo_invitado"],
        invitado_por=None if invitado_por is None else as_uuid(invitado_por),
        estado=row["estado"],
        expira_en=row["expira_en"],
        respondida_en=row["respondida_en"],
        created_at=row["created_at"],
    )


def _to_received_invitation_row(row: Mapping[str, Any]) -> ReceivedInvitationRow:
    """Convierte una fila de la proyección de recibidas en ReceivedInvitationRow."""
    return ReceivedInvitationRow(
        id=as_uuid(row["id"]),
        hogar_id=as_uuid(row["hogar_id"]),
        hogar_nombre=row["hogar_nombre"],
        invitado_por_nombre=row["invitado_por_nombre"],
        expira_en=row["expira_en"],
    )
