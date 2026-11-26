"""Formatos del backend: nombres, números es-CO, horas, claves de evento y textos resueltos.

Nombres de zona, de sensor y de la fuente principal (RN-XII-03, RN-X-03, RN-XVI-06), mes y
año «YYYY-MM» de la tarifa (RN-XVI-05), meses (`formato.mes` del
catálogo), números es-CO (RN-XII-08: coma decimal y punto de miles; kW con 2 decimales y kWh con
1), horas «HH:00» en America/Bogota, clave de evento (DC-25) y textos de
`config_files/textos-backend.es-CO.json` (RN-XI-09). El dominio no lee el archivo: `services/`
lo lee y lo pasa a `parse_backend_texts`; las plantillas se rellenan con `render_backend_text`.
También arma el correo de invitación (`correos.invitacion`; RN-IX-03, DC-04): texto plano y HTML
con todos los valores escapados.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime
from string import Formatter
from types import MappingProxyType
from typing import Any

from app.domain.simulator import TIMEZONE
from app.domain.zone_rules import ZONE_TYPES

# RN-XII-03. Una prueba compara estos nombres con `zona.*` del catálogo es-CO.
ZONE_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "cocina": "Cocina",
        "sala": "Sala",
        "dormitorio": "Dormitorio",
        "bano": "Baño",
        "oficina": "Oficina",
        "lavanderia": "Lavandería",
        "terraza": "Terraza",
        "garaje": "Garaje",
        "cuarto_servicio": "Cuarto de servicio",
    }
)

# Una prueba compara estos nombres con `formato.mes` del catálogo es-CO.
MONTH_NAMES: Mapping[int, str] = MappingProxyType(
    {
        1: "enero",
        2: "febrero",
        3: "marzo",
        4: "abril",
        5: "mayo",
        6: "junio",
        7: "julio",
        8: "agosto",
        9: "septiembre",
        10: "octubre",
        11: "noviembre",
        12: "diciembre",
    }
)

EVENT_KEY_SEPARATOR = ":"
_YEAR_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")  # se usa con fullmatch

# Valores que admite el esquema de `alertas` y `consejos` (RN-XIV-01, RN-XIV-02, RN-XV-04).
ALERT_CATEGORIES: tuple[str, ...] = ("consumo", "consejo", "informacion")
ALERT_SEVERITIES: tuple[str, ...] = ("informativa", "advertencia", "critica")
TIP_PRIORITIES: tuple[str, ...] = ("alta", "media", "baja")
# `regla_origen` de alertas (DC-25) que el backend necesita encontrar en el archivo.
REQUIRED_ALERT_RULES: tuple[str, ...] = (
    "consumo_elevado",
    "consumo_critico",
    "cierre_mes_dentro",
    "cierre_mes_encima",
    "nuevo_miembro",
    "nuevo_consejo_zona",
    "nuevo_consejo_general",
)
# `regla_origen` de consejos (DC-24): reglas por zona y regla general (sin zona).
ZONE_TIP_RULES: tuple[str, ...] = ("zona_elevada", "zona_critica")
GENERAL_TIP_RULES: tuple[str, ...] = ("cierre_mes_encima",)
TIP_VARIANTS: tuple[int, ...] = (1, 2)


def zone_name(tipo: str) -> str:
    """Nombre visible de una zona, tomado de su tipo (RN-XII-03).

    Raises:
        KeyError: el tipo no está en el catálogo de 9 zonas.
    """
    return ZONE_NAMES[tipo]


def main_source_name(nombre_hogar: str) -> str:
    """Nombre de la fuente principal del hogar (RN-X-03; `fuentes.principal_nombre`)."""
    return f"Fuente principal {nombre_hogar}"


def sensor_name(tipo: str) -> str:
    """Nombre del sensor de una zona: «Sensor [zona]» (RN-XVI-06; `fuentes.sensor_nombre`).

    Raises:
        KeyError: el tipo no está en el catálogo de 9 zonas.
    """
    return f"Sensor {zone_name(tipo)}"


# ------------------------------------------------------------------ mes y año
def first_day_of_month(year_month: str) -> date:
    """«YYYY-MM» -> día 1 de ese mes (RN-XVI-05: `vigente_desde` se guarda el día 1).

    Mismo patrón que `TarifaCrear.vigente_desde` del contrato (`^[0-9]{4}-(0[1-9]|1[0-2])$`),
    solo dígitos ASCII y sin espacios ni salto de línea final.

    Raises:
        ValueError: no es texto, no cumple el patrón o el año no es válido (0000).
    """
    if not isinstance(year_month, str) or not _YEAR_MONTH.fullmatch(year_month):
        raise ValueError("se espera mes y año con el formato YYYY-MM")
    year, month = year_month.split("-")
    return date(int(year), int(month), 1)


# ------------------------------------------------------------------ números y horas
def _es_co(value: float, decimals: int) -> str:
    text = f"{value:,.{decimals}f}"
    if text.startswith("-") and not text.strip("-0.,"):
        text = text[1:]  # -0,00 -> 0,00
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def format_kw(value: float) -> str:
    """kW con 2 decimales en es-CO: 1234.5 -> «1.234,50» (RN-XII-08)."""
    return _es_co(value, 2)


def format_kwh(value: float) -> str:
    """kWh con 1 decimal en es-CO: 1234.5 -> «1.234,5» (RN-XII-08)."""
    return _es_co(value, 1)


def format_hour(moment: datetime) -> str:
    """«HH:00» de la hora de `moment` en America/Bogota (la hora 23 termina en «00:00»).

    Raises:
        ValueError: `moment` no tiene zona horaria.
    """
    if moment.utcoffset() is None:
        raise ValueError("se exige una fecha con zona horaria")
    return moment.astimezone(TIMEZONE).strftime("%H:00")


# ------------------------------------------------------------------ clave de evento
def build_event_key(regla: str, *partes: str) -> str:
    """Arma `clave_evento` según DC-25 (por ejemplo, `<regla>:<zona_id>:<AAAA-MM-DD>`).

    Raises:
        ValueError: sin partes, o la regla o alguna parte está vacía o contiene «:».
    """
    pieces = (regla, *partes)
    if len(pieces) < 2:
        raise ValueError("la clave de evento necesita al menos una parte además de la regla")
    for piece in pieces:
        if not isinstance(piece, str) or not piece or EVENT_KEY_SEPARATOR in piece:
            raise ValueError("cada parte de la clave de evento debe ser texto no vacío sin «:»")
    return EVENT_KEY_SEPARATOR.join(pieces)


# ------------------------------------------------------------------ textos del backend
@dataclass(frozen=True)
class AlertTemplate:
    regla_origen: str
    categoria: str
    severidad: str
    titulo: str
    mensaje: str


@dataclass(frozen=True)
class TipTemplate:
    regla_origen: str
    zona: str | None
    prioridad: str
    variante: int
    titulo: str
    descripcion: str


@dataclass(frozen=True)
class EmailTemplate:
    """`correos.invitacion` de textos-backend: 10 claves, todas texto no vacío."""

    asunto: str
    preheader: str
    saludo: str
    cuerpo: str
    boton: str
    vigencia: str
    sin_cuenta: str
    enlace_alterno: str
    seguridad: str
    pie: str


@dataclass(frozen=True)
class BackendTexts:
    alerts: Mapping[str, AlertTemplate]
    tips: Sequence[TipTemplate]
    invitation_email: EmailTemplate


def _text(item: Mapping[str, Any], key: str, where: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where}.{key} debe ser texto no vacío")
    return value


def _choice(item: Mapping[str, Any], key: str, allowed: tuple[str, ...], where: str) -> str:
    value = _text(item, key, where)
    if value not in allowed:
        raise ValueError(f"{where}.{key} no es un valor válido")
    return value


def _alerts(raw: Mapping[str, Any]) -> dict[str, AlertTemplate]:
    section = raw.get("alertas")
    if not isinstance(section, Mapping) or not section:
        raise ValueError("falta la sección alertas en los textos del backend")
    alerts: dict[str, AlertTemplate] = {}
    for key, item in section.items():
        where = f"alertas.{key}"
        if not isinstance(item, Mapping) or not item:
            raise ValueError(f"{where} debe ser un objeto")
        regla = _text(item, "regla_origen", where)
        if regla != key:
            raise ValueError(f"{where}.regla_origen debe coincidir con la clave")
        alerts[key] = AlertTemplate(
            regla_origen=regla,
            categoria=_choice(item, "categoria", ALERT_CATEGORIES, where),
            severidad=_choice(item, "severidad", ALERT_SEVERITIES, where),
            titulo=_text(item, "titulo", where),
            mensaje=_text(item, "mensaje", where),
        )
    missing = [rule for rule in REQUIRED_ALERT_RULES if rule not in alerts]
    if missing:
        raise ValueError(f"faltan plantillas de alerta: {', '.join(missing)}")
    return alerts


def _tip(item: Any, position: int) -> TipTemplate:
    where = f"consejos[{position}]"
    if not isinstance(item, Mapping) or not item:
        raise ValueError(f"{where} debe ser un objeto")
    regla = _choice(item, "regla_origen", ZONE_TIP_RULES + GENERAL_TIP_RULES, where)
    zona = item.get("zona")
    if regla in ZONE_TIP_RULES and zona not in ZONE_TYPES:
        raise ValueError(f"{where}.zona debe ser un tipo de zona del catálogo")
    if regla in GENERAL_TIP_RULES and zona is not None:
        raise ValueError(f"{where}.zona debe ser null en un consejo general")
    variante = item.get("variante")
    if isinstance(variante, bool) or variante not in TIP_VARIANTS:
        raise ValueError(f"{where}.variante debe ser 1 o 2")
    return TipTemplate(
        regla_origen=regla,
        zona=zona,
        prioridad=_choice(item, "prioridad", TIP_PRIORITIES, where),
        variante=variante,
        titulo=_text(item, "titulo", where),
        descripcion=_text(item, "descripcion", where),
    )


def _tips(raw: Mapping[str, Any]) -> tuple[TipTemplate, ...]:
    section = raw.get("consejos")
    if not isinstance(section, list) or not section:
        raise ValueError("falta la lista consejos en los textos del backend")
    tips = tuple(_tip(item, position) for position, item in enumerate(section))
    groups: dict[tuple[str, str | None], dict[int, str]] = {}
    for tip in tips:
        group = groups.setdefault((tip.regla_origen, tip.zona), {})
        if tip.variante in group:
            raise ValueError(f"variante repetida en {tip.regla_origen}/{tip.zona}")
        if tip.titulo in group.values():
            # DC-24: la variante del consejo anterior se reconoce por su título.
            raise ValueError(f"título repetido en {tip.regla_origen}/{tip.zona}")
        group[tip.variante] = tip.titulo
    expected = [(rule, zone) for rule in ZONE_TIP_RULES for zone in ZONE_TYPES]
    expected += [(rule, None) for rule in GENERAL_TIP_RULES]
    for key in expected:
        if set(groups.get(key, {})) != set(TIP_VARIANTS):
            raise ValueError(f"faltan variantes de consejo en {key[0]}/{key[1]}")
    return tips


def _invitation_email(raw: Mapping[str, Any]) -> EmailTemplate:
    section = raw.get("correos")
    if not isinstance(section, Mapping) or not section:
        raise ValueError("falta la sección correos en los textos del backend")
    item = section.get("invitacion")
    if not isinstance(item, Mapping) or not item:
        raise ValueError("falta correos.invitacion en los textos del backend")
    where = "correos.invitacion"
    return EmailTemplate(**{field.name: _text(item, field.name, where)
                            for field in fields(EmailTemplate)})


def parse_backend_texts(raw: Mapping[str, Any]) -> BackendTexts:
    """Plantillas de alertas, consejos y correo de invitación del JSON ya leído.

    RN-XI-09, DC-24, DC-25, RN-IX-03. Exige las 7 reglas de alerta de DC-25, las variantes 1 y 2
    de cada regla de consejo por tipo de zona (y de la general), con títulos distintos por grupo,
    y las 10 claves de `correos.invitacion`.

    Raises:
        ValueError: falta una sección, una plantilla o un campo, o un valor no es válido.
    """
    return BackendTexts(
        alerts=MappingProxyType(_alerts(raw)),
        tips=_tips(raw),
        invitation_email=_invitation_email(raw),
    )


def render_backend_text(template: str, variables: Mapping[str, object]) -> str:
    """Rellena `{variable}` en el texto de la plantilla; el resultado se guarda resuelto.

    Los valores se insertan tal cual (ya formateados por quien llama); las llaves que traiga un
    valor no se vuelven a interpretar. Las variables de más se ignoran.

    Raises:
        KeyError: el texto usa una variable que no viene en `variables`.
        ValueError: el texto usa algo distinto de `{nombre}` (índices, atributos, formato).
    """
    parts: list[str] = []
    for literal, field, spec, conversion in Formatter().parse(template):
        parts.append(literal)
        if field is None:
            continue
        if not field.isidentifier() or spec or conversion:
            raise ValueError(f"variable no admitida en la plantilla: {{{field}}}")
        parts.append(str(variables[field]))
    return "".join(parts)


# ------------------------------------------------------------------ correo de invitación
@dataclass(frozen=True)
class RenderedEmail:
    asunto: str
    texto: str  # texto plano
    html: str  # HTML mínimo; todos los valores variables escapados


def format_long_date(day: date) -> str:
    """Fecha larga en es-CO: «2 de diciembre de 2026» (mes de `MONTH_NAMES`, día sin cero)."""
    return f"{day.day} de {MONTH_NAMES[day.month]} de {day.year}"


def _one_line(text: str) -> str:
    """El asunto va en una cabecera: sin saltos de línea aunque el nombre los traiga."""
    return " ".join(text.splitlines())


def render_invitation_email(
    texts: BackendTexts, *, invitador: str, hogar: str, correo: str, expira_en: datetime, enlace: str
) -> RenderedEmail:
    """Correo de invitación (RN-IX-03, DC-04) desde `correos.invitacion`.

    `{fecha_vencimiento}` es la fecha de `expira_en` en America/Bogota. Texto plano: párrafos
    separados por una línea en blanco (saludo, cuerpo, «botón: enlace», vigencia, sin_cuenta,
    enlace_alterno, seguridad, pie). HTML: preheader oculto, los mismos párrafos y el botón como
    enlace. El nombre de quien invita y el del hogar los escribe el usuario: en el HTML cada
    párrafo ya rellenado (valores incluidos) pasa por `html.escape`. El asunto se deja en una
    sola línea.

    Raises:
        ValueError: `expira_en` no tiene zona horaria.
        KeyError: una plantilla usa una variable fuera de las cinco del correo.
    """
    if expira_en.utcoffset() is None:
        raise ValueError("se exige una fecha con zona horaria")
    template = texts.invitation_email
    variables = {
        "invitador": invitador,
        "hogar": hogar,
        "correo": correo,
        "fecha_vencimiento": format_long_date(expira_en.astimezone(TIMEZONE).date()),
        "enlace": enlace,
    }

    def fill(text: str) -> str:
        return render_backend_text(text, variables)

    asunto = _one_line(fill(template.asunto))
    boton = fill(template.boton)
    before = [fill(template.saludo), fill(template.cuerpo)]
    after = [fill(text) for text in (template.vigencia, template.sin_cuenta,
                                     template.enlace_alterno, template.seguridad, template.pie)]
    texto = "\n\n".join([*before, f"{boton}: {enlace}", *after])

    def paragraph(text: str) -> str:
        return f"<p>{html.escape(text, quote=True)}</p>"

    button = (f'<p><a href="{html.escape(enlace, quote=True)}">'
              f"{html.escape(boton, quote=True)}</a></p>")
    preheader = (
        '<div style="display:none;max-height:0;overflow:hidden;opacity:0">'
        f"{html.escape(fill(template.preheader), quote=True)}</div>"
    )
    body = "\n".join([preheader, *map(paragraph, before), button, *map(paragraph, after)])
    page = (
        '<!DOCTYPE html>\n<html lang="es-CO">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{html.escape(asunto, quote=True)}</title>\n</head>\n<body>\n{body}\n"
        "</body>\n</html>\n"
    )
    return RenderedEmail(asunto=asunto, texto=texto, html=page)
