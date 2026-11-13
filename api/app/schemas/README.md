# schemas/

Modelos Pydantic **iguales al contrato 0.2.5**: mismos nombres de clase y de campo (en español, como el YAML; DC-62), mismos tipos, nulos y límites. Un archivo por etiqueta del contrato.

- **Va:** solo modelos de entrada y salida de la API.
- **No va:** lógica, consultas ni modelos de tablas.
- **Ejemplo:** `class Hogar(BaseModel)` en `households.py`.

`tests/contract/test_skeleton_matches_contract.py` compara cada esquema con el contrato. Las respuestas que en el contrato son objetos en línea tienen un nombre aquí (`ZonasLista`, `AlertasLista`…).
