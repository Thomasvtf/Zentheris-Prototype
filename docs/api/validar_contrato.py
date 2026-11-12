"""Validación estructural del contrato OpenAPI 3.1 (sustituto del lint oficial cuando no hay npm).
Uso: python -I validar_contrato.py <contrato.yaml> <mensaje_codigos.es-CO.json> <catalogo.es-CO.json>"""
import sys, json, re, yaml
from jsonschema import Draft202012Validator
ruta, rmc, rcat = sys.argv[1:4]
d = yaml.safe_load(open(ruta, encoding="utf-8"))
errores, avisos = [], []
def ok(c, m): (None if c else errores.append(m))
ok(d.get("openapi", "").startswith("3.1"), "openapi no es 3.1.x")
ok(d.get("info", {}).get("version"), "falta info.version")
# referencias
def refs(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "$ref": acc.append(v)
            else: refs(v, acc)
    elif isinstance(o, list):
        for v in o: refs(v, acc)
    return acc
def resolver(r):
    if not r.startswith("#/"): return False
    cur = d
    for p in r[2:].split("/"):
        if not isinstance(cur, dict) or p not in cur: return False
        cur = cur[p]
    return True
todas = refs(d, [])
for r in set(todas): ok(resolver(r), f"$ref no resuelve: {r}")
# operaciones
ops, opids = 0, []
metodos = {"get", "post", "put", "patch", "delete"}
tags_def = {t["name"] for t in d.get("tags", [])}
for ruta_p, item in d["paths"].items():
    pp = set(re.findall(r"{(\w+)}", ruta_p))
    params_item = item.get("parameters", [])
    for m, op in item.items():
        if m not in metodos: continue
        ops += 1; opids.append(op.get("operationId"))
        ok(op.get("operationId"), f"{m} {ruta_p} sin operationId")
        ok(op.get("summary"), f"{op.get('operationId')} sin summary")
        ok(op.get("responses"), f"{op.get('operationId')} sin responses")
        ok(any(str(c).startswith("2") for c in op.get("responses", {})), f"{op.get('operationId')} sin respuesta 2xx")
        for t in op.get("tags", []): ok(t in tags_def, f"tag no declarado {t}")
        declarados = set()
        for p in params_item + op.get("parameters", []):
            if "$ref" in p:
                cur = d
                for k in p["$ref"][2:].split("/"): cur = cur[k]
                p = cur
            if p.get("in") == "path": declarados.add(p["name"])
        ok(pp == declarados, f"{op.get('operationId')}: parámetros de ruta {pp} vs declarados {declarados}")
        if op.get("security", None) != [] :
            ok("401" in op["responses"], f"{op.get('operationId')} protegido sin 401")
ok(len(opids) == len(set(opids)), "operationId repetidos")
# esquemas JSON Schema 2020-12
for n, sch in d["components"]["schemas"].items():
    try: Draft202012Validator.check_schema(sch)
    except Exception as e: errores.append(f"esquema {n}: {str(e)[:120]}")
# cruces con el catálogo
mc = {c["mensaje_codigo"] for c in json.load(open(rmc, encoding="utf-8"))["codigos"]}
enum_mc = {v for v in d["components"]["schemas"]["MensajeCodigo"]["enum"] if v is not None}
ok(mc == enum_mc, f"MensajeCodigo difiere del catálogo: {mc ^ enum_mc}")
cat = json.load(open(rcat, encoding="utf-8"))
err_cat = set(k.upper() for k in cat["error"].keys() if k not in ("app", "campo"))
enum_err = set(d["components"]["schemas"]["CodigoError"]["enum"])
ok(enum_err <= err_cat, f"códigos sin texto en catálogo: {enum_err - err_cat}")
print(json.dumps({"archivo": ruta, "version": d["info"]["version"], "operaciones": ops, "refs": len(todas),
                  "esquemas": len(d["components"]["schemas"]), "mensaje_codigo": len(enum_mc), "codigos_error": len(enum_err),
                  "errores": errores, "avisos": avisos}, ensure_ascii=False, indent=1))
sys.exit(1 if errores else 0)
