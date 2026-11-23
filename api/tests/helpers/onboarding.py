"""Dobles del onboarding: `app.data.*` en memoria para app.services.onboarding (sin base ni red).

`FakeDatabase` hace de sesión y de tablas: distingue lo pendiente de lo guardado, así que una
reversión deja todo vacío. Lo usan tests/services/test_onboarding_service.py, B-02
(tests/backfill/test_b02_forced_failure_rollback.py) y C-01 (tests/contract/). El simulador y
las reglas de zonas siguen siendo los reales, con los perfiles de `docs/datos/perfiles/`.
"""

from collections.abc import Sequence
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import readings as readings_data
from app.data import simulation_profiles as profiles_data
from app.data.households import HouseholdRow, SensorToInsert, ZoneToInsert
from app.data.memberships import MembershipSummaryRow
from app.data.simulation_profiles import SimulationProfileRow
from app.domain.simulator import TIMEZONE
from app.domain.zone_rules import BASIC_ZONES
from app.errors import ApiError
from app.schemas.households import Hogar
from app.schemas.onboarding import OnboardingCrear
from app.services import onboarding as service
from tests.simulator.support import final_profiles, frozen_references

USER_ID = UUID("6f1c2d3e-4a5b-4c6d-8e7f-90a1b2c3d4e5")
EMAIL = "persona@example.com"
HOUSEHOLD_NAME = f"Hogar Secreto {EMAIL}"
NOW = datetime(2026, 11, 22, 15, 23, tzinfo=TIMEZONE)
LAST_HOUR = datetime(2026, 11, 22, 14, tzinfo=TIMEZONE)

# Hogar de referencia (vivienda, zonas) de cada personalidad: sección 8.1 y congelamiento.
REFERENCE_HOUSEHOLDS: dict[str, tuple[str, tuple[str, ...]]] = {
    name: (reference["vivienda"], tuple(reference["zonas"]))
    for name, reference in frozen_references().items()
}
TABLES = ("hogares", "hogar_miembros", "zonas", "fuentes_principales", "sensores_zona", "lecturas")

# Cada paso posterior a la validación de zonas, en el orden exigido por RN-X-03.
STEPS = (
    "get_active_membership_of_user",
    "get_profiles",
    "validate_or_raise",
    "insert_household",
    "insert_admin_membership",
    "insert_zones",
    "insert_main_source",
    "insert_zone_sensors",
    "generate_backfill",
    "insert_readings_batch",
    "commit",
)


class FakeDatabase:
    """Sesión y tablas en memoria. `pending` es la transacción abierta; `saved`, lo confirmado."""

    def __init__(self) -> None:
        self.saved: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
        self.pending: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
        self.events: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self.membership: MembershipSummaryRow | None = None
        self.profiles: dict[str, SimulationProfileRow] = {
            name: SimulationProfileRow(id=uuid4(), nombre=name, activo=True, params=params)
            for name, params in final_profiles().items()
        }
        self.requested_profiles: list[str] = []
        self.used_profiles: list[str] = []
        # Paso → excepción que lanza; paso → filas que faltan en el conteo devuelto.
        self.failures: dict[str, Exception] = {}
        self.rollback_failure: Exception | None = None
        self.short_counts: dict[str, int] = {}

    # --- sesión
    def commit(self) -> None:
        self.step("commit")
        for table, rows in self.pending.items():
            self.saved[table].extend(rows)
            rows.clear()
        self.commits += 1

    def rollback(self) -> None:
        self.events.append("rollback")
        self.rollbacks += 1
        if self.rollback_failure is not None:
            raise self.rollback_failure
        for rows in self.pending.values():
            rows.clear()

    def exec(self, *_args: Any, **_kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("el servicio no debe ejecutar SQL directamente")

    # --- apoyo
    def step(self, name: str) -> None:
        self.events.append(name)
        failure = self.failures.get(name)
        if failure is not None:
            raise failure

    def counted(self, name: str, total: int) -> int:
        return total - self.short_counts.get(name, 0)

    def set_active(self, name: str, active: bool) -> None:
        row = self.profiles[name]
        self.profiles[name] = SimulationProfileRow(
            id=row.id, nombre=name, activo=active, params={**row.params, "activo": active}
        )

    def assert_nothing_saved(self) -> None:
        assert self.commits == 0
        assert all(not rows for rows in self.saved.values())
        assert all(not rows for rows in self.pending.values())

    # --- app.data.*
    def get_active_membership_of_user(
        self, session: Any, usuario_id: UUID
    ) -> MembershipSummaryRow | None:
        assert session is self and usuario_id == USER_ID
        self.step("get_active_membership_of_user")
        return self.membership

    def get_profiles(self, session: Any, names: Sequence[str]) -> dict[str, SimulationProfileRow]:
        assert session is self
        self.step("get_profiles")
        self.requested_profiles = list(names)
        return {name: self.profiles[name] for name in names if name in self.profiles}

    def insert_household(
        self,
        session: Any,
        *,
        hogar_id: UUID,
        nombre: str,
        tipo_vivienda: str,
        perfil_simulacion_id: UUID,
    ) -> HouseholdRow:
        assert session is self
        assert type(tipo_vivienda) is str
        self.step("insert_household")
        self.pending["hogares"].append(
            {
                "id": hogar_id,
                "nombre": nombre,
                "tipo_vivienda": tipo_vivienda,
                "perfil_simulacion_id": perfil_simulacion_id,
            }
        )
        # Valores por defecto de la tabla (RN-II-03).
        return HouseholdRow(hogar_id, nombre, tipo_vivienda, True, True, True, False)

    def insert_admin_membership(
        self, session: Any, *, hogar_id: UUID, usuario_id: UUID, joined_at: datetime
    ) -> None:
        assert session is self
        self.step("insert_admin_membership")
        assert hogar_id in {row["id"] for row in self.pending["hogares"]}
        self.pending["hogar_miembros"].append(
            {"hogar_id": hogar_id, "usuario_id": usuario_id, "fecha_ingreso": joined_at}
        )

    def insert_zones(self, session: Any, hogar_id: UUID, zones: Sequence[ZoneToInsert]) -> int:
        assert session is self
        self.step("insert_zones")
        assert hogar_id in {row["id"] for row in self.pending["hogares"]}
        self.pending["zonas"].extend(
            {"id": zone.id, "hogar_id": hogar_id, "tipo": zone.tipo, "nombre": zone.nombre}
            for zone in zones
        )
        return self.counted("insert_zones", len(zones))

    def insert_main_source(
        self, session: Any, *, fuente_id: UUID, hogar_id: UUID, nombre: str
    ) -> None:
        assert session is self
        self.step("insert_main_source")
        assert hogar_id in {row["id"] for row in self.pending["hogares"]}
        self.pending["fuentes_principales"].append(
            {"id": fuente_id, "hogar_id": hogar_id, "nombre": nombre}
        )

    def insert_zone_sensors(
        self,
        session: Any,
        *,
        hogar_id: UUID,
        fuente_id: UUID,
        sensors: Sequence[SensorToInsert],
    ) -> int:
        """Como el INSERT…SELECT real: solo zonas y fuente del mismo hogar (DC-38)."""
        assert session is self
        self.step("insert_zone_sensors")
        zones = {row["id"] for row in self.pending["zonas"] if row["hogar_id"] == hogar_id}
        sources = {
            row["id"] for row in self.pending["fuentes_principales"] if row["hogar_id"] == hogar_id
        }
        accepted = [s for s in sensors if s.zona_id in zones and fuente_id in sources]
        self.pending["sensores_zona"].extend(
            {"id": s.id, "zona_id": s.zona_id, "fuente_principal_id": fuente_id} for s in accepted
        )
        return self.counted("insert_zone_sensors", len(accepted))

    def insert_readings_batch(self, session: Any, lecturas: Sequence[dict[str, Any]]) -> int:
        """Una llamada por lote; ON CONFLICT DO NOTHING por (sensor, hora)."""
        assert session is self
        self.step("insert_readings_batch")
        sensors = {row["id"] for row in self.pending["sensores_zona"]}
        rows = {(row["sensor_id"], row["fecha_hora"]): dict(row) for row in lecturas}
        assert {sensor for sensor, _ in rows} <= sensors
        self.pending["lecturas"].extend(rows.values())
        return self.counted("insert_readings_batch", len(rows))


def install_fake_database(monkeypatch: pytest.MonkeyPatch) -> FakeDatabase:
    """Reemplaza `app.data.*` y registra el paso por el simulador (que sigue siendo el real)."""
    fake = FakeDatabase()
    for module, names in (
        (memberships_data, ("get_active_membership_of_user", "insert_admin_membership")),
        (profiles_data, ("get_profiles",)),
        (
            households_data,
            ("insert_household", "insert_zones", "insert_main_source", "insert_zone_sensors"),
        ),
        (readings_data, ("insert_readings_batch",)),
    ):
        for name in names:
            monkeypatch.setattr(module, name, getattr(fake, name))

    real_validate, real_generate = service.validate_or_raise, service.generate_backfill

    def validate_or_raise(profile: Any) -> Any:
        fake.step("validate_or_raise")
        return real_validate(profile)

    def generate_backfill(hogar_id: UUID, profile: Any, sensors: Any, now: datetime) -> Any:
        fake.step("generate_backfill")
        fake.used_profiles.append(profile["nombre"])
        return real_generate(hogar_id, profile, sensors, now)

    monkeypatch.setattr(service, "validate_or_raise", validate_or_raise)
    monkeypatch.setattr(service, "generate_backfill", generate_backfill)
    return fake


def make_payload(
    housing: str = "apartamento", zones: Sequence[str] = BASIC_ZONES, name: str = HOUSEHOLD_NAME
) -> OnboardingCrear:
    return OnboardingCrear(nombre_hogar=name, tipo_vivienda=housing, zonas=list(zones))


def run(
    db: FakeDatabase, payload: OnboardingCrear | None = None, now: datetime | None = NOW
) -> Hogar:
    return service.create_household_onboarding(
        db,  # type: ignore[arg-type]
        USER_ID,
        payload or make_payload(),
        now,
    )


def run_error(db: FakeDatabase, payload: OnboardingCrear | None = None) -> ApiError:
    with pytest.raises(ApiError) as caught:
        run(db, payload)
    return caught.value


def missing_profile_error() -> IntegrityError:
    """El 23503 de Postgres tal como llega: el mensaje y el DETAIL llevan el id del usuario."""

    class ForeignKeyViolation(Exception):
        pgcode = "23503"
        diag = SimpleNamespace(constraint_name="hogar_miembros_usuario_id_fkey")

    orig = ForeignKeyViolation(
        f"DETAIL:  Key (usuario_id)=({USER_ID}) is not present in table usuarios. {HOUSEHOLD_NAME}"
    )
    return IntegrityError(f"insert … {USER_ID}", {"nombre": HOUSEHOLD_NAME}, orig)
