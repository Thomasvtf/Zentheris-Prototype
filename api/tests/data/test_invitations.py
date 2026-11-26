"""Pruebas de app.data.invitations sin base real (RN-X-05, RN-X-06, RN-II-02, DC-41, DC-42).

Una sesión falsa registra cada sentencia y sus parámetros: se comprueba el SQL generado
(filtro por hogar o por correo con lower(), estado y vigencia), el FOR UPDATE, que los valores
viajan como parámetros, que ninguna consulta devuelve token_hash, el mapeo de filas y la
traducción del índice único de invitación pendiente. La unicidad real (uq_invitacion_pendiente_
hogar_correo) y el LATERAL del nombre de quien invitó solo se comprueban con Postgres.
"""

import operator
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg2.errors
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import TextClause

from app.data import invitations
from app.data.invitations import (
    InvitationRow,
    PendingInvitationExistsError,
    ReceivedInvitationRow,
    count_pending_invitations,
    expire_stale_pending,
    expire_stale_pending_for_email,
    get_invitation,
    get_invitation_by_token_hash,
    get_received_invitation,
    has_pending_invitation,
    insert_invitation,
    list_pending_invitations,
    list_received_invitations,
    set_invitation_state,
)
from tests.data.fake_session import FakeResult, FakeSession, assert_bound_only, normalized_sql

NOW = datetime(2026, 11, 25, 15, 0, tzinfo=UTC)
BOGOTA = timezone(timedelta(hours=-5))
CORREO = "Invitada.Prueba@Example.COM"
TOKEN_HASH = "a" * 64

ALL_STATEMENTS = (
    invitations.EXPIRE_STALE_PENDING_SQL,
    invitations.EXPIRE_STALE_PENDING_FOR_EMAIL_SQL,
    invitations.HAS_PENDING_INVITATION_SQL,
    invitations.COUNT_PENDING_INVITATIONS_SQL,
    invitations.INSERT_INVITATION_SQL,
    invitations.LIST_PENDING_INVITATIONS_SQL,
    invitations.INVITATION_BY_ID_SQL,
    invitations.INVITATION_BY_ID_FOR_UPDATE_SQL,
    invitations.INVITATION_BY_TOKEN_HASH_SQL,
    invitations.SET_INVITATION_STATE_SQL,
    invitations.LIST_RECEIVED_INVITATIONS_SQL,
    invitations.RECEIVED_INVITATION_BY_ID_SQL,
)


def _invitation_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": uuid4(),
        "hogar_id": uuid4(),
        "correo_invitado": "invitada.prueba@example.com",
        "invitado_por": uuid4(),
        "estado": "pendiente",
        "expira_en": NOW + timedelta(days=7),
        "respondida_en": None,
        "created_at": NOW,
    }
    row.update(overrides)
    return row


def _received_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": uuid4(),
        "hogar_id": uuid4(),
        "hogar_nombre": "Casa de prueba",
        "invitado_por_nombre": "Persona administradora",
        "expira_en": NOW + timedelta(days=7),
    }
    row.update(overrides)
    return row


# ------------------------------------------------------------------------- generales


@pytest.mark.parametrize("statement", ALL_STATEMENTS)
def test_statements_are_constants_without_python_formatting(statement: Any) -> None:
    assert isinstance(statement, TextClause)
    assert "{" not in str(statement)
    assert "%" not in str(statement)


@pytest.mark.parametrize("statement", ALL_STATEMENTS)
def test_no_statement_returns_or_selects_the_token_hash_column(statement: Any) -> None:
    """RN-X-05: el hash solo se escribe o se compara; nunca vuelve en una fila."""
    sql = normalized_sql(statement)
    select_part = sql.split(" from ", 1)[0] if sql.startswith("select") else ""
    returning_part = sql.split("returning", 1)[1] if "returning" in sql else ""
    assert "token_hash" not in select_part
    assert "token_hash" not in returning_part


@pytest.mark.parametrize(
    "statement",
    [
        invitations.EXPIRE_STALE_PENDING_SQL,
        invitations.EXPIRE_STALE_PENDING_FOR_EMAIL_SQL,
        invitations.HAS_PENDING_INVITATION_SQL,
        invitations.LIST_RECEIVED_INVITATIONS_SQL,
    ],
)
def test_email_comparisons_use_lower_on_both_sides(statement: Any) -> None:
    """DC-41: igual que el índice único (hogar_id, lower(correo_invitado))."""
    sql = normalized_sql(statement)
    assert "lower(correo_invitado) = lower(:correo)" in sql or (
        "lower(i.correo_invitado) = lower(:correo)" in sql
    )


def test_pending_index_name_matches_the_migration() -> None:
    migrations = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
    (migration,) = migrations.glob("*_0003_*.sql")

    expected = f"create unique index {invitations.PENDING_INVITATION_INDEX}\n"
    assert expected in migration.read_text(encoding="utf-8")


def test_no_function_commits() -> None:
    hogar_id, invitacion_id = uuid4(), uuid4()
    session = FakeSession(
        FakeResult(rowcount=0),
        FakeResult(rowcount=0),
        [],
        [{"total": 0}],
        [_invitation_row()],
        [],
        [],
        [],
        [],
        [],
        [],
    )

    expire_stale_pending(session, hogar_id, CORREO, NOW)  # type: ignore[arg-type]
    expire_stale_pending_for_email(session, CORREO, NOW)  # type: ignore[arg-type]
    has_pending_invitation(session, hogar_id, CORREO, NOW)  # type: ignore[arg-type]
    count_pending_invitations(session, hogar_id, NOW)  # type: ignore[arg-type]
    _insert(session)
    list_pending_invitations(session, hogar_id, NOW)  # type: ignore[arg-type]
    get_invitation(session, invitacion_id, for_update=True)  # type: ignore[arg-type]
    get_invitation_by_token_hash(session, TOKEN_HASH)  # type: ignore[arg-type]
    set_invitation_state(session, invitacion_id, "revocada", None)  # type: ignore[arg-type]
    list_received_invitations(session, CORREO, NOW)  # type: ignore[arg-type]
    get_received_invitation(session, invitacion_id)  # type: ignore[arg-type]

    assert len(session.calls) == 11
    assert session.commits == 0


# --------------------------------------------------------------- vencidas (DC-42)


def test_expire_stale_pending_filters_household_email_state_and_expiry() -> None:
    hogar_id = uuid4()
    session = FakeSession(FakeResult(rowcount=2))

    changed = expire_stale_pending(session, hogar_id, CORREO, NOW)  # type: ignore[arg-type]

    assert changed == 2
    (statement, params) = session.calls[0]
    assert params == {"hogar_id": hogar_id, "correo": CORREO, "now": NOW}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "update invitaciones_hogar set estado = 'expirada' "
        "where hogar_id = :hogar_id and lower(correo_invitado) = lower(:correo) "
        "and estado = 'pendiente' and expira_en < :now"
    )


def test_expire_stale_pending_for_email_touches_every_household_of_that_email() -> None:
    session = FakeSession(FakeResult(rowcount=0))

    changed = expire_stale_pending_for_email(session, CORREO, NOW)  # type: ignore[arg-type]

    assert changed == 0
    (statement, params) = session.calls[0]
    assert params == {"correo": CORREO, "now": NOW}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql == (
        "update invitaciones_hogar set estado = 'expirada' "
        "where lower(correo_invitado) = lower(:correo) "
        "and estado = 'pendiente' and expira_en < :now"
    )
    assert "hogar_id" not in sql


# ------------------------------------------- frontera de vencimiento (RN-X-05, DC-42)

STALE_STATEMENTS = (
    invitations.EXPIRE_STALE_PENDING_SQL,
    invitations.EXPIRE_STALE_PENDING_FOR_EMAIL_SQL,
)
CURRENT_STATEMENTS = (
    invitations.HAS_PENDING_INVITATION_SQL,
    invitations.COUNT_PENDING_INVITATIONS_SQL,
    invitations.LIST_PENDING_INVITATIONS_SQL,
    invitations.LIST_RECEIVED_INVITATIONS_SQL,
)
_OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def _expiry_predicate_matches(statement: Any, expira_en: datetime, now: datetime) -> bool:
    """Evalúa en Python la única condición `expira_en <op> :now` de la sentencia."""
    (op,) = re.findall(r"expira_en (<=|>=|<|>) :now", normalized_sql(statement))
    return _OPERATORS[op](expira_en, now)


@pytest.mark.parametrize("statement", STALE_STATEMENTS)
@pytest.mark.parametrize(
    ("expira_en", "stale"),
    [
        (NOW - timedelta(microseconds=1), True),
        (NOW, False),  # exactamente en la frontera: todavía vigente
        (NOW + timedelta(microseconds=1), False),
    ],
    ids=["antes", "frontera", "después"],
)
def test_stale_means_expiry_strictly_before_now(
    statement: Any, expira_en: datetime, stale: bool
) -> None:
    """RN-X-05: «expirada cuando expira_en es anterior a la hora actual»."""
    assert _expiry_predicate_matches(statement, expira_en, NOW) is stale


@pytest.mark.parametrize("statement", CURRENT_STATEMENTS)
@pytest.mark.parametrize(
    ("expira_en", "current"),
    [
        (NOW - timedelta(microseconds=1), False),
        (NOW, True),  # exactamente en la frontera: vigente
        (NOW + timedelta(microseconds=1), True),
    ],
    ids=["antes", "frontera", "después"],
)
def test_current_means_expiry_at_or_after_now(
    statement: Any, expira_en: datetime, current: bool
) -> None:
    """RN-X-05: vigente ⇔ expira_en >= now (complemento exacto de vencida)."""
    assert _expiry_predicate_matches(statement, expira_en, NOW) is current


# ------------------------------------------------------- pendientes (DC-41, RN-II-02)


@pytest.mark.parametrize(("rows", "expected"), [([{"existe": 1}], True), ([], False)])
def test_has_pending_invitation(rows: list[dict[str, Any]], expected: bool) -> None:
    hogar_id = uuid4()
    session = FakeSession(rows)

    assert has_pending_invitation(session, hogar_id, CORREO, NOW) is expected  # type: ignore[arg-type]

    (statement, params) = session.calls[0]
    assert params == {"hogar_id": hogar_id, "correo": CORREO, "now": NOW}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "where hogar_id = :hogar_id" in sql
    assert "and estado = 'pendiente'" in sql
    assert "and expira_en >= :now" in sql
    assert sql.endswith("limit 1")


@pytest.mark.parametrize(("rows", "expected"), [([{"total": 3}], 3), ([], 0)])
def test_count_pending_invitations(rows: list[dict[str, Any]], expected: int) -> None:
    hogar_id = uuid4()
    session = FakeSession(rows)

    total = count_pending_invitations(session, hogar_id, NOW)  # type: ignore[arg-type]

    assert total == expected
    assert isinstance(total, int)
    (statement, params) = session.calls[0]
    assert params == {"hogar_id": hogar_id, "now": NOW}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "select count(*) as total from invitaciones_hogar where hogar_id = :hogar_id "
        "and estado = 'pendiente' and expira_en >= :now"
    )


def test_list_pending_invitations_filters_orders_and_maps() -> None:
    hogar_id = uuid4()
    first = _invitation_row(hogar_id=str(hogar_id), id=str(uuid4()), invitado_por=None)
    second = _invitation_row(hogar_id=hogar_id, created_at=NOW - timedelta(days=1))
    session = FakeSession([first, second])

    rows = list_pending_invitations(session, hogar_id, NOW)  # type: ignore[arg-type]

    (statement, params) = session.calls[0]
    assert params == {"hogar_id": hogar_id, "now": NOW}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "from invitaciones_hogar where hogar_id = :hogar_id" in sql
    assert "and estado = 'pendiente' and expira_en >= :now" in sql
    assert sql.endswith("order by created_at desc, id")
    assert [row.id for row in rows] == [UUID(first["id"]), second["id"]]
    assert all(row.hogar_id == hogar_id for row in rows)
    assert rows[0].invitado_por is None
    assert isinstance(rows[0], InvitationRow)


# --------------------------------------------------------------- alta (RN-X-05)


def _insert(session: FakeSession, **overrides: Any) -> InvitationRow:
    values: dict[str, Any] = {
        "hogar_id": uuid4(),
        "correo_invitado": "invitada.prueba@example.com",
        "invitado_por": uuid4(),
        "token_hash": TOKEN_HASH,
        "expira_en": NOW + timedelta(days=7),
        "created_at": NOW,
    }
    values.update(overrides)
    return insert_invitation(session, **values)  # type: ignore[arg-type]


def test_insert_invitation_sql_params_and_mapping() -> None:
    hogar_id, invitado_por, invitacion_id = uuid4(), uuid4(), uuid4()
    expira_en = NOW + timedelta(days=7)
    stored = _invitation_row(
        id=str(invitacion_id),
        hogar_id=str(hogar_id),
        invitado_por=str(invitado_por),
        expira_en=expira_en,
    )
    session = FakeSession([stored])

    row = _insert(
        session,
        hogar_id=hogar_id,
        invitado_por=invitado_por,
        expira_en=expira_en,
    )

    (statement, params) = session.calls[0]
    assert params == {
        "hogar_id": hogar_id,
        "correo_invitado": "invitada.prueba@example.com",
        "invitado_por": invitado_por,
        "token_hash": TOKEN_HASH,
        "expira_en": expira_en,
        "created_at": NOW,
    }
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql.startswith(
        "insert into invitaciones_hogar "
        "(hogar_id, correo_invitado, invitado_por, token_hash, estado, expira_en, created_at) "
        "values (:hogar_id, :correo_invitado, :invitado_por, :token_hash, 'pendiente', :expira_en, "
        ":created_at) returning"
    )
    assert row == InvitationRow(
        id=invitacion_id,
        hogar_id=hogar_id,
        correo_invitado="invitada.prueba@example.com",
        invitado_por=invitado_por,
        estado="pendiente",
        expira_en=expira_en,
        respondida_en=None,
        created_at=NOW,
    )
    assert session.commits == 0


class _FakeDiag:
    def __init__(self, constraint_name: str | None) -> None:
        self.constraint_name = constraint_name


class _FakeDriverError(Exception):
    """Imita la excepción de psycopg2: `pgcode`, `diag` (si viene) y el mensaje con el índice."""

    def __init__(
        self, pgcode: str | None, *, message: str = "", diag: _FakeDiag | None = None
    ) -> None:
        super().__init__(message)
        self.pgcode = pgcode
        if diag is not None:
            self.diag = diag


def _unique_message(constraint: str) -> str:
    return (
        f'duplicate key value violates unique constraint "{constraint}"\n'
        "DETAIL: Key (hogar_id, lower(correo_invitado))=(x, invitada.prueba@example.com) exists."
    )


def _integrity_error(orig: Exception) -> IntegrityError:
    return IntegrityError("insert into invitaciones_hogar ...", {}, orig)


@pytest.mark.parametrize(
    "orig",
    [
        _FakeDriverError("23505", diag=_FakeDiag("uq_invitacion_pendiente_hogar_correo")),
        _FakeDriverError("23505", message=_unique_message("uq_invitacion_pendiente_hogar_correo")),
        _FakeDriverError(
            "23505",
            message=_unique_message("uq_invitacion_pendiente_hogar_correo"),
            diag=_FakeDiag(None),
        ),
    ],
    ids=["diag", "sin diag", "diag sin nombre"],
)
def test_insert_invitation_raises_pending_exists_without_leaking_the_email(
    orig: Exception,
) -> None:
    """DC-41: el índice único cierra la carrera entre dos invitaciones al mismo correo."""
    session = FakeSession(_integrity_error(orig))

    with pytest.raises(PendingInvitationExistsError) as exc_info:
        _insert(session)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert "@" not in str(exc_info.value)
    assert TOKEN_HASH not in str(exc_info.value)
    assert not isinstance(exc_info.value, IntegrityError)


@pytest.mark.parametrize(
    "orig",
    [
        _FakeDriverError("23505", diag=_FakeDiag("invitaciones_hogar_token_hash_key")),
        _FakeDriverError("23505", message=_unique_message("invitaciones_hogar_token_hash_key")),
        _FakeDriverError(
            "23505",
            message=_unique_message("uq_invitacion_pendiente_hogar_correo"),
            diag=_FakeDiag("invitaciones_hogar_token_hash_key"),
        ),
        _FakeDriverError("23505"),
        _FakeDriverError("23503", diag=_FakeDiag("invitaciones_hogar_hogar_id_fkey")),
        _FakeDriverError("23503", message=_unique_message("uq_invitacion_pendiente_hogar_correo")),
        _FakeDriverError(None),
        psycopg2.errors.UniqueViolation(),
    ],
    ids=[
        "hash duplicado en diag",
        "hash duplicado en el mensaje",
        "diag manda sobre el mensaje",
        "23505 sin nombre",
        "FK del hogar",
        "otro SQLSTATE con el nombre",
        "sin SQLSTATE",
        "excepción real de psycopg2 sin datos",
    ],
)
def test_insert_invitation_reraises_any_other_integrity_error(orig: Exception) -> None:
    error = _integrity_error(orig)
    session = FakeSession(error)

    with pytest.raises(IntegrityError) as exc_info:
        _insert(session)

    assert exc_info.value is error


# ------------------------------------------------------ lectura por id y por hash


@pytest.mark.parametrize(
    ("for_update", "statement"),
    [
        (False, invitations.INVITATION_BY_ID_SQL),
        (True, invitations.INVITATION_BY_ID_FOR_UPDATE_SQL),
    ],
)
def test_get_invitation_by_id_with_and_without_lock(for_update: bool, statement: Any) -> None:
    invitacion_id = uuid4()
    stored = _invitation_row(id=str(invitacion_id), estado="aceptada", respondida_en=NOW)
    session = FakeSession([stored])

    row = get_invitation(session, invitacion_id, for_update=for_update)  # type: ignore[arg-type]

    (executed, params) = session.calls[0]
    assert executed is statement
    assert params == {"invitacion_id": invitacion_id}
    assert_bound_only(executed, params)
    sql = normalized_sql(executed)
    assert "from invitaciones_hogar where id = :invitacion_id" in sql
    assert sql.endswith(" for update") is for_update
    assert row is not None
    assert row.id == invitacion_id
    assert row.estado == "aceptada"
    assert row.respondida_en == NOW


def test_get_invitation_returns_none_without_row() -> None:
    assert get_invitation(FakeSession(), uuid4()) is None  # type: ignore[arg-type]


def test_get_invitation_by_token_hash_binds_the_hash() -> None:
    stored = _invitation_row()
    session = FakeSession([stored])

    row = get_invitation_by_token_hash(session, TOKEN_HASH)  # type: ignore[arg-type]

    (statement, params) = session.calls[0]
    assert params == {"token_hash": TOKEN_HASH}
    assert_bound_only(statement, params)
    assert normalized_sql(statement).endswith(
        "from invitaciones_hogar where token_hash = :token_hash"
    )
    assert row is not None
    assert row.id == stored["id"]


def test_get_invitation_by_token_hash_returns_none_without_row() -> None:
    assert get_invitation_by_token_hash(FakeSession(), TOKEN_HASH) is None  # type: ignore[arg-type]


def test_invitation_dates_keep_their_time_zone() -> None:
    expira_en = datetime(2026, 12, 2, 10, 0, tzinfo=BOGOTA)
    session = FakeSession([_invitation_row(expira_en=expira_en)])

    row = get_invitation(session, uuid4())  # type: ignore[arg-type]

    assert row is not None
    assert row.expira_en == expira_en
    assert row.expira_en.tzinfo is BOGOTA


# ---------------------------------------------------------- cambio de estado (RN-X-06)


@pytest.mark.parametrize(
    ("estado", "respondida_en"),
    [("aceptada", NOW), ("rechazada", NOW), ("expirada", None), ("revocada", None)],
)
def test_set_invitation_state_only_changes_pending_rows(
    estado: str, respondida_en: datetime | None
) -> None:
    invitacion_id = uuid4()
    session = FakeSession([{"id": invitacion_id}])

    changed = set_invitation_state(session, invitacion_id, estado, respondida_en)  # type: ignore[arg-type]

    assert changed is True
    (statement, params) = session.calls[0]
    assert params == {
        "invitacion_id": invitacion_id,
        "estado": estado,
        "respondida_en": respondida_en,
    }
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "update invitaciones_hogar set estado = :estado, respondida_en = :respondida_en "
        "where id = :invitacion_id and estado = 'pendiente' returning id"
    )


def test_set_invitation_state_returns_false_when_no_longer_pending() -> None:
    assert set_invitation_state(FakeSession(), uuid4(), "rechazada", NOW) is False  # type: ignore[arg-type]


@pytest.mark.parametrize("estado", ["pendiente", "cancelada", ""])
def test_set_invitation_state_rejects_unknown_states_without_sql(estado: str) -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        set_invitation_state(session, uuid4(), estado, None)  # type: ignore[arg-type]

    assert session.calls == []


# --------------------------------------------------------- recibidas (RN-X-06)


def test_list_received_invitations_filters_email_state_and_expiry() -> None:
    session = FakeSession([_received_row()])

    list_received_invitations(session, CORREO, NOW)  # type: ignore[arg-type]

    (statement, params) = session.calls[0]
    assert params == {"correo": CORREO, "now": NOW}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "join hogares h on h.id = i.hogar_id" in sql
    assert "left join usuarios u on u.id = i.invitado_por" in sql
    assert "where lower(i.correo_invitado) = lower(:correo)" in sql
    assert "and i.estado = 'pendiente' and i.expira_en >= :now" in sql
    assert sql.endswith("order by i.created_at desc, i.id")


def test_received_projection_falls_back_to_the_current_active_admin_name() -> None:
    """DC-36 (TODO pendiente en invitations.py): sin invitado_por, el nombre del admin activo."""
    sql = normalized_sql(invitations.LIST_RECEIVED_INVITATIONS_SQL)

    assert "coalesce(u.nombre_completo, adm.nombre_completo) as invitado_por_nombre" in sql
    assert "left join lateral (" in sql
    assert (
        "where m.hogar_id = i.hogar_id and m.rol = 'administrador' and m.estado = 'activo'" in sql
    )
    assert "limit 1 ) adm on true" in sql


def test_list_received_invitations_maps_rows() -> None:
    first = _received_row(id=str(uuid4()), hogar_id=str(uuid4()))
    second = _received_row(invitado_por_nombre=None)
    session = FakeSession([first, second])

    rows = list_received_invitations(session, CORREO, NOW)  # type: ignore[arg-type]

    assert rows == [
        ReceivedInvitationRow(
            id=UUID(first["id"]),
            hogar_id=UUID(first["hogar_id"]),
            hogar_nombre="Casa de prueba",
            invitado_por_nombre="Persona administradora",
            expira_en=first["expira_en"],
        ),
        ReceivedInvitationRow(
            id=second["id"],
            hogar_id=second["hogar_id"],
            hogar_nombre="Casa de prueba",
            invitado_por_nombre=None,
            expira_en=second["expira_en"],
        ),
    ]


def test_get_received_invitation_uses_the_same_projection_by_id() -> None:
    invitacion_id = uuid4()
    session = FakeSession([_received_row(id=invitacion_id)])

    row = get_received_invitation(session, invitacion_id)  # type: ignore[arg-type]

    (statement, params) = session.calls[0]
    assert params == {"invitacion_id": invitacion_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    projection = normalized_sql(invitations.LIST_RECEIVED_INVITATIONS_SQL).split(" where lower(")[0]
    assert sql.startswith(projection)
    assert sql.endswith("where i.id = :invitacion_id")
    assert row is not None
    assert row.id == invitacion_id


def test_get_received_invitation_returns_none_without_row() -> None:
    assert get_received_invitation(FakeSession(), uuid4()) is None  # type: ignore[arg-type]
