"""Guardias de permisos: mapeo permiso → `CodigoError`, `recibir_alertas` y membresía resuelta.

Reglas: RN-XVII-01…05 (403 con el código exacto; el administrador pasa todos), RN-I-03.
Complementa P-02…P-06.
"""

import pytest

from app.errors import NOT_FOUND_MESSAGE, ApiError, CodigoError
from app.security.dependencies import (
    PERMISSION_ERRORS,
    AuthenticatedUser,
    HouseholdPermissions,
    Membership,
    membership,
    require_permission,
)
from tests.helpers.auth import FakeSession, install_fake_memberships, make_membership_row
from tests.permissions.guarded_app import (
    FORBIDDEN_MESSAGE,
    HOGAR_ID,
    MEMBER_ID,
    PERMISSION_ROUTES,
    CallRoute,
    member_row,
)


def test_permission_errors_map_each_permission_to_its_exact_code() -> None:
    assert PERMISSION_ERRORS == {
        "ver_consumo_actual": CodigoError.SIN_PERMISO_VER_CONSUMO,
        "ver_historial": CodigoError.SIN_PERMISO_VER_HISTORIAL,
        "recibir_alertas": CodigoError.SIN_PERMISO_RECIBIR_ALERTAS,
        "modificar_metas": CodigoError.SIN_PERMISO_MODIFICAR_METAS,
    }
    assert set(PERMISSION_ERRORS) == set(HouseholdPermissions.__dataclass_fields__)


@pytest.mark.parametrize("permission", sorted(PERMISSION_ROUTES))
def test_each_missing_permission_returns_its_code(call: CallRoute, permission: str) -> None:
    method, path = PERMISSION_ROUTES[permission]
    row = member_row(**{permission: False})
    response = call(method, path, user_id=MEMBER_ID, rows=[row])
    assert response.status_code == 403
    assert response.json() == {
        "codigo": PERMISSION_ERRORS[permission].value,  # type: ignore[index]
        "mensaje": FORBIDDEN_MESSAGE,
        "detalles": None,
    }


def test_member_without_receive_alerts_gets_403(call: CallRoute) -> None:
    response = call("GET", "/alertas", user_id=MEMBER_ID, rows=[member_row(recibir_alertas=False)])
    assert response.status_code == 403
    assert response.json()["codigo"] == "SIN_PERMISO_RECIBIR_ALERTAS"


def test_require_permission_rejects_unknown_permission() -> None:
    with pytest.raises(ValueError):
        require_permission("ver_todo")  # type: ignore[arg-type]


def test_require_permission_returns_the_same_dependency_per_permission() -> None:
    # Misma dependencia para el mismo permiso: FastAPI la resuelve una vez por petición y
    # las pruebas de contrato pueden identificar el guardia de cada operación.
    assert require_permission("ver_historial") is require_permission("ver_historial")
    assert require_permission("ver_historial") is not require_permission("modificar_metas")


def test_membership_maps_row_fields(call: CallRoute) -> None:
    row = member_row(ver_consumo_actual=True)
    response = call("GET", "/miembros", user_id=MEMBER_ID, rows=[row], hogar_id=HOGAR_ID)
    assert response.status_code == 200
    assert response.json() == {"membresia_id": str(row.membresia_id), "rol": "miembro"}


def test_membership_dependency_builds_membership_with_permissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = make_membership_row(
        MEMBER_ID,
        HOGAR_ID,
        ver_consumo_actual=False,
        ver_historial=True,
        recibir_alertas=False,
        modificar_metas=True,
    )
    install_fake_memberships(monkeypatch, [row])
    user = AuthenticatedUser(id=MEMBER_ID, correo="persona@example.com")

    member = membership(HOGAR_ID, user, session=FakeSession())  # type: ignore[arg-type]

    assert member == Membership(
        membresia_id=row.membresia_id,
        hogar_id=HOGAR_ID,
        usuario_id=MEMBER_ID,
        rol="miembro",
        permisos=HouseholdPermissions(
            ver_consumo_actual=False,
            ver_historial=True,
            recibir_alertas=False,
            modificar_metas=True,
        ),
    )
    assert member.is_admin is False


def test_membership_dependency_raises_404_without_active_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_memberships(monkeypatch, [])
    user = AuthenticatedUser(id=MEMBER_ID, correo="persona@example.com")
    with pytest.raises(ApiError) as error:
        membership(HOGAR_ID, user, session=FakeSession())  # type: ignore[arg-type]
    assert error.value.status_code == 404
    assert error.value.codigo is CodigoError.NO_ENCONTRADO
    assert error.value.mensaje == NOT_FOUND_MESSAGE
    assert error.value.detalles is None


def test_admin_membership_is_administrator() -> None:
    member = Membership(
        membresia_id=MEMBER_ID,
        hogar_id=HOGAR_ID,
        usuario_id=MEMBER_ID,
        rol="administrador",
        permisos=HouseholdPermissions(False, False, False, False),
    )
    assert member.is_admin is True
