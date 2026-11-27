"""Caso B-03 del registro de pruebas (09_pruebas/): 10 creaciones de hogar en el servidor publicado
con la base real. Meta: p95 <= 10 s (DC-33).

Se corre desde la carpeta api/ del repositorio, que es donde está el .env:
    uv run python <ruta-de-este-archivo>

En cada repetición:
  1. crea una cuenta de prueba temporal en Supabase Auth (confirmada, sin mandar correo),
  2. inicia sesión con ella, crea su ficha y mide POST /onboarding (casa con las 9 zonas, el peor caso),
  3. borra la cuenta con DELETE /usuarios/me (se lleva el hogar y sus lecturas) y, por si acaso,
     también la borra directo en Supabase Auth.

Nunca imprime las claves del .env, las contraseñas temporales ni los tokens.
Guarda el resultado en 09_pruebas/evidencias/B-03/<AAAA-MM-DD>_resultado.txt.
"""

import math
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

API = "https://zentheris-api.onrender.com/api/v1"
REPETICIONES = 10
LIMITE_S = 10.0
ZONAS = ["cocina", "sala", "dormitorio", "bano", "oficina", "lavanderia", "terraza", "garaje", "cuarto_servicio"]
EVIDENCIAS = Path(__file__).resolve().parent.parent / "evidencias" / "B-03"


def leer_env(ruta: Path) -> dict[str, str]:
    valores = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def falla(paso: str, r: httpx.Response | None = None, e: Exception | None = None) -> str:
    if r is not None:
        return f"{paso}: respondió {r.status_code}"
    return f"{paso}: {type(e).__name__}"


def main() -> int:
    ruta_env = Path.cwd() / ".env"
    if not ruta_env.exists():
        print("No encuentro api/.env. Corre el comando desde la carpeta api del clon.")
        return 2
    env = leer_env(ruta_env)
    url = env.get("SUPABASE_URL", "").rstrip("/")
    clave = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not clave:
        print("Al .env le falta SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY.")
        return 2
    admin = {"apikey": clave, "Authorization": f"Bearer {clave}"}

    with httpx.Client(timeout=90.0) as c:
        print("Despertando Render (puede tardar hasta un minuto)...")
        try:
            r = c.get(f"{API}/salud")
            if r.status_code != 200:
                print(falla("Salud de Render", r))
                return 1
        except Exception as e:  # noqa: BLE001
            print(falla("Salud de Render", e=e))
            return 1
        print("Render responde. Empiezo las 10 mediciones.\n")

        tiempos: list[float] = []
        errores: list[str] = []
        for n in range(1, REPETICIONES + 1):
            correo = f"b03-{secrets.token_hex(4)}@example.com"
            contrasena = "B03" + secrets.token_urlsafe(18) + "9a"
            usuario_id = None
            token = None
            try:
                r = c.post(f"{url}/auth/v1/admin/users", headers=admin,
                           json={"email": correo, "password": contrasena, "email_confirm": True})
                if r.status_code not in (200, 201):
                    errores.append(f"#{n} " + falla("Crear cuenta de prueba", r))
                    print(errores[-1])
                    continue
                usuario_id = r.json().get("id")

                r = c.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": clave},
                           json={"email": correo, "password": contrasena})
                if r.status_code != 200:
                    errores.append(f"#{n} " + falla("Iniciar sesión", r))
                    print(errores[-1])
                    continue
                token = r.json()["access_token"]
                yo = {"Authorization": f"Bearer {token}"}

                r = c.post(f"{API}/usuarios/me", headers=yo, json={"nombre_completo": "Prueba B03"})
                if r.status_code != 201:
                    errores.append(f"#{n} " + falla("Crear ficha", r))
                    print(errores[-1])
                    continue

                inicio = time.perf_counter()
                r = c.post(f"{API}/onboarding", headers=yo,
                           json={"nombre_hogar": f"Medición B03 {n}", "tipo_vivienda": "casa", "zonas": ZONAS})
                segundos = time.perf_counter() - inicio
                if r.status_code != 201:
                    errores.append(f"#{n} " + falla("Crear hogar", r))
                    print(errores[-1])
                    continue
                tiempos.append(segundos)
                print(f"#{n}: {segundos:.2f} s")
            except Exception as e:  # noqa: BLE001
                errores.append(f"#{n} " + falla("Conexión", e=e))
                print(errores[-1])
            finally:
                if token:
                    try:
                        c.delete(f"{API}/usuarios/me", headers={"Authorization": f"Bearer {token}"})
                    except Exception:  # noqa: BLE001, S110
                        pass  # el borrado directo de abajo lo cubre
                if usuario_id:
                    try:
                        c.delete(f"{url}/auth/v1/admin/users/{usuario_id}", headers=admin)
                    except Exception:  # noqa: BLE001
                        errores.append(f"#{n} no pude confirmar el borrado de la cuenta de prueba")

    ahora = datetime.now(ZoneInfo("America/Bogota"))
    lineas = [f"Medición B-03 · {ahora:%d/%m/%Y %H:%M} · casa con 9 zonas (6 480 lecturas)"]
    lineas += [f"#{i}: {t:.2f} s" for i, t in enumerate(tiempos, 1)]
    if tiempos:
        orden = sorted(tiempos)
        p95 = orden[math.ceil(0.95 * len(orden)) - 1]
        lineas.append(f"Mediciones válidas: {len(tiempos)} de {REPETICIONES}")
        lineas.append(f"Mínimo {orden[0]:.2f} s · mediana {orden[len(orden) // 2]:.2f} s · p95 {p95:.2f} s")
        pasa = p95 <= LIMITE_S and len(tiempos) == REPETICIONES
        lineas.append("RESULTADO: PASA (p95 <= 10 s)" if pasa else "RESULTADO: NO PASA o incompleto")
    else:
        lineas.append("RESULTADO: sin mediciones válidas")
    lineas += errores
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    resultado = EVIDENCIAS / f"{ahora:%Y-%m-%d}_resultado.txt"
    resultado.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lineas))
    print(f"\nGuardado en {resultado}")
    return 0 if tiempos and not errores else 1


if __name__ == "__main__":
    sys.exit(main())
