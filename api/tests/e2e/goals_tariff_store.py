"""Metas, tarifas y fuentes de datos en el almacén en memoria de los e2e (fase 10).

`GoalsTariffMixin` le enseña al almacén de `test_onboarding_e2e` (`Store`, a través de
`ConsumptionStore`) las sentencias de `app.data` que leen y escriben `metas_consumo`,
`tarifas_hogar`, `fuentes_principales` y `sensores_zona`, imitando la semántica del SQL y las
restricciones de `supabase/migrations/` 0002 y 0003 que tocan esas filas:

- **Metas** (`data/goals.py`): `ACTIVE_GOAL_SQL` (la fila 'activa' del hogar),
  `DEACTIVATE_ACTIVE_GOAL_SQL` (UPDATE de la activa a 'inactiva' con `fecha_fin`; rowcount) e
  `INSERT_GOAL_SQL` (RETURNING). Restricciones: `metas_rango_valido` (`fecha_fin` nula o
  `> fecha_inicio`, 23514), checks de `tipo` y `valor_kwh_mensual > 0` (23514), clave foránea a
  `hogares` (23503) y el único parcial `uq_meta_activa_por_hogar` (una activa por hogar, 23505).
- **Tarifas** (`data/tariffs.py`): `CURRENT_TARIFF_SQL` y `TARIFFS_BETWEEN_SQL` (vigencia
  [desde, hasta), DC-39), `OPEN_TARIFF_SQL` (`vigente_hasta` nula), `CLOSE_TARIFF_SQL` (UPDATE
  con `id` y `hogar_id`, R-01) e `INSERT_TARIFF_SQL` (RETURNING). Restricciones:
  `tarifas_rango_valido` (`vigente_hasta` nula o `> vigente_desde`, 23514), checks de precio y
  cargo fijo ≥ 0 (23514), `numeric(12,2)` (se redondea a 2 decimales como PostgreSQL), clave
  foránea a `hogares` (23503), la exclusión `tarifas_sin_solapamiento`
  (`daterange(desde, hasta, '[)') &&` en el mismo hogar, 23P01; se comprueba antes que el único
  porque la crea la 0002) y el único parcial `uq_tarifa_abierta_por_hogar` (0003, 23505).
- **Fuentes de datos** (`data/households.py`): `MAIN_SOURCE_SQL` (la fuente del hogar) y
  `ZONE_SENSORS_SQL` (sensores JOIN zonas del hogar, sin filtrar estados, por id de zona).
- **Comprobación bajo bloqueo** de `crearMeta` y `crearTarifa` (después de `LOCK_HOUSEHOLD_SQL`):
  `USER_MEMBERSHIP_IN_HOUSEHOLD[_FOR_UPDATE]_SQL` (la membresía 'activo' de quien llama en el
  hogar; FOR UPDATE no espera de verdad) y `HOUSEHOLD_SQL` (el hogar con sus 4 permisos).

`created_at` y `updated_at` (`default now()`) toman el reloj del servicio que escribe
(`goals_tariff.datetime`, fijado por la prueba). Las metas y tarifas «sembradas» por las pruebas
de fases anteriores van como filas confirmadas de esas tablas (`seed_goal_row`, `seed_tariffs`).
`assert_goal_tariff_invariants()` comprueba al final de una prueba las restricciones sobre lo
confirmado.

El SQL no se ejecuta: que PostgreSQL haga lo mismo queda pendiente (I-02 y R-01 sobre Postgres
real).

Reglas: RN-V-01, RN-V-02, RN-V-03, RN-XVI-04, RN-XVI-05, RN-XVI-06, RN-III-03. Decisiones: DC-39,
DC-41 y D3, D4, D5 de la fase 10.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

from app.data import goals as goals_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import tariffs as tariffs_data
from app.services import goals_tariff as goals_tariff_service
from tests.data.fake_session import FakeResult
from tests.e2e.test_onboarding_e2e import Params, StoreSession

GOAL_TYPES = ("ahorro", "eficiencia", "presupuesto")
GOAL_COLUMNS = ("id", "tipo", "valor_kwh_mensual", "fecha_inicio")
GOAL_RETURNING = (*GOAL_COLUMNS, "estado", "fecha_fin")
TARIFF_COLUMNS = (
    "id",
    "precio_kwh",
    "cargo_fijo_mensual",
    "vigente_desde",
    "vigente_hasta",
    "operador",
)
CENTS = Decimal("0.01")  # numeric(12,2) de precio_kwh y cargo_fijo_mensual


def overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """`daterange(desde, hasta, '[)') && daterange(…)`; `hasta` nula = sin fin."""
    a_end, b_end = a["vigente_hasta"], b["vigente_hasta"]
    return (b_end is None or a["vigente_desde"] < b_end) and (
        a_end is None or b["vigente_desde"] < a_end
    )


def _numeric_12_2(value: Any) -> Decimal | None:
    """Como `numeric(12,2)`: redondeo a 2 decimales, mitad hacia arriba (PostgreSQL)."""
    if value is None:
        return None
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


class GoalsTariffMixin:
    """Sentencias de metas, tarifas y fuentes para un `Store` (ver el módulo).

    Se mezcla delante de `RecoveryStore` (`class ConsumptionStore(GoalsTariffMixin, RecoveryStore)`).
    """

    committed: dict[str, dict[Any, dict[str, Any]]]
    handlers: dict[int, tuple[str, Any]]

    def register_goals_tariff(self) -> None:
        for module, name, handler in (
            (goals_data, "ACTIVE_GOAL_SQL", self._active_goal),
            (goals_data, "DEACTIVATE_ACTIVE_GOAL_SQL", self._deactivate_active_goal),
            (goals_data, "INSERT_GOAL_SQL", self._insert_goal),
            (tariffs_data, "CURRENT_TARIFF_SQL", self._current_tariff),
            (tariffs_data, "TARIFFS_BETWEEN_SQL", self._tariffs_between),
            (tariffs_data, "OPEN_TARIFF_SQL", self._open_tariff),
            (tariffs_data, "CLOSE_TARIFF_SQL", self._close_tariff),
            (tariffs_data, "INSERT_TARIFF_SQL", self._insert_tariff),
            (households_data, "MAIN_SOURCE_SQL", self._main_source),
            (households_data, "ZONE_SENSORS_SQL", self._zone_sensors),
            # La comprobación bajo bloqueo de crearMeta y crearTarifa (las mismas sentencias de
            # la fase 9; `MembersStore` las vuelve a registrar con su propio intérprete).
            (households_data, "HOUSEHOLD_SQL", self._household_permissions),
            (memberships_data, "USER_MEMBERSHIP_IN_HOUSEHOLD_SQL", self._own_membership),
            (memberships_data, "USER_MEMBERSHIP_IN_HOUSEHOLD_FOR_UPDATE_SQL", self._own_membership),
        ):
            self.handlers[id(getattr(module, name))] = (name, handler)

    @staticmethod
    def now() -> datetime:
        """`now()` de la transacción: el reloj del servicio de metas y tarifa."""
        return goals_tariff_service.datetime.now(UTC)

    # --- semilla (ya confirmada) y lo que miran las pruebas -------------------------------

    def seed_goal_row(
        self,
        hogar_id: UUID,
        meta_id: UUID,
        valor_kwh_mensual: Decimal,
        fecha_inicio: date,
        *,
        tipo: str = "ahorro",
        created_at: datetime,
    ) -> None:
        """Meta 'activa' y abierta confirmada (como la dejaría `crearMeta`)."""
        self.committed["metas_consumo"][meta_id] = {
            "id": meta_id,
            "hogar_id": hogar_id,
            "tipo": tipo,
            "valor_kwh_mensual": valor_kwh_mensual,
            "estado": "activa",
            "fecha_inicio": fecha_inicio,
            "fecha_fin": None,
            "created_at": created_at,
            "updated_at": created_at,
        }

    def seed_tariffs(self, hogar_id: UUID, rows: list[dict[str, Any]]) -> None:
        """Reemplaza las tarifas confirmadas del hogar (filas con las columnas de TARIFF_COLUMNS)."""
        table = self.committed["tarifas_hogar"]
        for key in [k for k, row in table.items() if row["hogar_id"] == hogar_id]:
            del table[key]
        for row in rows:
            table[row["id"]] = {"operador": None, **row, "hogar_id": hogar_id}

    def goals_of(self, hogar_id: UUID) -> list[dict[str, Any]]:
        rows = [r for r in self.committed["metas_consumo"].values() if r["hogar_id"] == hogar_id]
        return sorted(rows, key=lambda r: (r["created_at"], str(r["id"])))

    def tariffs_of(self, hogar_id: UUID) -> list[dict[str, Any]]:
        rows = [r for r in self.committed["tarifas_hogar"].values() if r["hogar_id"] == hogar_id]
        return sorted(rows, key=lambda r: r["vigente_desde"])

    def assert_goal_tariff_invariants(self) -> None:
        """Restricciones de 0002/0003 sobre lo confirmado (metas y tarifas)."""
        goals = list(self.committed["metas_consumo"].values())
        active = Counter(row["hogar_id"] for row in goals if row["estado"] == "activa")
        assert all(count == 1 for count in active.values()), "uq_meta_activa_por_hogar"
        for row in goals:
            assert row["fecha_fin"] is None or row["fecha_fin"] > row["fecha_inicio"], row
        tariffs = list(self.committed["tarifas_hogar"].values())
        opened = Counter(row["hogar_id"] for row in tariffs if row["vigente_hasta"] is None)
        assert all(count == 1 for count in opened.values()), "uq_tarifa_abierta_por_hogar"
        for row in tariffs:
            hasta = row["vigente_hasta"]
            assert hasta is None or hasta > row["vigente_desde"], ("tarifas_rango_valido", row)
        for index, a in enumerate(tariffs):
            for b in tariffs[index + 1 :]:
                same = a["hogar_id"] == b["hogar_id"]
                assert not (same and overlaps(a, b)), ("tarifas_sin_solapamiento", a, b)

    # --- metas -----------------------------------------------------------------------------

    def _active_goal(self, session: StoreSession, params: Params) -> FakeResult:
        rows = [
            {column: row[column] for column in GOAL_COLUMNS}
            for row in self.view(session, "metas_consumo").values()
            if row["hogar_id"] == params["hogar_id"] and row["estado"] == "activa"
        ]
        return FakeResult(rows)

    def _deactivate_active_goal(self, session: StoreSession, params: Params) -> FakeResult:
        """UPDATE … SET estado='inactiva', fecha_fin, updated_at=now() WHERE hogar y 'activa'."""
        fecha_fin = params["fecha_fin"]
        changed = 0
        for key, row in self.view(session, "metas_consumo").items():
            if row["hogar_id"] != params["hogar_id"] or row["estado"] != "activa":
                continue
            self._require(
                fecha_fin is None or fecha_fin > row["fecha_inicio"], "23514", "metas_rango_valido"
            )
            closed = {**row, "estado": "inactiva", "fecha_fin": fecha_fin, "updated_at": self.now()}
            self.put(session, "metas_consumo", key, closed)
            changed += 1
        return FakeResult(rowcount=changed)

    def _insert_goal(self, session: StoreSession, params: Params) -> FakeResult:
        """INSERT 'activa' y abierta RETURNING; checks, clave foránea y la activa única."""
        hogar_id = params["hogar_id"]
        require = self._require
        require(params["tipo"] in GOAL_TYPES, "23514", "metas_consumo_tipo_check")
        valor = Decimal(str(params["valor_kwh_mensual"]))
        require(valor > 0, "23514", "metas_consumo_valor_kwh_mensual_check")
        require(
            hogar_id in self.view(session, "hogares"),
            "23503",
            "metas_consumo_hogar_id_fkey",
        )
        index = goals_data.ACTIVE_GOAL_INDEX
        self._claim_unique(session, (index, hogar_id))
        active = [
            row
            for row in self.view(session, "metas_consumo").values()
            if row["hogar_id"] == hogar_id and row["estado"] == "activa"
        ]
        require(not active, "23505", index)
        moment = self.now()
        row = {
            "id": uuid4(),
            "hogar_id": hogar_id,
            "tipo": params["tipo"],
            "valor_kwh_mensual": valor,
            "estado": "activa",
            "fecha_inicio": params["fecha_inicio"],
            "fecha_fin": None,
            "created_at": moment,
            "updated_at": moment,
        }
        self.put(session, "metas_consumo", row["id"], row)
        return FakeResult([{column: row[column] for column in GOAL_RETURNING}], rowcount=1)

    # --- tarifas ---------------------------------------------------------------------------

    def _household_tariffs(self, session: StoreSession, hogar_id: UUID) -> list[dict[str, Any]]:
        return [
            row
            for row in self.view(session, "tarifas_hogar").values()
            if row["hogar_id"] == hogar_id
        ]

    @staticmethod
    def _tariff_row(row: dict[str, Any]) -> dict[str, Any]:
        return {column: row[column] for column in TARIFF_COLUMNS}

    def _current_tariff(self, session: StoreSession, params: Params) -> FakeResult:
        today = params["today"]
        return FakeResult(
            [
                self._tariff_row(row)
                for row in self._household_tariffs(session, params["hogar_id"])
                if row["vigente_desde"] <= today
                and (row["vigente_hasta"] is None or row["vigente_hasta"] > today)
            ]
        )

    def _tariffs_between(self, session: StoreSession, params: Params) -> FakeResult:
        """Vigencia [desde, hasta) que toca [start, end] (inclusive), ORDER BY vigente_desde."""
        rows = [
            self._tariff_row(row)
            for row in self._household_tariffs(session, params["hogar_id"])
            if row["vigente_desde"] <= params["end"]
            and (row["vigente_hasta"] is None or row["vigente_hasta"] > params["start"])
        ]
        return FakeResult(sorted(rows, key=lambda row: row["vigente_desde"]))

    def _open_tariff(self, session: StoreSession, params: Params) -> FakeResult:
        return FakeResult(
            [
                self._tariff_row(row)
                for row in self._household_tariffs(session, params["hogar_id"])
                if row["vigente_hasta"] is None
            ]
        )

    def _check_no_overlap(self, session: StoreSession, row: dict[str, Any]) -> None:
        """Exclusión `tarifas_sin_solapamiento` contra las demás tarifas del hogar (23P01)."""
        others = [r for r in self._household_tariffs(session, row["hogar_id"]) if r["id"] != row["id"]]
        self._require(
            not any(overlaps(row, other) for other in others),
            "23P01",
            tariffs_data.OVERLAP_CONSTRAINT,
        )

    def _close_tariff(self, session: StoreSession, params: Params) -> FakeResult:
        """UPDATE … SET vigente_hasta, updated_at=now() WHERE id AND hogar_id (R-01)."""
        row = self.view(session, "tarifas_hogar").get(params["tarifa_id"])
        if row is None or row["hogar_id"] != params["hogar_id"]:
            return FakeResult(rowcount=0)
        hasta = params["vigente_hasta"]
        self._require(
            hasta is None or hasta > row["vigente_desde"], "23514", tariffs_data.RANGE_CONSTRAINT
        )
        closed = {**row, "vigente_hasta": hasta, "updated_at": self.now()}
        self._check_no_overlap(session, closed)
        self.put(session, "tarifas_hogar", row["id"], closed)
        return FakeResult(rowcount=1)

    def _insert_tariff(self, session: StoreSession, params: Params) -> FakeResult:
        """INSERT abierta RETURNING; checks, clave foránea, exclusión y la abierta única."""
        hogar_id = params["hogar_id"]
        require = self._require
        precio = _numeric_12_2(params["precio_kwh"])
        cargo = _numeric_12_2(params["cargo_fijo_mensual"])
        require(precio is not None and precio >= 0, "23514", "tarifas_hogar_precio_kwh_check")
        require(cargo is None or cargo >= 0, "23514", "tarifas_hogar_cargo_fijo_mensual_check")
        require(
            hogar_id in self.view(session, "hogares"),
            "23503",
            "tarifas_hogar_hogar_id_fkey",
        )
        moment = self.now()
        row = {
            "id": uuid4(),
            "hogar_id": hogar_id,
            "operador": params["operador"],
            "precio_kwh": precio,
            "cargo_fijo_mensual": cargo,
            "vigente_desde": params["vigente_desde"],
            "vigente_hasta": None,
            "created_at": moment,
            "updated_at": moment,
        }
        self._check_no_overlap(session, row)
        index = tariffs_data.OPEN_TARIFF_INDEX
        self._claim_unique(session, (index, hogar_id))
        opened = [r for r in self._household_tariffs(session, hogar_id) if r["vigente_hasta"] is None]
        require(not opened, "23505", index)
        self.put(session, "tarifas_hogar", row["id"], row)
        return FakeResult([self._tariff_row(row)], rowcount=1)

    # --- comprobación bajo bloqueo (membresía propia y permisos del hogar) -----------------

    def _own_membership(self, session: StoreSession, params: Params) -> FakeResult:
        return FakeResult(
            [
                {
                    "membresia_id": row["id"],
                    "hogar_id": row["hogar_id"],
                    "usuario_id": row["usuario_id"],
                    "rol": row["rol"],
                    "estado": row["estado"],
                }
                for row in self.view(session, "hogar_miembros").values()
                if (row["hogar_id"], row["usuario_id"]) == (params["hogar_id"], params["usuario_id"])
                and row["estado"] == "activo"
            ]
        )

    def _household_permissions(self, session: StoreSession, params: Params) -> FakeResult:
        row = self.view(session, "hogares").get(params["hogar_id"])
        if row is None:
            return FakeResult()
        columns = ("id", "nombre", "tipo_vivienda", *households_data.PERMISSION_COLUMNS.values())
        return FakeResult([{column: row[column] for column in columns}])

    # --- fuentes de datos ------------------------------------------------------------------

    def _main_source(self, session: StoreSession, params: Params) -> FakeResult:
        return FakeResult(
            [
                {column: row[column] for column in ("id", "nombre", "estado")}
                for row in self.view(session, "fuentes_principales").values()
                if row["hogar_id"] == params["hogar_id"]
            ]
        )

    def _zone_sensors(self, session: StoreSession, params: Params) -> FakeResult:
        """sensores_zona JOIN zonas WHERE zonas.hogar_id ORDER BY zonas.id (sin filtrar estados)."""
        zones = {
            key: row
            for key, row in self.view(session, "zonas").items()
            if row["hogar_id"] == params["hogar_id"]
        }
        rows = [
            {
                "sensor_id": sensor["id"],
                "zona_id": sensor["zona_id"],
                "zona_tipo": zones[sensor["zona_id"]]["tipo"],
                "zona_estado": zones[sensor["zona_id"]]["estado"],
                "sensor_estado": sensor["estado"],
            }
            for sensor in self.view(session, "sensores_zona").values()
            if sensor["zona_id"] in zones
        ]
        return FakeResult(sorted(rows, key=lambda row: row["zona_id"]))
