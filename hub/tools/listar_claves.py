"""Imprime todas las cadenas que faltan traducir a un idioma, con el español de origen.

    cd hub && python tools/listar_claves.py quc          # todo lo que falta en K'iche'
    cd hub && python tools/listar_claves.py quc --solo-clinico
    cd hub && python tools/listar_claves.py quc --hechas   # lo que ya está traducido

Da la lista para llevar a la ALMG / un hablante. Al validar una traducción, ponla en
`hub/plantillas/<idioma>.py` (dict `T`) y corre `python test_plantillas.py`.
"""

from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

import plantillas as P  # noqa: E402
from plantillas.base import CLAVES_CLINICAS, ES  # noqa: E402

_TITULOS = {
    "guia": "Repreguntas y orientaciones guiadas 🩺",
    "primeros_auxilios": "Primeros auxilios de emergencia 🩺",
    "generico": "Texto libre genérico 🩺",
    "aviso": "Aviso de emergencia 🩺",
    "disclaimer": "Descargo permanente 🩺",
    "social": "Respuestas sociales (saludo, identidad, gracias)",
    "motivo": "Etiquetas de los botones de motivo",
    "emergencia": "Etiquetas de los tipos de emergencia",
    "nota": "Notas del sistema",
    "ui": "Textos de interfaz",
    "saludo": "Saludo de bienvenida",
    "langName": "Nombre del idioma",
}
_ORDEN = list(_TITULOS)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit("uso: python tools/listar_claves.py <idioma> [--solo-clinico] [--hechas]")
    idioma = args[0]
    solo_clinico = "--solo-clinico" in args
    hechas = "--hechas" in args

    cob = P.cobertura(idioma)
    print(f"# {idioma}  —  {cob['clinicas_traducidas']}/{cob['clinicas_total']} claves "
          f"clínicas · {cob['traducidas']}/{cob['total']} en total\n")

    for g in _ORDEN:
        claves = sorted(k for k in ES if k.split(".")[0] == g)
        if not claves:
            continue
        if solo_clinico:
            claves = [k for k in claves if k in CLAVES_CLINICAS]
        claves = [k for k in claves if P.hay(idioma, k) == hechas]
        if not claves:
            continue
        print(f"## {_TITULOS[g]}\n")
        for k in claves:
            print(f"- {k}")
            print(f"    ES: {ES[k].strip()}")
            if hechas:
                print(f"    {idioma}: {P.resolver(idioma, k)[0]}")
        print()


if __name__ == "__main__":
    main()
