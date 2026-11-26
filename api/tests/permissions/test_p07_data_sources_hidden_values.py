"""P-07 · Permisos: Fuentes de datos sin permiso.

Esperado: 200, `valores_ocultos=true`, kW `null`. Regla: RN-XVI-06.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

De punta a punta, con la app real y el almacén en memoria de los e2e
(`tests/e2e/test_data_sources_e2e.py`): onboarding real del hogar de referencia de cada
personalidad, un miembro activo y el permiso `ver_consumo_actual` del hogar en false. El miembro
pide `obtenerFuentesDatos`: no es un 403 (la guardia solo exige membresía, RN-XVII-01 no aplica a
esta operación); el servicio oculta TODOS los kW (fuente y sensores) y marca
`valores_ocultos=true`, y sigue mostrando nombres y estados. Control: con el permiso el mismo
miembro ve los kW, y el administrador los ve siempre (RN-XVII-05, P-06). El cuerpo se valida
contra el contrato.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.e2e.test_consumption_e2e import HOUR_AT_T, ConsumptionStore, query_at
from tests.e2e.test_data_sources_e2e import (  # noqa: F401 - fixtures `db` y `client`
    client,
    db,
    get_sources,
    new_household,
    ok,
    user_of,
)
from tests.e2e.test_hour_recovery_e2e import T
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.simulator.support import stable_id


@pytest.mark.parametrize("name", PERSONALITY_ORDER)
def test_member_without_view_consumption_gets_200_with_hidden_values(
    db: ConsumptionStore,  # noqa: F811
    client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    hogar_id = new_household(db, client, monkeypatch, name)
    member_id: UUID = stable_id("miembro", "p07", name)
    db.seed_member(hogar_id, member_id)
    db.set_household_permission(hogar_id, "permiso_ver_consumo_actual", False)
    query_at(monkeypatch, T)
    stored = db.zone_kwh(hogar_id, HOUR_AT_T)
    assert stored and all(kwh is not None for kwh in stored.values())  # sí hay valores

    response = get_sources(client, member_id, hogar_id)

    assert response.status_code == 200, response.text  # no 403
    body = response.json()
    assert body["valores_ocultos"] is True
    assert body["fuente_principal"]["potencia_kw"] is None
    assert len(body["sensores"]) == len(stored)
    assert [sensor["potencia_kw"] for sensor in body["sensores"]] == [None] * len(stored)
    assert {sensor["estado"] for sensor in body["sensores"]} == {"activo"}

    admin = ok(get_sources(client, user_of(name), hogar_id))
    assert admin["valores_ocultos"] is False
    assert admin["fuente_principal"]["potencia_kw"] == pytest.approx(sum(stored.values()))

    db.set_household_permission(hogar_id, "permiso_ver_consumo_actual", True)
    allowed = ok(get_sources(client, member_id, hogar_id))
    assert allowed["valores_ocultos"] is False
    assert None not in [sensor["potencia_kw"] for sensor in allowed["sensores"]]
