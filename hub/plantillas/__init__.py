"""Capa de idiomas de Tinimit.

`resolver(idioma, clave) -> (texto, nativo)`:
  - `nativo=True`  → el texto está en el idioma pedido (validado)
  - `nativo=False` → se devuelve el español de respaldo; el kiosko lo marca

Reglas duras:
- El contenido CLÍNICO en idioma maya SOLO sale de aquí si está declarado y validado.
- El modelo NUNCA genera texto en idioma maya (razona en español y elige qué responder).
- Si un archivo de idioma declara una clave clínica con valor que "parece español",
  `verificar_idioma()` lo rechaza (lo detectan los tests).
"""

from __future__ import annotations

from .base import CLAVES_CLINICAS, ES, TODAS
from . import cak as _cak
from . import quc as _quc

_TABLAS: dict[str, dict] = {
    "es": ES,
    "cak": getattr(_cak, "T", {}),
    "quc": getattr(_quc, "T", {}),
}

# metadatos para el kiosko / selector
IDIOMAS: dict[str, dict] = {
    "es": {"nombre": "Español", "saludo": ""},
    "cak": {"nombre": _cak.T.get("langName", "Kaqchikel"), "saludo": _cak.T.get("saludo", "")},
    "quc": {"nombre": _quc.T.get("langName", "K'iche'"), "saludo": _quc.T.get("saludo", "")},
}


def resolver(idioma: str, clave: str) -> tuple[str, bool]:
    """Texto de `clave` en `idioma`; cae a español si no hay traducción validada."""
    es = ES.get(clave, clave)
    if idioma == "es":
        return es, True
    tabla = _TABLAS.get(idioma)
    if not tabla:
        return es, False
    val = tabla.get(clave)
    if isinstance(val, str) and val.strip():
        return val, True
    return es, False


def hay(idioma: str, clave: str) -> bool:
    return resolver(idioma, clave)[1]


def cobertura(idioma: str) -> dict:
    """Cuántas claves tiene traducidas ese idioma (para el panel / doc)."""
    tabla = _TABLAS.get(idioma, {})
    tiene = {k for k in TODAS if isinstance(tabla.get(k), str) and tabla[k].strip()}
    clin_tiene = tiene & CLAVES_CLINICAS
    return {
        "idioma": idioma,
        "total": len(TODAS),
        "traducidas": len(tiene),
        "clinicas_total": len(CLAVES_CLINICAS),
        "clinicas_traducidas": len(clin_tiene),
        "faltan": sorted(TODAS - tiene),
    }
