"""Alta de una alerta ya planificada y miembros que pueden recibirla (parte compartida).

Lo usan `live_alerts` (alertas de consumo, cierre de mes y aviso «Nuevo consejo») y
`members_invitations` (aviso «Nuevo miembro»). Cada uno decide sus destinatarios con la regla del
dominio que le toca (`alert_rules.alert_recipients` o `alert_rules.new_member_recipients`) y
cuándo leer los miembros; aquí solo vive lo que era idéntico en ambos:

- `insert_planned_alert`: guarda la `PlannedAlert` con su texto ya resuelto (RN-XI-09) y su
  `clave_evento` (DC-25); None si la clave ya existía (`ON CONFLICT DO NOTHING`).
- `present_members`: miembros activos que ya estaban en el hogar cuando ocurrió el evento
  (`fecha_ingreso <= moment`; RN-VI-02 y RN-XV-06, sin efecto retroactivo).

Módulo interno de `app.services`: no importa otros servicios (sin ciclos de importación). Sin
commit ni rollback.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlmodel import Session

from app.data import alerts as alerts_data
from app.data.memberships import AlertMemberRow
from app.domain.alert_rules import AlertMember, PlannedAlert


def insert_planned_alert(session: Session, hogar_id: UUID, alert: PlannedAlert) -> UUID | None:
    """Inserta la alerta del hogar; devuelve su id o None si `clave_evento` ya existía (DC-25)."""
    return alerts_data.insert_alert(
        session,
        hogar_id=hogar_id,
        categoria=alert.categoria,
        severidad=alert.severidad,
        titulo=alert.titulo,
        mensaje=alert.mensaje,
        zona_id=alert.zona_id,
        regla_origen=alert.regla_origen,
        clave_evento=alert.clave_evento,
        created_at=alert.created_at,
    )


def present_members(rows: Sequence[AlertMemberRow], moment: datetime) -> list[AlertMember]:
    """Miembros activos que ya estaban en el hogar en `moment`, en el orden de entrada."""
    return [
        AlertMember(row.usuario_id, row.rol, row.notif_consumo, row.notif_consejos)
        for row in rows
        if row.fecha_ingreso <= moment
    ]
