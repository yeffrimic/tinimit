"""Pruebas de la capa de idiomas (plantillas) — sin modelo, sin red.

    cd hub && python test_plantillas.py
"""

from __future__ import annotations

import plantillas as P
from guias import EMERGENCIAS, FIRST_AID, GUIAS, MOTIVOS
from plantillas.base import CLAVES_CLINICAS, ES


def test_esquema_cubre_guias() -> None:
    """Cada trozo de contenido curado tiene su clave en el esquema."""
    faltan = []
    for mid, g in GUIAS.items():
        for i in range(len(g["preguntas"])):
            if f"guia.{mid}.pregunta.{i}" not in ES:
                faltan.append(f"guia.{mid}.pregunta.{i}")
        if f"guia.{mid}.orientacion" not in ES:
            faltan.append(f"guia.{mid}.orientacion")
    for eid, pasos in FIRST_AID.items():
        for i in range(len(pasos)):
            if f"primeros_auxilios.{eid}.{i}" not in ES:
                faltan.append(f"primeros_auxilios.{eid}.{i}")
    for mid in MOTIVOS:
        assert f"motivo.{mid}" in ES
    for eid in EMERGENCIAS:
        assert f"emergencia.{eid}" in ES
    assert not faltan, f"claves sin esquema: {faltan}"


def test_resolver_respaldo() -> None:
    # idioma desconocido → español + no nativo
    t, n = P.resolver("xx", "guia.fiebre.orientacion")
    assert t == GUIAS["fiebre"]["orientacion"] and n is False
    # clave inexistente → devuelve la clave + no nativo
    t, n = P.resolver("quc", "no.existe")
    assert t == "no.existe" and n is False
    # español siempre nativo
    t, n = P.resolver("es", "disclaimer")
    assert n is True and t == ES["disclaimer"]
    # clave presente en quc → nativo
    t, n = P.resolver("quc", "langName")
    assert n is True and t == "K'iche'"


def test_quc_sin_espanol_en_clinico() -> None:
    """Ningún hueco CLÍNICO de quc.py tiene texto español por accidente."""
    import plantillas.quc as Q
    filtrados = {k: v for k, v in Q.T.items() if k in CLAVES_CLINICAS}
    for k, v in filtrados.items():
        assert v != ES.get(k), f"quc.{k} es idéntico al español (¿copiaste sin traducir?)"
        # heurística: si contiene 3+ palabras funcionales españolas, sospechar
        esp = sum(v.lower().count(w) for w in (" el ", " la ", " los ", " que ", " para ",
                                               " con ", " puedes ", " acude "))
        assert esp < 3, f"quc.{k} parece español: {v!r}"


def test_cak_conserva_saludo() -> None:
    t, n = P.resolver("cak", "saludo")
    assert n is True and t == "La utz awäch?"


def test_cobertura() -> None:
    c = P.cobertura("quc")
    assert c["total"] == len(P.TODAS) if hasattr(P, "TODAS") else c["total"] > 80
    assert c["clinicas_traducidas"] <= c["clinicas_total"]
    # es está completo (salvo el saludo vacío intencional)
    ce = P.cobertura("es")
    assert ce["clinicas_traducidas"] == ce["clinicas_total"]


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if not nombre.startswith("test_"):
            continue
        try:
            fn()
            print(f"  ok  {nombre}")
        except Exception as e:  # noqa: BLE001
            fallos += 1
            print(f"FALLA {nombre}: {e}")
    if not fallos:
        for idi in ("quc", "cak"):
            c = P.cobertura(idi)
            print(f"  · {idi}: {c['clinicas_traducidas']}/{c['clinicas_total']} claves "
                  f"clínicas traducidas, {c['traducidas']}/{c['total']} en total")
    raise SystemExit(fallos)
