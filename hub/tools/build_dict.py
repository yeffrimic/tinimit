"""Genera `hub/dictionary.txt` — el diccionario preestablecido del códec DEFLATE.

Se ejecuta UNA VEZ (o cada vez que cambie `guias.py`) y su salida se commitea.
El server nunca lo importa: solo hace `DICC = dictionary.txt.read_bytes()`.

    cd hub && python tools/build_dict.py

Todo el contenido sale de `guias.py` / `medical.py` (curado por humanos) más una
lista corta de stems frecuentes en el fraseo del modelo. Nada clínico inventado aquí.

Orden: de menos a más valioso. `zlib` solo mira los últimos 32 KB del zdict y las
back-references al FINAL del diccionario se codifican con menos bits (menor distancia),
así que las cadenas más rentables (las orientaciones completas) van al final.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUB))

import medical  # noqa: E402  (solo para leer sus constantes de texto)
from guias import (  # noqa: E402
    EMERGENCIAS,
    FIRST_AID,
    GENERIC_ORIENTACION,
    GENERIC_PREGUNTA,
    GUIAS,
    MOTIVOS,
)

# Tope del diccionario (y de la constante que irá al firmware como zdict).
# zlib solo consulta los últimos 32 KB del zdict, así que el límite es de huella en
# flash, no de correctitud. 8 KB entra todo el corpus curado y no pesa nada en PROGMEM.
CAP_BYTES = 8192


# Stems frecuentes en las respuestas del modelo (observados en las pruebas con
# MedGemma). Curados a mano, en español llano, sin contenido clínico nuevo.
STEMS = [
    "acude al puesto de salud",
    "acude hoy al puesto de salud",
    "acude de inmediato al puesto de salud",
    "busca atención",
    "de inmediato",
    "lo antes posible",
    "si empeora",
    "si no mejora en 2 o 3 días",
    "consulta con el personal de salud",
    "mantén a la persona",
    "mantén la zona limpia",
    "lava la zona con agua y jabón",
    "toma líquidos en poca cantidad y seguido",
    "ofrece líquidos",
    "suero oral",
    "reposo e hidratación",
    "paracetamol según el peso, cada 6 a 8 horas, sin pasar la dosis",
    "no des medicamentos sin indicación",
    "señales de alarma",
    "dificultad para respirar",
    "fiebre alta que no baja",
    "dolor fuerte que no cede",
    "vómito que no para",
    "sangre en el excremento",
    "manchas en la piel",
    "no despierta bien",
    "respira rápido o con dificultad",
    "¿Hace cuántos días",
    "¿Desde cuándo",
    "¿Tiene además",
    "¿Qué edad tiene",
    "hinchazón",
    "sangrado",
    "vómitos",
]


def _norm(s: str) -> str:
    """Colapsa espacios en runs y recorta; conserva los \\n como separadores."""
    s = s.replace("\r\n", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return s.strip()


def _tokens_medical() -> list[str]:
    return [
        medical._DISCLAIMER,
        medical._AVISO_EMERGENCIA,
        "PRIORIDAD: ",
        "ORIENTACION: ",
        "rutina",
        "urgente",
        "emergencia",
        "Datos de la persona: ",
        "edad ",
        "sector ",
        "alergias/condiciones: ",
        "Persona: ",
        "Asistente: ",
        "Motivo de consulta: ",
    ]


def build() -> bytes:
    # Bloques en orden peor -> mejor (la cola del zdict codifica más barato).
    bloques: list[list[str]] = [
        # 1. palabras raras / etiquetas
        list(MOTIVOS.values()) + list(EMERGENCIAS.values()) + _tokens_medical(),
        # 2. repreguntas guiadas + genérica
        [q for g in GUIAS.values() for q in g["preguntas"]] + [GENERIC_PREGUNTA],
        # 3. stems frecuentes del modelo
        STEMS,
        # 4. primeros auxilios: se envían verbatim en CADA emergencia -> muy valioso
        [paso for pasos in FIRST_AID.values() for paso in pasos],
        # 5. lo más valioso: orientaciones completas (respuesta curada verbatim)
        [g["orientacion"] for g in GUIAS.values()] + [GENERIC_ORIENTACION],
    ]

    buf = ""
    for bloque in bloques:
        for cand in bloque:
            cand = _norm(cand)
            if not cand or cand in buf:  # dedup por substring
                continue
            buf += ("\n" if buf else "") + cand

    data = buf.encode("utf-8")
    if len(data) > CAP_BYTES:
        data = data[-CAP_BYTES:]  # los últimos bytes son los más rentables
        nl = data.find(b"\n")  # recorta el primer trozo parcial -> UTF-8 válido
        if 0 <= nl < 200:
            data = data[nl + 1 :]
    return data


def main() -> None:
    # El archivo es zdict puro (sin cabecera): cada byte cuenta como diccionario.
    # La nota "no editar / regenerar tras cambios" vive en el docstring de este script
    # y en la cabecera de guias.py.
    data = build()
    out = HUB / "dictionary.txt"
    out.write_bytes(data)
    print(f"escrito {out}  ({len(data)} bytes, {data.count(chr(10).encode()) + 1} lineas)")
    print("--- primeras 200 B ---")
    print(data[:200].decode("utf-8", "replace"))
    print("--- ultimas 200 B ---")
    print(data[-200:].decode("utf-8", "replace"))


if __name__ == "__main__":
    main()
