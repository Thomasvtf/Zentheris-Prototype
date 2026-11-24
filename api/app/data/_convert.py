"""Conversiones internas de valores de fila compartidas por los módulos de app.data."""

from uuid import UUID


def as_uuid(value: UUID | str) -> UUID:
    """Id de una fila como UUID: psycopg2 lo entrega como UUID o como texto según el tipo."""
    return value if isinstance(value, UUID) else UUID(str(value))
