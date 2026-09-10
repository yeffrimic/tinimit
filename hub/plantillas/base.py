"""Esquema de claves traducibles — el español es la fuente de verdad.

`ES` se arma desde `guias.py` + las constantes de `medical.py`, así nunca se
desincroniza del contenido clínico curado. Cada archivo de idioma (`quc.py`,
`cak.py`) declara SOLO las claves que tiene traducidas y validadas; el resto cae
a `ES` (y el kiosko lo marca con subrayado punteado).

Convención de claves:
    guia.<motivo>.pregunta.<0..2>       repregunta guiada
    guia.<motivo>.orientacion            orientación final del motivo
    generico.pregunta / generico.orientacion
    primeros_auxilios.<tipo>.<0..3>
    motivo.<id> / emergencia.<id>        etiquetas de los botones
    aviso.emergencia / disclaimer
    social.<saludo|identidad|gracias|despedida|confirmar>
    ui.<pensando|respuesta_en_espanol|...>
    saludo / langName
"""

from __future__ import annotations

import sys
from pathlib import Path

_HUB = Path(__file__).resolve().parents[1]
if str(_HUB) not in sys.path:
    sys.path.insert(0, str(_HUB))

from guias import (  # noqa: E402
    EMERGENCIAS,
    FIRST_AID,
    GENERIC_ORIENTACION,
    GENERIC_PREGUNTA,
    GUIAS,
    MOTIVOS,
)

_DISCLAIMER = (
    "Esto es orientación general y no reemplaza la valoración de un profesional de salud."
)
_AVISO_EMERGENCIA = (
    "Esto puede ser grave y necesita atención inmediata. Usa el botón rojo de "
    "EMERGENCIA de arriba para enviar una alerta al puesto de salud ahora mismo."
)


def _construir_es() -> dict[str, str]:
    d: dict[str, str] = {}
    for mid, g in GUIAS.items():
        for i, q in enumerate(g["preguntas"]):
            d[f"guia.{mid}.pregunta.{i}"] = q
        d[f"guia.{mid}.orientacion"] = g["orientacion"]
    for mid, label in MOTIVOS.items():
        d[f"motivo.{mid}"] = label
    for eid, label in EMERGENCIAS.items():
        d[f"emergencia.{eid}"] = label
    for eid, pasos in FIRST_AID.items():
        for i, p in enumerate(pasos):
            d[f"primeros_auxilios.{eid}.{i}"] = p
    d["generico.pregunta"] = GENERIC_PREGUNTA
    d["generico.orientacion"] = GENERIC_ORIENTACION
    d["aviso.emergencia"] = _AVISO_EMERGENCIA
    d["disclaimer"] = _DISCLAIMER
    d["social.saludo"] = (
        "¡Hola! Soy el asistente de salud de la aldea. Estoy para ayudarte. "
        "Cuéntame qué te está molestando o toca uno de los botones de arriba."
    )
    d["social.identidad"] = (
        "Soy un asistente de salud de la comunidad; funciono en una computadora, no soy "
        "una persona. No soy doctor, pero te doy orientación y te digo cuándo ir al "
        "puesto de salud. Cuéntame, ¿qué te pasa?"
    )
    d["social.gracias"] = (
        "¡Con gusto! Cuídate mucho. Si algo empeora o tienes otra duda, escríbeme de "
        "nuevo. Si es una urgencia con peligro de vida, usa el botón rojo de EMERGENCIA."
    )
    d["social.despedida"] = "Que te mejores pronto. Aquí estaré si necesitas algo."
    d["social.fuera_de_tema"] = (
        "Soy el asistente de salud de la aldea y solo puedo ayudarte con temas de salud. "
        "Cuéntame qué te está molestando —fiebre, dolor, tos, una herida, un malestar— o "
        "toca uno de los botones de arriba. Si hay peligro de vida, usa el botón rojo de "
        "EMERGENCIA."
    )
    d["social.confirmar"] = (
        "Perfecto. ¿Hay algo más en lo que te pueda ayudar? Puedes contarme otra "
        "molestia o tocar un botón de arriba."
    )
    d["nota.prefijo_donde"] = "📍 Dónde conseguirlo:"
    d["ui.pensando"] = "El puesto de salud está pensando…"
    d["ui.respuesta_en_espanol"] = (
        "Esta respuesta está en español; la traducción a tu idioma está en validación."
    )
    d["saludo"] = ""  # saludo de bienvenida por idioma (vacío = sin prefijo)
    d["langName"] = "Español"
    return d


ES: dict[str, str] = _construir_es()
TODAS = frozenset(ES)

# Claves de contenido CLÍNICO: si un idioma las declara, deben ser texto real en ese
# idioma (validado), nunca español. Las de UI / etiquetas pueden ser de mejor esfuerzo.
CLAVES_CLINICAS = frozenset(
    k for k in ES
    if k.split(".", 1)[0] in {"guia", "generico", "primeros_auxilios", "aviso", "disclaimer"}
)
