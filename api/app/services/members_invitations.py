"""Casos de uso de la etiqueta «Miembros e invitaciones» (fase 9).

Reglas: RN-II-01..04 (membresía, roles y límite de 5), RN-X-05..08 (invitar, aceptar, rechazar,
revocar, salir, expulsar, transferir y permisos), RN-IX-03 y DC-04 (correo de invitación),
RN-XIV-06/07/08, RN-VI-02 y DC-25 (alerta «Nuevo miembro»), DC-41 y DC-42 (una pendiente por
hogar y correo; las vencidas se marcan 'expirada' antes de comprobar).

Manejan la transacción: la sesión llega del router (la misma de las dependencias de seguridad);
cada operación que escribe hace `session.commit()` al final y, si algo lanza antes, la sesión se
cierra sin commit (rollback). La autorización básica ya viene de `app.security`; la «guardia de
gestión» (`_lock_admin`) la vuelve a comprobar BAJO BLOQUEO por si hubo una transferencia entre
la dependencia y el caso de uso.

ORDEN DE BLOQUEO ÚNICO DEL PROYECTO: hogar (`lock_household`) → fila(s) de hogar_miembros
(FOR UPDATE) → fila de usuarios (FOR UPDATE). Nunca se pide un nivel anterior teniendo uno
posterior.

Seguridad (RN-X-05, S-01, S-02): en la base solo se guarda el hash del token; el token en claro
solo vive en memoria y en el enlace del correo (o del log en local, DC-04). Ningún log de este
módulo lleva correos, tokens, hashes ni ids.
"""

import logging
from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from sqlmodel import Session

from app.config import Settings
from app.data import alerts as alerts_data
from app.data import households as households_data
from app.data import invitations as invitations_data
from app.data import memberships as memberships_data
from app.data import users as users_data
from app.domain import alert_rules
from app.domain.formats import render_invitation_email
from app.domain.simulator import TIMEZONE
from app.errors import NOT_FOUND_MESSAGE, ApiError, CodigoError
from app.schemas.households import Permisos, PermisosActualizar
from app.schemas.members_invitations import (
    InvitacionCrear,
    InvitacionesRecibidasLista,
    InvitacionPendiente,
    InvitacionRecibida,
    InvitacionToken,
    Miembro,
    MiembrosHogar,
)
from app.schemas.users import MembresiaResumen
from app.security.invitation_tokens import generate_invitation_token, hash_invitation_token
from app.services import email as email_service
from app.services._alert_delivery import insert_planned_alert, present_members
from app.services.backend_texts import get_backend_texts

# RN-X-05: la invitación vence a los 7 días.
INVITATION_VALIDITY = timedelta(days=7)
# RN-II-02: máximo 5 miembros activos (al invitar cuentan también las pendientes vigentes).
MAX_MEMBERS = 5
# D2 (decisión de Nicolás, 25/11/2026; contrato 0.2.10): máximo 20 invitaciones CREADAS por hogar
# en el día de Bogotá, en cualquier estado.
MAX_DAILY_INVITATIONS = 20

# Mensajes técnicos y cortos: la app decide el texto por `codigo`.
NOT_ADMIN_MESSAGE = "Solo el administrador puede hacer esta operación."
ADMIN_DEBE_TRANSFERIR_MESSAGE = "El administrador debe transferir la administración antes de salir."
ADMIN_UNICO_MIEMBRO_MESSAGE = "El administrador es el único miembro: debe eliminar su cuenta."
VALIDACION_MESSAGE = "Los datos enviados no cumplen las reglas."
EMPTY_PATCH_MESSAGE = "Envía al menos un campo."
NOT_NULL_MESSAGE = "El campo no admite null."
SELF_TRANSFER_MESSAGE = "No puedes transferirte la administración a ti mismo."
YA_ES_MIEMBRO_MESSAGE = "El correo pertenece a un miembro activo del hogar."
PENDING_EXISTS_MESSAGE = "Ya hay una invitación pendiente para ese correo en este hogar."
LIMIT_MESSAGE = "El hogar alcanzó el límite de 5 miembros."
DAILY_LIMIT_MESSAGE = "El hogar alcanzó el límite de 20 invitaciones por día."
NOT_PENDING_MESSAGE = "La invitación ya no está pendiente."
EXPIRED_MESSAGE = "La invitación venció."
EMAIL_MISMATCH_MESSAGE = "La invitación es para otro correo."
ACTIVE_MEMBERSHIP_MESSAGE = "El usuario ya pertenece a un hogar."
INCONSISTENT_MESSAGE = "Estado inconsistente del hogar o de la invitación."
NAMELESS_INVITATIONS_MESSAGE = "Se omitieron %d invitaciones recibidas sin nombre de quien invita."

logger = logging.getLogger(__name__)


# --- miembros -----------------------------------------------------------------------------


def list_members(
    session: Session, user_id: UUID, hogar_id: UUID, now: datetime | None = None
) -> MiembrosHogar:
    """`listarMiembros`: miembros activos, invitaciones pendientes y permisos (RN-XVI-07, RN-X-08).

    Sin bloqueo ni commit. Solo el administrador recibe las invitaciones pendientes; para los
    demás `invitaciones_pendientes` es null (contrato, sección 7.3).
    """
    moment = _now(now)
    own = memberships_data.get_user_membership_in_household(session, hogar_id, user_id)
    if own is None:  # la dependencia ya lo garantiza; defensa en profundidad
        raise _not_found()
    return _members_view(session, hogar_id, own.rol == "administrador", moment)


def update_permissions(
    session: Session, user_id: UUID, hogar_id: UUID, payload: PermisosActualizar
) -> Permisos:
    """`actualizarPermisos`: cambia solo los permisos enviados (RN-II-03, RN-X-08).

    Afectan por igual a todos los miembros; el administrador conserva acceso total. `{}` o un null
    dan 422 `VALIDACION` sin tocar la base.
    """
    _lock_admin(session, user_id, hogar_id)
    changes = {field: getattr(payload, field) for field in sorted(payload.model_fields_set)}
    if not changes:
        raise _validation_error(["body"], EMPTY_PATCH_MESSAGE)
    for field, value in changes.items():
        if value is None:
            raise _validation_error(["body", field], NOT_NULL_MESSAGE)
    row = households_data.update_permissions(session, hogar_id, changes)
    if row is None:
        raise _not_found()
    permisos = _to_permisos(row)
    session.commit()
    return permisos


def leave_household(
    session: Session, user_id: UUID, hogar_id: UUID, now: datetime | None = None
) -> None:
    """`salirDelHogar`: la membresía pasa a 'inactivo' con `fecha_salida` (RN-II-04, RN-X-07).

    El administrador no puede salir: 409 `ADMIN_DEBE_TRANSFERIR` si hay otros miembros activos y
    409 `ADMIN_UNICO_MIEMBRO` si es el único (debe eliminar su cuenta).
    """
    moment = _now(now)
    households_data.lock_household(session, hogar_id)
    own = memberships_data.get_user_membership_in_household(
        session, hogar_id, user_id, for_update=True
    )
    if own is None:
        raise _not_found()
    if own.rol == "administrador":
        raise _admin_cannot_leave(session, hogar_id, user_id)
    memberships_data.close_membership(session, own.membresia_id, moment)
    session.commit()


def remove_member(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    membresia_id: UUID,
    now: datetime | None = None,
) -> None:
    """`expulsarMiembro`: la membresía pasa a 'inactivo' con `fecha_salida` (RN-II-04, RN-X-07).

    Solo el administrador. Membresía inexistente, de otro hogar o inactiva → 404. Expulsarse a
    sí mismo → los mismos 409 que salir del hogar.
    """
    moment = _now(now)
    own = _lock_admin(session, user_id, hogar_id)
    target = memberships_data.get_household_membership(
        session, hogar_id, membresia_id, for_update=True
    )
    if target is None or target.estado != "activo":
        raise _not_found()
    if target.membresia_id == own.membresia_id:
        raise _admin_cannot_leave(session, hogar_id, user_id)
    memberships_data.close_membership(session, target.membresia_id, moment)
    session.commit()


def transfer_admin(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    membresia_id: UUID,
    now: datetime | None = None,
) -> MiembrosHogar:
    """`transferirAdministracion`: el destino pasa a administrador y quien llama a miembro.

    RN-II-04, RN-X-07. El destino no tiene que aceptar. Primero se baja al administrador actual y
    luego se sube al destino (índice único de un administrador activo por hogar). Destino
    inexistente o inactivo → 404; la propia membresía → 422 `VALIDACION` en `membresia_id`.
    Devuelve la vista ya como miembro (sin invitaciones y sin gestión).
    """
    moment = _now(now)
    own = _lock_admin(session, user_id, hogar_id)
    target = memberships_data.get_household_membership(
        session, hogar_id, membresia_id, for_update=True
    )
    if target is None or target.estado != "activo":
        raise _not_found()
    if target.membresia_id == own.membresia_id:
        raise _validation_error(["path", "membresia_id"], SELF_TRANSFER_MESSAGE)
    memberships_data.set_membership_role(session, own.membresia_id, "miembro")
    memberships_data.set_membership_role(session, target.membresia_id, "administrador")
    # La vista se arma antes del commit: después de confirmar ya nada puede fallar.
    view = _members_view(session, hogar_id, False, moment)
    session.commit()
    return view


# --- invitaciones (administrador) -----------------------------------------------------------


def create_invitation(
    session: Session,
    settings: Settings,
    user_id: UUID,
    hogar_id: UUID,
    payload: InvitacionCrear,
    now: datetime | None = None,
) -> InvitacionPendiente:
    """`crearInvitacion`: invitación de 7 días y correo con el enlace (RN-X-05, RN-IX-03, DC-04).

    Orden: guardia → correo en minúsculas → vencidas a 'expirada' (DC-42) → 409 `YA_ES_MIEMBRO`
    → 409 `INVITACION_PENDIENTE_EXISTENTE` → 409 `LIMITE_MIEMBROS` (activos + pendientes ≥ 5) →
    409 `LIMITE_INVITACIONES_DIARIO` (ya hay 20 creadas hoy en el día de Bogotá, en cualquier
    estado; D2) → token (solo se guarda su hash) → correo ANTES del commit. Si el envío falla,
    rollback y la excepción sube (500 `ERROR_INTERNO`, declarado en el contrato 0.2.10);
    reintentar es seguro porque no queda nada guardado.
    Si el correo tiene un hogar activo en otro lugar, la invitación se crea igual (contrato).
    """
    moment = _now(now)
    _lock_admin(session, user_id, hogar_id)
    correo = payload.correo_invitado.strip().lower()
    invitations_data.expire_stale_pending(session, hogar_id, correo, moment)
    if memberships_data.is_active_member_email(session, hogar_id, correo):
        raise ApiError(409, CodigoError.YA_ES_MIEMBRO, YA_ES_MIEMBRO_MESSAGE)
    if invitations_data.has_pending_invitation(session, hogar_id, correo, moment):
        raise _pending_exists()
    active = memberships_data.count_active_members(session, hogar_id)
    pending = invitations_data.count_pending_invitations(session, hogar_id, moment)
    if active + pending >= MAX_MEMBERS:
        raise _limit_reached()
    day_start, day_end = _bogota_day_bounds(moment)
    created_today = invitations_data.count_invitations_created_between(
        session, hogar_id, day_start, day_end
    )
    if created_today >= MAX_DAILY_INVITATIONS:
        raise ApiError(409, CodigoError.LIMITE_INVITACIONES_DIARIO, DAILY_LIMIT_MESSAGE)

    token, token_hash = generate_invitation_token()
    try:
        invitation = invitations_data.insert_invitation(
            session,
            hogar_id=hogar_id,
            correo_invitado=correo,
            invitado_por=user_id,
            token_hash=token_hash,
            expira_en=moment + INVITATION_VALIDITY,
            created_at=moment,
        )
    except invitations_data.PendingInvitationExistsError:
        raise _pending_exists() from None

    inviter = users_data.get_user_profile(session, user_id)
    household = households_data.get_household(session, hogar_id)
    if inviter is None or household is None:
        raise RuntimeError(INCONSISTENT_MESSAGE)  # 500 ERROR_INTERNO (contrato 0.2.10)
    enlace = settings.invitation_link_base + token
    email = render_invitation_email(
        get_backend_texts(),
        invitador=inviter.nombre_completo,
        hogar=household.nombre,
        correo=correo,
        expira_en=invitation.expira_en,
        enlace=enlace,
    )
    try:
        email_service.send_invitation_email(
            settings, correo_invitado=correo, email=email, enlace=enlace
        )
    except email_service.EmailDeliveryError:
        # 500 ERROR_INTERNO (contrato 0.2.10). Reintentar es seguro: no queda invitación.
        session.rollback()
        raise
    session.commit()
    return InvitacionPendiente(
        id=invitation.id,
        correo_invitado=invitation.correo_invitado,
        estado="pendiente",
        expira_en=invitation.expira_en,
    )


def revoke_invitation(
    session: Session,
    user_id: UUID,
    hogar_id: UUID,
    invitacion_id: UUID,
    now: datetime | None = None,
) -> None:
    """`revocarInvitacion`: la invitación pasa a 'revocada'; no se borra (RN-X-06).

    Inexistente o de otro hogar → 404; no pendiente → 409 `INVITACION_NO_PENDIENTE`; vencida →
    se marca 'expirada', commit y 409 `INVITACION_EXPIRADA` (DC-42).
    """
    moment = _now(now)
    _lock_admin(session, user_id, hogar_id)
    invitation = invitations_data.get_invitation(session, invitacion_id, for_update=True)
    if invitation is None or invitation.hogar_id != hogar_id:
        raise _not_found()
    _ensure_pending(session, invitation, moment)
    invitations_data.set_invitation_state(session, invitation.id, "revocada", None)
    session.commit()


# --- invitaciones (persona invitada) ---------------------------------------------------------


def list_received_invitations(
    session: Session, user_id: UUID, correo: str, now: datetime | None = None
) -> InvitacionesRecibidasLista:
    """`listarInvitacionesRecibidas`: pendientes vigentes para el correo del usuario (RN-X-01).

    Las vencidas se marcan 'expirada' al consultarse y no se devuelven (contrato, DC-42); por
    eso hay commit. `invitado_por_nombre`: quien invitó o, si eliminó su cuenta, el
    administrador actual (capa de datos).
    """
    del user_id  # el correo del token identifica a la persona invitada
    moment = _now(now)
    invitations_data.expire_stale_pending_for_email(session, correo, moment)
    rows = invitations_data.list_received_invitations(session, correo, moment)
    # TODO(pendiente: nombre de invitado_por_nombre cuando invitado_por es null; el contrato lo
    # exige). Sin invitador ni administrador con ficha no se puede mostrar; no debería ocurrir en
    # un hogar vivo. Se omite y queda un aviso sin datos personales.
    invitaciones = [_to_received(row) for row in rows if row.invitado_por_nombre is not None]
    skipped = len(rows) - len(invitaciones)
    if skipped:
        logger.warning(NAMELESS_INVITATIONS_MESSAGE, skipped)
    session.commit()
    return InvitacionesRecibidasLista(invitaciones=invitaciones)


def resolve_invitation_token(
    session: Session,
    user_id: UUID,
    correo: str,
    payload: InvitacionToken,
    now: datetime | None = None,
) -> InvitacionRecibida:
    """`resolverTokenInvitacion`: la invitación del enlace, buscada por el hash (RN-X-05).

    Token desconocido → 404; correo distinto → 403 `CORREO_NO_COINCIDE`; no pendiente → 409
    `INVITACION_NO_PENDIENTE`; vencida → se marca, commit y 409 `INVITACION_EXPIRADA`.
    """
    del user_id
    moment = _now(now)
    invitation = invitations_data.get_invitation_by_token_hash(
        session, hash_invitation_token(payload.token)
    )
    if invitation is None:
        raise _not_found()
    _ensure_same_email(invitation, correo)
    _ensure_pending(session, invitation, moment)
    received = invitations_data.get_received_invitation(session, invitation.id)
    if received is None:
        raise _not_found()
    if received.invitado_por_nombre is None:
        # TODO(pendiente: el contrato no declara 500 en resolverTokenInvitacion; PENDIENTES #29).
        raise RuntimeError(INCONSISTENT_MESSAGE)
    return _to_received(received)


def accept_invitation(
    session: Session,
    user_id: UUID,
    correo: str,
    invitacion_id: UUID,
    now: datetime | None = None,
) -> MembresiaResumen:
    """`aceptarInvitacion`: membresía 'miembro' y alerta «Nuevo miembro» (RN-X-05, RN-X-06).

    Orden (bloqueo hogar → usuario):
    1. Lectura sin bloqueo: inexistente → 404; correo distinto → 403 `CORREO_NO_COINCIDE`.
    2. Hogar bloqueado y relectura FOR UPDATE: no pendiente → 409; vencida → se marca, commit,
       409 `INVITACION_EXPIRADA` (DC-42).
    3. Ficha bloqueada: sin ficha (o eliminándose la cuenta) → 404 `NO_ENCONTRADO` (el contrato
       reserva `FICHA_NO_CREADA` para `/usuarios/me`, components.responses.NoEncontrado).
    4. Membresía activa en cualquier hogar → 409 `MEMBRESIA_ACTIVA_EXISTENTE`.
    5. 5 activos → 409 `LIMITE_MIEMBROS` (RN-II-02; las pendientes no cuentan al aceptar).
    6. Membresía nueva e invitación 'aceptada'.
    7. Alerta «Nuevo miembro» en la misma transacción (RN-XIV-07 (4), DC-25), para los demás
       miembros con permiso e interruptor (RN-VI-02, RN-XIV-06). Si falla, sube sin commit.
    8. Commit.
    """
    moment = _now(now)
    invitation = invitations_data.get_invitation(session, invitacion_id)
    if invitation is None:
        raise _not_found()
    _ensure_same_email(invitation, correo)
    hogar_id = invitation.hogar_id

    households_data.lock_household(session, hogar_id)
    locked = invitations_data.get_invitation(session, invitacion_id, for_update=True)
    if locked is None:
        raise _not_found()
    _ensure_pending(session, locked, moment)

    profile = users_data.lock_user_profile(session, user_id)
    if profile is None:
        raise _not_found()
    if memberships_data.get_active_membership_of_user(session, user_id) is not None:
        raise _active_membership_exists()
    if memberships_data.count_active_members(session, hogar_id) >= MAX_MEMBERS:
        raise _limit_reached()
    try:
        membresia_id = memberships_data.insert_member_membership(
            session, hogar_id=hogar_id, usuario_id=user_id, fecha_ingreso=moment
        )
    except memberships_data.ActiveMembershipExistsError:
        raise _active_membership_exists() from None
    invitations_data.set_invitation_state(session, locked.id, "aceptada", moment)

    _create_new_member_alert(
        session,
        hogar_id=hogar_id,
        membresia_id=membresia_id,
        new_usuario_id=user_id,
        nombre=profile.nombre_completo,
        created_at=moment,
    )
    session.commit()
    return MembresiaResumen(membresia_id=membresia_id, hogar_id=hogar_id, rol="miembro")


def reject_invitation(
    session: Session,
    user_id: UUID,
    correo: str,
    invitacion_id: UUID,
    now: datetime | None = None,
) -> None:
    """`rechazarInvitacion`: la invitación pasa a 'rechazada' con `respondida_en` (RN-X-06).

    Inexistente → 404; correo distinto → 403 (sin bloquear); no pendiente → 409; vencida → se
    marca, commit y 409 `INVITACION_EXPIRADA`.
    """
    del user_id
    moment = _now(now)
    invitation = invitations_data.get_invitation(session, invitacion_id)
    if invitation is None:
        raise _not_found()
    _ensure_same_email(invitation, correo)
    locked = invitations_data.get_invitation(session, invitacion_id, for_update=True)
    if locked is None:
        raise _not_found()
    _ensure_pending(session, locked, moment)
    invitations_data.set_invitation_state(session, locked.id, "rechazada", moment)
    session.commit()


# --- auxiliares ---------------------------------------------------------------------------


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


def _bogota_day_bounds(moment: datetime) -> tuple[datetime, datetime]:
    """[00:00 Bogotá de hoy, 00:00 Bogotá de mañana) para el día de Bogotá de `moment` (D2).

    `moment` sin zona horaria: ValueError (`astimezone` lo tomaría como hora local del servidor).
    """
    if moment.utcoffset() is None:
        raise ValueError("`now` debe llevar zona horaria.")
    today = moment.astimezone(TIMEZONE).date()
    start = datetime.combine(today, time(0), tzinfo=TIMEZONE)
    end = datetime.combine(today + timedelta(days=1), time(0), tzinfo=TIMEZONE)
    return start, end


def _lock_admin(session: Session, user_id: UUID, hogar_id: UUID) -> memberships_data.MembershipRow:
    """Guardia de gestión: hogar bloqueado → membresía propia FOR UPDATE → debe ser administrador.

    Vuelve a comprobar bajo bloqueo lo que ya vio la dependencia (`require_admin`), por si hubo
    una transferencia o una salida entre medias. Sin membresía activa → 404 `NO_ENCONTRADO`; no
    administrador → 403 `NO_ES_ADMINISTRADOR`.
    """
    households_data.lock_household(session, hogar_id)
    own = memberships_data.get_user_membership_in_household(
        session, hogar_id, user_id, for_update=True
    )
    if own is None:
        raise _not_found()
    if own.rol != "administrador":
        raise ApiError(403, CodigoError.NO_ES_ADMINISTRADOR, NOT_ADMIN_MESSAGE)
    return own


def _members_view(session: Session, hogar_id: UUID, is_admin: bool, now: datetime) -> MiembrosHogar:
    """`MiembrosHogar`: miembros activos, pendientes (solo administrador), permisos y gestión."""
    members = memberships_data.list_active_members(session, hogar_id)
    pending = (
        [
            _to_pending(row)
            for row in invitations_data.list_pending_invitations(session, hogar_id, now)
        ]
        if is_admin
        else None
    )
    household = households_data.get_household(session, hogar_id)
    if household is None:
        raise _not_found()
    return MiembrosHogar(
        miembros_activos=len(members),
        miembros=[_to_member(row) for row in members],
        invitaciones_pendientes=pending,
        permisos=_to_permisos(household),
        puede_gestionar=is_admin,
    )


def _admin_cannot_leave(session: Session, hogar_id: UUID, user_id: UUID) -> ApiError:
    """RN-X-07: con otros miembros, transferir primero; solo, eliminar la cuenta."""
    others = memberships_data.count_other_active_members(session, hogar_id, user_id)
    if others > 0:
        return ApiError(409, CodigoError.ADMIN_DEBE_TRANSFERIR, ADMIN_DEBE_TRANSFERIR_MESSAGE)
    return ApiError(409, CodigoError.ADMIN_UNICO_MIEMBRO, ADMIN_UNICO_MIEMBRO_MESSAGE)


def _ensure_same_email(invitation: invitations_data.InvitationRow, correo: str) -> None:
    if invitation.correo_invitado.strip().lower() != correo.strip().lower():
        raise ApiError(403, CodigoError.CORREO_NO_COINCIDE, EMAIL_MISMATCH_MESSAGE)


def _ensure_pending(
    session: Session, invitation: invitations_data.InvitationRow, now: datetime
) -> None:
    """No pendiente → 409; vencida → 'expirada', commit y 409 (DC-42).

    Vencida si `expira_en < now` (RN-X-05: «anterior a la hora actual»); en el instante exacto de
    `expira_en` sigue vigente, igual que en las consultas de app/data/invitations.py.
    """
    if invitation.estado != "pendiente":
        raise ApiError(409, CodigoError.INVITACION_NO_PENDIENTE, NOT_PENDING_MESSAGE)
    if invitation.expira_en < now:
        invitations_data.set_invitation_state(session, invitation.id, "expirada", None)
        session.commit()
        raise ApiError(409, CodigoError.INVITACION_EXPIRADA, EXPIRED_MESSAGE)


def _create_new_member_alert(
    session: Session,
    *,
    hogar_id: UUID,
    membresia_id: UUID,
    new_usuario_id: UUID,
    nombre: str,
    created_at: datetime,
) -> None:
    """Alerta «Nuevo miembro» y su entrega (RN-X-06, RN-XIV-07 (4), RN-VI-02, DC-25).

    Texto resuelto desde `config_files/` (RN-XI-09). Destinatarios: miembros activos que ya
    estaban en `created_at`, con el permiso del hogar (o administrador) y el interruptor de
    consumo encendido, sin el nuevo miembro. Clave `nuevo_miembro:<membresia_id>`.
    """
    household = households_data.get_household(session, hogar_id)
    if household is None:
        raise RuntimeError(INCONSISTENT_MESSAGE)
    alert = alert_rules.plan_new_member_alert(
        get_backend_texts(),
        membresia_id=membresia_id,
        nombre=nombre,
        hogar_nombre=household.nombre,
        created_at=created_at,
    )
    alerta_id = insert_planned_alert(session, hogar_id, alert)
    if alerta_id is None:
        return
    members = present_members(memberships_data.list_alert_members(session, hogar_id), created_at)
    permission = bool(memberships_data.get_alert_permission(session, hogar_id))
    recipients = alert_rules.new_member_recipients(members, permission, new_usuario_id)
    alerts_data.insert_alert_deliveries(session, alerta_id, recipients)


def _to_member(row: memberships_data.MemberRow) -> Miembro:
    return Miembro(
        membresia_id=row.membresia_id,
        usuario_id=row.usuario_id,
        nombre_completo=row.nombre_completo,
        avatar_url=row.avatar_url,
        rol=row.rol,
        estado="activo",
        fecha_ingreso=row.fecha_ingreso,
    )


def _to_pending(row: invitations_data.InvitationRow) -> InvitacionPendiente:
    return InvitacionPendiente(
        id=row.id, correo_invitado=row.correo_invitado, estado="pendiente", expira_en=row.expira_en
    )


def _to_received(row: invitations_data.ReceivedInvitationRow) -> InvitacionRecibida:
    if row.invitado_por_nombre is None:
        raise RuntimeError(INCONSISTENT_MESSAGE)
    return InvitacionRecibida(
        id=row.id,
        hogar_nombre=row.hogar_nombre,
        invitado_por_nombre=row.invitado_por_nombre,
        expira_en=row.expira_en,
    )


def _to_permisos(row: households_data.HouseholdRow) -> Permisos:
    return Permisos(
        ver_consumo_actual=row.permiso_ver_consumo_actual,
        ver_historial=row.permiso_ver_historial,
        recibir_alertas=row.permiso_recibir_alertas,
        modificar_metas=row.permiso_modificar_metas,
    )


def _not_found() -> ApiError:
    return ApiError(404, CodigoError.NO_ENCONTRADO, NOT_FOUND_MESSAGE)


def _pending_exists() -> ApiError:
    return ApiError(409, CodigoError.INVITACION_PENDIENTE_EXISTENTE, PENDING_EXISTS_MESSAGE)


def _limit_reached() -> ApiError:
    return ApiError(409, CodigoError.LIMITE_MIEMBROS, LIMIT_MESSAGE)


def _active_membership_exists() -> ApiError:
    return ApiError(409, CodigoError.MEMBRESIA_ACTIVA_EXISTENTE, ACTIVE_MEMBERSHIP_MESSAGE)


def _validation_error(location: list[str], message: str) -> ApiError:
    return ApiError(
        422,
        CodigoError.VALIDACION,
        VALIDACION_MESSAGE,
        {"campos": [{"ubicacion": location, "mensaje": message}]},
    )
