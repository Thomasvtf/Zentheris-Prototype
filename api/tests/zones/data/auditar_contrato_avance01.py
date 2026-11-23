"""Implementación independiente del Avance 01 (K03). No es código de producción.

Copia literal de las constantes y de `asignar` de `insumos/auditar_contrato_avance01.py` del zip
de referencia (SHA-256 811f5201303343a0ff2c1ecd2f4a1e1882bfca44e6a80077a379536add9836c1). Se
conservan sus nombres en español para poder compararla con el original; no se corrige ni se
refactoriza, porque su valor es ser independiente de app/domain/zone_rules.py.
"""

BASICAS = frozenset(("cocina", "sala", "dormitorio", "bano"))
COMPLEMENTARIAS = frozenset(("oficina", "lavanderia"))
EXTRAS = frozenset(("terraza", "garaje", "cuarto_servicio"))
ZONAS = ("cocina", "sala", "dormitorio", "bano", "lavanderia",
         "oficina", "terraza", "garaje", "cuarto_servicio")
VIVIENDAS = ("apartaestudio", "apartamento", "casa", "duplex", "casa_campestre")
PERSONALIDADES = tuple("Consumo " + n for n in
                      ("compacto", "eficiente", "intermedio", "familiar", "amplio"))


def asignar(vivienda: str, zonas: list[str] | tuple[str, ...]) -> str:
    """Valida antes de clasificar; rechaza nombres desconocidos y duplicados."""
    if vivienda not in VIVIENDAS:
        raise ValueError("Vivienda desconocida")
    if not isinstance(zonas, (list, tuple)) or any(not isinstance(z, str) for z in zonas):
        raise ValueError("La selección debe ser una lista de nombres")
    conjunto = set(zonas)
    if len(conjunto) != len(zonas) or not conjunto <= set(ZONAS):
        raise ValueError("Zona duplicada o desconocida")
    if vivienda == "apartaestudio":
        if not (3 <= len(conjunto) <= 5 and len(conjunto & BASICAS) >= 3
                and not conjunto & EXTRAS):
            raise ValueError("Selección inválida para apartaestudio")
        return PERSONALIDADES[0 if len(conjunto) <= 4 else 1]
    if not BASICAS <= conjunto:
        raise ValueError("Faltan zonas básicas")
    c = len(conjunto & {"oficina", "lavanderia", "terraza", "garaje"})
    s = "cuarto_servicio" in conjunto
    e = len(conjunto & EXTRAS)
    ol = bool(conjunto & COMPLEMENTARIAS)
    nivel = 4 if e >= 2 and ol else 3 if c >= 2 or s else 2 if c == 1 else 1
    if vivienda == "casa_campestre":
        nivel = min(4, nivel + 1)
    return PERSONALIDADES[nivel]
