"""Pruebas de app.services.users con `app.data.*` y `supabase_admin` falsos (sin base ni red).

Cubre las 8 operaciones de la fase 3: ficha (RN-IX-01, RN-IX-07), avatar (RN-I-02, DC-43),
preferencias (RN-VI-04, RN-VII-01, RN-XVI-02, RN-XVI-03) y baja de la cuenta (RN-IX-09,
DC-36). Cada llamada a datos, el commit y las llamadas a Supabase quedan en un registro
ordenado para comprobar la transacción: commit solo con éxito y Supabase después del commit.
La baja de la cuenta sigue el orden de bloqueo único hogar → membresía → ficha y borra la ficha
antes del commit (RN-IX-09, DC-36; docstring de `delete_account`). La carrera con aceptar una
invitación se prueba en test_delete_account_race.py.
"""

import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import users as users_data
from app.data.memberships import MembershipSummaryRow
from app.data.users import PreferencesRow, UserProfileRow
from app.errors import ApiError, CodigoError, NotImplementedOperation
from app.schemas.common import ReferenciaTipo, Rol
from app.schemas.users import (
    AvatarGuardar,
    ContrasenaCambiar,
    ContrasenaVerificar,
    Preferencias,
    PreferenciasActualizar,
    UsuarioActual,
    UsuarioActualizar,
    UsuarioCrear,
)
from app.services import supabase_admin
from app.services import users as service
from app.services.supabase_admin import SupabaseAdminError

USER_ID = UUID("6f1c2d3e-4a5b-4c6d-8e7f-90a1b2c3d4e5")
OTHER_USER_ID = UUID("0a0b0c0d-1e1f-4a2b-8c3d-4e5f60718293")
HOGAR_ID = UUID("11111111-2222-4333-8444-555555555555")
MEMBRESIA_ID = UUID("99999999-8888-4777-8666-555555555555")
CORREO = "persona@example.com"
NOW = datetime(2026, 11, 20, 15, 30, tzinfo=UTC)

DEFAULT_PREFERENCES = PreferencesRow(
    notif_consumo=True, notif_consejos=True, base_comparacion="promedio"
)


class FakeSession:
    """Solo cuenta commits y rollbacks y los anota en el registro compartido; no ejecuta SQL."""

    def __init__(self, events: list[tuple[Any, ...]]) -> None:
        self.events = events
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1
        self.events.append(("commit",))

    def rollback(self) -> None:
        self.rollbacks += 1
        self.events.append(("rollback",))

    def exec(self, *_args: Any, **_kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("el servicio no debe ejecutar SQL directamente")


@dataclass
class FakeData:
    """Estado en memoria de usuarios, preferencias y membresías, más el registro de llamadas."""

    profile: UserProfileRow | None = None
    membership: MembershipSummaryRow | None = None
    # Si se da, cada lectura de la membresía activa consume el siguiente valor (en orden).
    membership_reads: list[MembershipSummaryRow | None] | None = None
    other_members: int = 0
    insert_error: Exception | None = None
    auth_error: Exception | None = None
    storage_error: Exception | None = None
    events: list[tuple[Any, ...]] = field(default_factory=list)

    def names(self) -> list[str]:
        return [event[0] for event in self.events]

    def find(self, name: str) -> tuple[Any, ...]:
        matches = [event for event in self.events if event[0] == name]
        assert len(matches) == 1, (name, self.events)
        return matches[0]


@pytest.fixture
def data(monkeypatch: pytest.MonkeyPatch) -> FakeData:
    fake = FakeData()

    def get_user_profile(_session: Any, usuario_id: UUID) -> UserProfileRow | None:
        fake.events.append(("get_user_profile", usuario_id))
        return fake.profile

    def insert_user_with_default_preferences(
        _session: Any, usuario_id: UUID, nombre_completo: str, telefono: str | None
    ) -> bool:
        fake.events.append(("insert_user", usuario_id, nombre_completo, telefono))
        if fake.insert_error is not None:
            raise fake.insert_error
        if fake.profile is not None:
            return False
        fake.profile = UserProfileRow(
            id=usuario_id,
            nombre_completo=nombre_completo,
            telefono=telefono,
            avatar_url=None,
            preferencias=DEFAULT_PREFERENCES,
        )
        return True

    def lock_user_profile(_session: Any, usuario_id: UUID) -> UserProfileRow | None:
        fake.events.append(("lock_user_profile", usuario_id))
        return fake.profile

    def delete_user_profile(_session: Any, usuario_id: UUID) -> bool:
        fake.events.append(("delete_user_profile", usuario_id))
        deleted = fake.profile is not None
        fake.profile = None
        return deleted

    def update_user_profile(_session: Any, usuario_id: UUID, changes: dict[str, Any]) -> bool:
        fake.events.append(("update_user_profile", usuario_id, dict(changes)))
        if not changes:
            raise ValueError("No hay cambios que aplicar.")
        if fake.profile is None:
            return False
        fake.profile = _replace(fake.profile, **changes)
        return True

    def set_avatar_url(_session: Any, usuario_id: UUID, avatar_url: str | None) -> bool:
        fake.events.append(("set_avatar_url", usuario_id, avatar_url))
        if fake.profile is None:
            return False
        fake.profile = _replace(fake.profile, avatar_url=avatar_url)
        return True

    def get_preferences(_session: Any, usuario_id: UUID) -> PreferencesRow | None:
        fake.events.append(("get_preferences", usuario_id))
        return None if fake.profile is None else fake.profile.preferencias

    def update_preferences(
        _session: Any, usuario_id: UUID, changes: dict[str, Any]
    ) -> PreferencesRow | None:
        fake.events.append(("update_preferences", usuario_id, dict(changes)))
        if not changes or any(value is None for value in changes.values()):
            raise ValueError("cambios inválidos")
        if fake.profile is None:
            return None
        current = fake.profile.preferencias
        updated = PreferencesRow(
            notif_consumo=changes.get("notif_consumo", current.notif_consumo),
            notif_consejos=changes.get("notif_consejos", current.notif_consejos),
            base_comparacion=changes.get("base_comparacion", current.base_comparacion),
        )
        fake.profile = _replace(fake.profile, preferencias=updated)
        return updated

    def get_active_membership_of_user(
        _session: Any, usuario_id: UUID, *, for_update: bool = False
    ) -> MembershipSummaryRow | None:
        fake.events.append(("get_active_membership_of_user", usuario_id, for_update))
        if fake.membership_reads is not None:
            return fake.membership_reads.pop(0)
        return fake.membership

    def count_other_active_members(_session: Any, hogar_id: UUID, usuario_id: UUID) -> int:
        fake.events.append(("count_other_active_members", hogar_id, usuario_id))
        return fake.other_members

    def close_membership(_session: Any, membresia_id: UUID, closed_at: datetime) -> None:
        fake.events.append(("close_membership", membresia_id, closed_at))

    def lock_household(_session: Any, hogar_id: UUID) -> None:
        fake.events.append(("lock_household", hogar_id))

    def delete_household(_session: Any, hogar_id: UUID) -> None:
        fake.events.append(("delete_household", hogar_id))

    def delete_auth_user(_settings: Any, usuario_id: UUID) -> None:
        fake.events.append(("delete_auth_user", usuario_id))
        if fake.auth_error is not None:
            raise fake.auth_error

    def delete_avatar_files(_settings: Any, usuario_id: UUID) -> None:
        fake.events.append(("delete_avatar_files", usuario_id))
        if fake.storage_error is not None:
            raise fake.storage_error

    for module, function in (
        (users_data, get_user_profile),
        (users_data, insert_user_with_default_preferences),
        (users_data, update_user_profile),
        (users_data, lock_user_profile),
        (users_data, delete_user_profile),
        (users_data, set_avatar_url),
        (users_data, get_preferences),
        (users_data, update_preferences),
        (memberships_data, get_active_membership_of_user),
        (memberships_data, count_other_active_members),
        (memberships_data, close_membership),
        (households_data, lock_household),
        (households_data, delete_household),
        (supabase_admin, delete_auth_user),
        (supabase_admin, delete_avatar_files),
    ):
        assert hasattr(module, function.__name__), function.__name__
        monkeypatch.setattr(module, function.__name__, function)
    return fake


@pytest.fixture
def session(data: FakeData) -> FakeSession:
    return FakeSession(data.events)


@pytest.fixture
def settings() -> Settings:
    # Sin leer .env: los valores no importan porque Supabase está falso.
    return Settings.model_construct()


def _replace(row: Any, **changes: Any) -> Any:
    return replace(row, **changes)


def _profile(**overrides: Any) -> UserProfileRow:
    values: dict[str, Any] = {
        "id": USER_ID,
        "nombre_completo": "Ana Pérez",
        "telefono": "3001234567",
        "avatar_url": None,
        "preferencias": DEFAULT_PREFERENCES,
    }
    values.update(overrides)
    return UserProfileRow(**values)


def _membership(
    rol: str, hogar_id: UUID = HOGAR_ID, membresia_id: UUID = MEMBRESIA_ID
) -> MembershipSummaryRow:
    return MembershipSummaryRow(membresia_id=membresia_id, hogar_id=hogar_id, rol=rol)  # type: ignore[arg-type]


# Orden único de bloqueo (hogar → membresía): lectura sin bloqueo, bloqueo del hogar, relectura.
def _lock_sequence(hogar_id: UUID = HOGAR_ID) -> list[tuple[Any, ...]]:
    return [
        ("get_active_membership_of_user", USER_ID, False),
        ("lock_household", hogar_id),
        ("get_active_membership_of_user", USER_ID, True),
    ]


# Último nivel del orden único: la ficha, después del hogar y la membresía.
PROFILE_LOCK = ("lock_user_profile", USER_ID)


def _assert_api_error(exc: ApiError, status: int, codigo: CodigoError) -> None:
    assert exc.status_code == status
    assert exc.codigo == codigo
    assert exc.mensaje  # técnico y corto; nunca una excepción interna


# --- obtenerUsuarioActual -------------------------------------------------------------------


def test_get_current_user_returns_profile_preferences_and_membership(
    data: FakeData, session: FakeSession
) -> None:
    data.profile = _profile(avatar_url=f"{USER_ID}/avatar.png")
    data.membership = _membership("administrador")

    result = service.get_current_user(session, USER_ID, CORREO)  # type: ignore[arg-type]

    assert isinstance(result, UsuarioActual)
    assert result.model_dump(mode="json") == {
        "id": str(USER_ID),
        "correo": CORREO,
        "nombre_completo": "Ana Pérez",
        "telefono": "3001234567",
        "avatar_url": f"{USER_ID}/avatar.png",
        "preferencias": {
            "notif_consumo": True,
            "notif_consejos": True,
            "base_comparacion": "promedio",
        },
        "membresia": {
            "membresia_id": str(MEMBRESIA_ID),
            "hogar_id": str(HOGAR_ID),
            "rol": "administrador",
        },
    }
    assert result.membresia is not None and result.membresia.rol is Rol.ADMINISTRADOR
    assert session.commits == 0
    assert ("get_active_membership_of_user", USER_ID, False) in data.events


def test_get_current_user_without_membership_returns_null_membership(
    data: FakeData, session: FakeSession
) -> None:
    data.profile = _profile(telefono=None)

    result = service.get_current_user(session, USER_ID, CORREO)  # type: ignore[arg-type]

    assert result.membresia is None
    assert result.telefono is None  # null = sin dato
    assert result.avatar_url is None


def test_get_current_user_without_profile_is_404_ficha_no_creada(
    data: FakeData, session: FakeSession
) -> None:
    with pytest.raises(ApiError) as caught:
        service.get_current_user(session, USER_ID, CORREO)  # type: ignore[arg-type]

    _assert_api_error(caught.value, 404, CodigoError.FICHA_NO_CREADA)
    assert caught.value.mensaje == service.FICHA_NO_CREADA_MESSAGE
    assert session.commits == 0


# --- crearFichaUsuario ----------------------------------------------------------------------


def test_create_user_profile_creates_with_default_preferences_and_commits(
    data: FakeData, session: FakeSession
) -> None:
    payload = UsuarioCrear(nombre_completo="Ana Pérez", telefono=None)

    result = service.create_user_profile(session, USER_ID, CORREO, payload)  # type: ignore[arg-type]

    assert data.find("insert_user") == ("insert_user", USER_ID, "Ana Pérez", None)
    assert result.id == USER_ID
    assert result.correo == CORREO
    assert result.telefono is None
    assert result.membresia is None
    assert result.preferencias == Preferencias(
        notif_consumo=True, notif_consejos=True, base_comparacion=ReferenciaTipo.PROMEDIO
    )
    assert session.commits == 1
    assert data.names()[-1] == "commit"


def test_create_user_profile_existing_is_409_without_commit(
    data: FakeData, session: FakeSession
) -> None:
    data.profile = _profile()

    with pytest.raises(ApiError) as caught:
        service.create_user_profile(  # type: ignore[arg-type]
            session, USER_ID, CORREO, UsuarioCrear(nombre_completo="Otra")
        )

    _assert_api_error(caught.value, 409, CodigoError.FICHA_EXISTENTE)
    assert session.commits == 0
    assert data.profile.nombre_completo == "Ana Pérez"


def test_create_user_profile_for_deleted_auth_account_is_401_without_commit(
    data: FakeData, session: FakeSession
) -> None:
    # Token aún vigente de una cuenta ya borrada en Auth: falla la FK hacia auth.users.
    data.insert_error = users_data.AuthUserMissingError()

    with pytest.raises(ApiError) as caught:
        service.create_user_profile(  # type: ignore[arg-type]
            session, USER_ID, CORREO, UsuarioCrear(nombre_completo="Ana Pérez")
        )

    _assert_api_error(caught.value, 401, CodigoError.NO_AUTENTICADO)
    assert caught.value.headers == {"WWW-Authenticate": "Bearer"}
    assert caught.value.detalles is None
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    assert session.commits == 0
    assert data.names() == ["insert_user"]


# --- actualizarPerfil -----------------------------------------------------------------------


def test_update_profile_sends_only_the_fields_sent(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile()
    payload = UsuarioActualizar.model_validate({"nombre_completo": "Ana María"})

    result = service.update_profile(session, USER_ID, CORREO, payload)  # type: ignore[arg-type]

    assert data.find("update_user_profile") == (
        "update_user_profile",
        USER_ID,
        {"nombre_completo": "Ana María"},
    )
    assert result.nombre_completo == "Ana María"
    assert result.telefono == "3001234567"  # no enviado: no cambia
    assert session.commits == 1
    assert data.names()[-1] == "commit"


def test_update_profile_null_phone_clears_it(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile()
    payload = UsuarioActualizar.model_validate({"telefono": None})

    result = service.update_profile(session, USER_ID, CORREO, payload)  # type: ignore[arg-type]

    assert data.find("update_user_profile")[2] == {"telefono": None}
    assert result.telefono is None
    assert result.nombre_completo == "Ana Pérez"
    assert session.commits == 1


def test_update_profile_both_fields(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile()
    payload = UsuarioActualizar.model_validate(
        {"nombre_completo": "Ana María", "telefono": "3109876543"}
    )

    service.update_profile(session, USER_ID, CORREO, payload)  # type: ignore[arg-type]

    assert data.find("update_user_profile")[2] == {
        "nombre_completo": "Ana María",
        "telefono": "3109876543",
    }


def test_update_profile_without_profile_is_404_without_commit(
    data: FakeData, session: FakeSession
) -> None:
    payload = UsuarioActualizar.model_validate({"telefono": "3001234567"})

    with pytest.raises(ApiError) as caught:
        service.update_profile(session, USER_ID, CORREO, payload)  # type: ignore[arg-type]

    _assert_api_error(caught.value, 404, CodigoError.FICHA_NO_CREADA)
    assert session.commits == 0


def test_update_profile_empty_payload_is_422_without_touching_data(
    data: FakeData, session: FakeSession
) -> None:
    data.profile = _profile()
    # El esquema ya rechaza `{}` (minProperties: 1); se construye sin validar para probar
    # la defensa del servicio.

    with pytest.raises(ApiError) as caught:
        service.update_profile(  # type: ignore[arg-type]
            session, USER_ID, CORREO, UsuarioActualizar.model_construct()
        )

    _assert_api_error(caught.value, 422, CodigoError.VALIDACION)
    assert "update_user_profile" not in data.names()
    assert session.commits == 0


def test_update_profile_null_name_is_422(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile()
    # El esquema ya lo rechaza; el servicio se defiende si llegara construido sin validar.
    payload = UsuarioActualizar.model_construct(
        _fields_set={"nombre_completo"}, nombre_completo=None
    )

    with pytest.raises(ApiError) as caught:
        service.update_profile(session, USER_ID, CORREO, payload)  # type: ignore[arg-type]

    _assert_api_error(caught.value, 422, CodigoError.VALIDACION)
    assert caught.value.detalles == {
        "campos": [{"ubicacion": ["body", "nombre_completo"], "mensaje": service.NOT_NULL_MESSAGE}]
    }
    assert session.commits == 0


# --- guardarAvatar --------------------------------------------------------------------------


@pytest.mark.parametrize("extension", ["jpg", "png", "webp"])
def test_save_avatar_accepts_own_path_and_commits(
    data: FakeData, session: FakeSession, extension: str
) -> None:
    data.profile = _profile()
    path = f"{USER_ID}/avatar.{extension}"

    result = service.save_avatar(  # type: ignore[arg-type]
        session, USER_ID, CORREO, AvatarGuardar(avatar_url=path)
    )

    assert data.find("set_avatar_url") == ("set_avatar_url", USER_ID, path)
    assert result.avatar_url == path
    assert session.commits == 1
    assert data.names()[-1] == "commit"


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(f"{OTHER_USER_ID}/avatar.jpg", id="otro-usuario"),
        pytest.param(f"{USER_ID}/avatar.gif", id="extension-gif"),
        pytest.param(f"{USER_ID}/avatar.jpeg", id="extension-jpeg"),
        pytest.param(f"{USER_ID}/avatar.JPG", id="extension-mayuscula"),
        pytest.param(f"avatares/{USER_ID}/avatar.jpg", id="prefijo-bucket"),
        pytest.param(f"{USER_ID}/../{OTHER_USER_ID}/avatar.jpg", id="punto-punto"),
        pytest.param(f"{USER_ID}/../avatar.jpg", id="punto-punto-corto"),
        pytest.param(f"../{USER_ID}/avatar.jpg", id="punto-punto-inicio"),
        pytest.param(f"{USER_ID}/foto.jpg", id="otro-nombre"),
        pytest.param(f"{USER_ID}/avatar.jpg\n", id="salto-de-linea"),
        pytest.param(f"/{USER_ID}/avatar.jpg", id="barra-inicial"),
        pytest.param(f"{str(USER_ID).upper()}/avatar.jpg", id="id-mayusculas"),
        pytest.param(f"https://x.supabase.co/{USER_ID}/avatar.jpg", id="url-completa"),
    ],
)
def test_save_avatar_rejects_invalid_path_with_422(
    data: FakeData, session: FakeSession, path: str
) -> None:
    data.profile = _profile()

    with pytest.raises(ApiError) as caught:
        service.save_avatar(  # type: ignore[arg-type]
            session, USER_ID, CORREO, AvatarGuardar(avatar_url=path)
        )

    _assert_api_error(caught.value, 422, CodigoError.VALIDACION)
    assert caught.value.mensaje == "Los datos enviados no cumplen las reglas."
    detalles = caught.value.detalles
    assert detalles is not None
    assert [campo["ubicacion"] for campo in detalles["campos"]] == [["body", "avatar_url"]]
    assert path not in str(detalles)  # no se repite lo que envió el cliente
    assert "set_avatar_url" not in data.names()
    assert session.commits == 0


def test_save_avatar_without_profile_is_404_without_commit(
    data: FakeData, session: FakeSession
) -> None:
    with pytest.raises(ApiError) as caught:
        service.save_avatar(  # type: ignore[arg-type]
            session, USER_ID, CORREO, AvatarGuardar(avatar_url=f"{USER_ID}/avatar.jpg")
        )

    _assert_api_error(caught.value, 404, CodigoError.FICHA_NO_CREADA)
    assert session.commits == 0


# --- eliminarAvatar -------------------------------------------------------------------------


def test_delete_avatar_sets_null_and_commits(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile(avatar_url=f"{USER_ID}/avatar.webp")

    assert service.delete_avatar(session, USER_ID) is None  # type: ignore[arg-type]

    assert data.find("set_avatar_url") == ("set_avatar_url", USER_ID, None)
    assert data.profile.avatar_url is None
    assert session.commits == 1


def test_delete_avatar_without_profile_is_404_without_commit(
    data: FakeData, session: FakeSession
) -> None:
    with pytest.raises(ApiError) as caught:
        service.delete_avatar(session, USER_ID)  # type: ignore[arg-type]

    _assert_api_error(caught.value, 404, CodigoError.FICHA_NO_CREADA)
    assert session.commits == 0


# --- obtenerPreferencias / actualizarPreferencias -------------------------------------------


def test_get_preferences_returns_schema(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile(
        preferencias=PreferencesRow(
            notif_consumo=False, notif_consejos=True, base_comparacion="meta"
        )
    )

    result = service.get_preferences(session, USER_ID)  # type: ignore[arg-type]

    assert result == Preferencias(
        notif_consumo=False, notif_consejos=True, base_comparacion=ReferenciaTipo.META
    )
    assert session.commits == 0


def test_get_preferences_without_row_is_404(data: FakeData, session: FakeSession) -> None:
    with pytest.raises(ApiError) as caught:
        service.get_preferences(session, USER_ID)  # type: ignore[arg-type]

    _assert_api_error(caught.value, 404, CodigoError.FICHA_NO_CREADA)


def test_update_preferences_sends_only_the_fields_sent_as_plain_values(
    data: FakeData, session: FakeSession
) -> None:
    data.profile = _profile()
    payload = PreferenciasActualizar.model_validate({"base_comparacion": "meta"})

    result = service.update_preferences(session, USER_ID, payload)  # type: ignore[arg-type]

    changes = data.find("update_preferences")[2]
    assert changes == {"base_comparacion": "meta"}
    assert type(changes["base_comparacion"]) is str  # el SQL recibe el texto, no el enum
    assert result == Preferencias(
        notif_consumo=True, notif_consejos=True, base_comparacion=ReferenciaTipo.META
    )
    assert session.commits == 1
    assert data.names()[-1] == "commit"


def test_update_preferences_switches(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile()
    payload = PreferenciasActualizar.model_validate(
        {"notif_consumo": False, "notif_consejos": False}
    )

    result = service.update_preferences(session, USER_ID, payload)  # type: ignore[arg-type]

    assert data.find("update_preferences")[2] == {"notif_consumo": False, "notif_consejos": False}
    assert result.notif_consumo is False
    assert result.notif_consejos is False
    assert result.base_comparacion is ReferenciaTipo.PROMEDIO


def test_update_preferences_without_row_is_404_without_commit(
    data: FakeData, session: FakeSession
) -> None:
    payload = PreferenciasActualizar.model_validate({"notif_consumo": False})

    with pytest.raises(ApiError) as caught:
        service.update_preferences(session, USER_ID, payload)  # type: ignore[arg-type]

    _assert_api_error(caught.value, 404, CodigoError.FICHA_NO_CREADA)
    assert session.commits == 0


def test_update_preferences_empty_payload_is_422(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile()
    # El esquema ya rechaza `{}` (minProperties: 1); se construye sin validar para probar
    # la defensa del servicio.

    with pytest.raises(ApiError) as caught:
        service.update_preferences(  # type: ignore[arg-type]
            session, USER_ID, PreferenciasActualizar.model_construct()
        )

    _assert_api_error(caught.value, 422, CodigoError.VALIDACION)
    assert "update_preferences" not in data.names()
    assert session.commits == 0


def test_update_preferences_null_value_is_422(data: FakeData, session: FakeSession) -> None:
    data.profile = _profile()
    payload = PreferenciasActualizar.model_construct(
        _fields_set={"notif_consumo"}, notif_consumo=None
    )

    with pytest.raises(ApiError) as caught:
        service.update_preferences(session, USER_ID, payload)  # type: ignore[arg-type]

    _assert_api_error(caught.value, 422, CodigoError.VALIDACION)
    assert "update_preferences" not in data.names()


# --- eliminarCuenta -------------------------------------------------------------------------


def test_delete_account_admin_with_other_members_is_409_without_commit_or_supabase(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.profile = _profile()
    data.membership = _membership("administrador")
    data.other_members = 2

    with pytest.raises(ApiError) as caught:
        service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    _assert_api_error(caught.value, 409, CodigoError.ADMIN_DEBE_TRANSFERIR)
    assert session.commits == 0
    names = data.names()
    assert "close_membership" not in names
    assert "delete_household" not in names
    assert "delete_user_profile" not in names
    assert "delete_auth_user" not in names
    assert "delete_avatar_files" not in names


def test_delete_account_only_admin_closes_membership_deletes_household_then_auth(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.profile = _profile()
    data.membership = _membership("administrador")
    data.other_members = 0

    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert data.events == [
        *_lock_sequence(),
        PROFILE_LOCK,
        ("count_other_active_members", HOGAR_ID, USER_ID),
        ("close_membership", MEMBRESIA_ID, NOW),
        ("delete_household", HOGAR_ID),
        ("delete_user_profile", USER_ID),
        ("commit",),
        ("delete_auth_user", USER_ID),
        ("delete_avatar_files", USER_ID),
    ]
    assert session.commits == 1
    assert session.rollbacks == 0


def test_delete_account_member_not_alone_closes_membership_keeps_household(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.profile = _profile()
    data.membership = _membership("miembro")
    data.other_members = 3

    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    names = data.names()
    assert data.find("close_membership") == ("close_membership", MEMBRESIA_ID, NOW)
    assert "delete_household" not in names
    assert (
        names.index("close_membership")
        < names.index("delete_user_profile")
        < names.index("commit")
        < names.index("delete_auth_user")
    )
    assert names[-1] == "delete_avatar_files"
    assert session.commits == 1


def test_delete_account_only_member_with_member_role_deletes_household(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.membership = _membership("miembro")
    data.other_members = 0

    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert data.find("delete_household") == ("delete_household", HOGAR_ID)


def test_delete_account_without_membership_rechecks_and_deletes_profile_then_auth(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.profile = _profile()

    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    # Sin membresía en la lectura sin bloqueo: no se bloquea ningún hogar; tras bloquear la ficha
    # se comprueba que no apareció una membresía mientras se esperaba.
    assert data.events == [
        ("get_active_membership_of_user", USER_ID, False),
        PROFILE_LOCK,
        ("get_active_membership_of_user", USER_ID, False),
        ("delete_user_profile", USER_ID),
        ("commit",),
        ("delete_auth_user", USER_ID),
        ("delete_avatar_files", USER_ID),
    ]
    assert data.profile is None


def test_delete_account_without_profile_does_not_delete_it(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert "delete_user_profile" not in data.names()
    assert data.names()[-3:] == ["commit", "delete_auth_user", "delete_avatar_files"]


def test_delete_account_locks_household_then_membership_then_profile(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.profile = _profile()
    data.membership = _membership("miembro")
    data.other_members = 1

    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert data.events[:5] == [
        *_lock_sequence(),
        PROFILE_LOCK,
        ("count_other_active_members", HOGAR_ID, USER_ID),
    ]


def test_delete_account_membership_closed_meanwhile_continues_without_membership(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    # Otra transacción cerró la membresía entre la lectura y el bloqueo del hogar.
    data.profile = _profile()
    data.membership_reads = [_membership("administrador"), None, None]
    data.other_members = 2

    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert data.events == [
        *_lock_sequence(),
        PROFILE_LOCK,
        ("get_active_membership_of_user", USER_ID, False),
        ("delete_user_profile", USER_ID),
        ("commit",),
        ("delete_auth_user", USER_ID),
        ("delete_avatar_files", USER_ID),
    ]


def test_delete_account_membership_appeared_while_locking_profile_rolls_back_and_retries(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    # Sin membresía al empezar; una aceptación confirmó mientras se esperaba la ficha.
    data.profile = _profile()
    accepted = _membership("miembro")
    data.membership_reads = [None, accepted, accepted, accepted]
    data.other_members = 1

    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert data.events == [
        ("get_active_membership_of_user", USER_ID, False),
        PROFILE_LOCK,
        ("get_active_membership_of_user", USER_ID, False),
        ("rollback",),
        *_lock_sequence(),
        PROFILE_LOCK,
        ("count_other_active_members", HOGAR_ID, USER_ID),
        ("close_membership", MEMBRESIA_ID, NOW),
        ("delete_user_profile", USER_ID),
        ("commit",),
        ("delete_auth_user", USER_ID),
        ("delete_avatar_files", USER_ID),
    ]
    assert session.rollbacks == 1


def test_delete_account_membership_appearing_every_round_is_runtime_error_without_commit(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.profile = _profile()
    accepted = _membership("miembro")
    data.membership_reads = [None, accepted] * service.LOCK_ATTEMPTS

    with pytest.raises(RuntimeError):
        service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert session.commits == 0
    assert session.rollbacks == service.LOCK_ATTEMPTS
    assert "delete_user_profile" not in data.names()
    assert "delete_auth_user" not in data.names()


def test_delete_account_membership_moved_household_retries_once(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    new_household = UUID("22222222-3333-4444-8555-666666666666")
    new_membership = _membership("miembro", hogar_id=new_household, membresia_id=uuid4())
    data.membership_reads = [
        _membership("miembro"),
        new_membership,  # relectura: cambió de hogar
        new_membership,  # se repite la secuencia
        new_membership,
    ]
    data.other_members = 0

    service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert data.events == [
        *_lock_sequence(HOGAR_ID),
        ("rollback",),  # suelta el primer hogar antes de bloquear el nuevo
        *_lock_sequence(new_household),
        PROFILE_LOCK,
        ("count_other_active_members", new_household, USER_ID),
        ("close_membership", new_membership.membresia_id, NOW),
        ("delete_household", new_household),
        ("commit",),
        ("delete_auth_user", USER_ID),
        ("delete_avatar_files", USER_ID),
    ]


def test_delete_account_membership_moving_twice_is_runtime_error_without_commit(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    second = UUID("22222222-3333-4444-8555-666666666666")
    third = UUID("33333333-4444-4555-8666-777777777777")
    data.membership_reads = [
        _membership("miembro"),
        _membership("miembro", hogar_id=second),
        _membership("miembro", hogar_id=second),
        _membership("miembro", hogar_id=third),
    ]

    with pytest.raises(RuntimeError):
        service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    assert data.events == [*_lock_sequence(HOGAR_ID), ("rollback",), *_lock_sequence(second)]
    assert session.commits == 0
    assert session.rollbacks == 1


def test_delete_account_uses_current_utc_time_by_default(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.membership = _membership("miembro")
    data.other_members = 1
    before = datetime.now(UTC)

    service.delete_account(session, USER_ID, settings)  # type: ignore[arg-type]

    closed_at = data.find("close_membership")[2]
    assert closed_at.tzinfo is not None
    assert before <= closed_at <= datetime.now(UTC)


def test_delete_account_auth_failure_propagates_after_commit(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.membership = _membership("administrador")
    data.auth_error = SupabaseAdminError("Supabase respondió 500 al borrar el usuario de Auth.")

    with pytest.raises(SupabaseAdminError):
        service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]

    names = data.names()
    assert session.commits == 1
    assert names.index("commit") < names.index("delete_auth_user")
    assert "delete_avatar_files" not in names


def test_delete_account_storage_failure_does_not_break_and_logs_without_ids(
    data: FakeData,
    session: FakeSession,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data.storage_error = SupabaseAdminError("Supabase respondió 500 al borrar los avatares.")

    with caplog.at_level(logging.WARNING, logger=service.logger.name):
        assert service.delete_account(session, USER_ID, settings, now=NOW) is None  # type: ignore[arg-type]

    assert data.names()[-1] == "delete_avatar_files"
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "SupabaseAdminError" in message
    assert str(USER_ID) not in message
    assert warnings[0].exc_info is None


def test_delete_account_storage_unexpected_error_is_not_swallowed(
    data: FakeData, session: FakeSession, settings: Settings
) -> None:
    data.storage_error = RuntimeError("fallo de programación")

    with pytest.raises(RuntimeError):
        service.delete_account(session, USER_ID, settings, now=NOW)  # type: ignore[arg-type]


# --- fuera de esta fase ---------------------------------------------------------------------


def test_password_operations_stay_501() -> None:
    user_id = uuid4()
    with pytest.raises(NotImplementedOperation) as verify:
        service.verify_current_password(
            user_id, ContrasenaVerificar.model_validate({"contrasena_actual": "x"})
        )
    assert verify.value.operation_id == "verificarContrasenaActual"
    with pytest.raises(NotImplementedOperation) as change:
        service.change_password(
            user_id,
            ContrasenaCambiar.model_validate(
                {"contrasena_actual": "x", "contrasena_nueva": "12345678"}
            ),
        )
    assert change.value.operation_id == "cambiarContrasena"
