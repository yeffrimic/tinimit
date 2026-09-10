"""Pruebas de store.py — SQLite en dos niveles, sin modelo ni red.

    cd hub && python test_store.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from store import Store

_LORA = {"bytes_in": 400, "bytes_comprimido": 120, "tramas": 2, "ratio": 3.33, "airtime_ms": 780.0}


def _store() -> Store:
    return Store(Path(tempfile.mkdtemp()))


def test_perfil_ida_vuelta() -> None:
    s = _store()
    s.put_perfil("m1", nombre="Ana", edad="34", sector="Centro", alergias="penicilina")
    p = s.get_perfil("m1")
    assert p["nombre"] == "Ana" and p["sector"] == "Centro" and p["alergias"] == "penicilina"
    s.put_perfil("m1", nombre="Ana María", edad="35", sector="Centro", alergias="")
    assert s.get_perfil("m1")["nombre"] == "Ana María"


def test_consulta_y_feed() -> None:
    s = _store()
    s.put_perfil("m1", nombre="Ana", sector="Xepiacul")
    cid = s.log_consulta(mac="m1", motivo="fiebre", texto="tengo fiebre",
                         respuesta="Da líquidos y paracetamol.", prioridad="rutina",
                         fuente="modelo", lora=_LORA)
    assert cid == 1
    feed = s.feed()
    assert feed[0]["nombre"] == "Ana" and feed[0]["sector"] == "Xepiacul"
    assert feed[0]["motivo"] == "fiebre" and feed[0]["bytes_aire"] == 120


def test_emergencia_crea_alerta() -> None:
    s = _store()
    s.put_perfil("m2", nombre="Diego", sector="Panimaché I")
    s.log_consulta(mac="m2", motivo="mordedura", texto="serpiente",
                   respuesta="No cortes, no succiones.", prioridad="emergencia",
                   fuente="curado", lora=_LORA, es_emergencia=True, tipo_emergencia="mordedura")
    abiertas = s.alertas_abiertas()
    assert len(abiertas) == 1 and abiertas[0]["tipo"] == "mordedura"
    s.atender_alerta(abiertas[0]["id"])
    assert s.alertas_abiertas() == []


def test_resumen_por_sector() -> None:
    s = _store()
    s.put_perfil("a", nombre="A", sector="Centro")
    s.put_perfil("b", nombre="B", sector="Centro")
    s.put_perfil("c", nombre="C", sector="Xepiacul")
    for mac in ("a", "a", "b"):
        s.log_consulta(mac=mac, motivo="tos", texto="x", respuesta="y",
                       prioridad="rutina", fuente="modelo", lora=_LORA)
    s.log_consulta(mac="c", motivo="parto", texto="x", respuesta="y", prioridad="emergencia",
                   fuente="curado", lora=_LORA, es_emergencia=True, tipo_emergencia="parto")
    r = s.resumen()
    secs = {x["sector"]: x for x in r["sectores"]}
    assert secs["Centro"]["consultas"] == 3
    assert secs["Xepiacul"]["alertas_abiertas"] == 1
    assert secs["Xepiacul"]["prioridad_max"] == "emergencia"
    assert r["consultas_total"] == 4 and r["emergencias_abiertas"] == 1


def test_historial_para_modelo() -> None:
    s = _store()
    s.put_perfil("m", nombre="M", sector="Centro")
    assert s.contexto_historial("m") == ""
    s.registrar_conversacion(conv_id="c1", mac="m",
                             mensajes=[{"rol": "user", "texto": "tengo fiebre"},
                                       {"rol": "bot", "texto": "toma agua"}],
                             motivo="fiebre", titulo="Fiebre", prioridad="rutina")
    ctx = s.contexto_historial("m")
    assert "Fiebre" in ctx and "hoy" in ctx
    # la conversación en curso se excluye del contexto que se le pasa al modelo
    assert s.contexto_historial("m", excluir_conv="c1") == ""


def test_conversaciones_agrupan_turnos() -> None:
    s = _store()
    s.put_perfil("m", nombre="Ana", sector="Xepiacul")
    # turno 1: repregunta
    s.registrar_conversacion(conv_id="A", mac="m",
        mensajes=[{"rol": "user", "texto": "me duele la cabeza"},
                  {"rol": "bot", "texto": "¿desde cuándo?"}],
        titulo="Dolor de cabeza", prioridad="rutina")
    # turno 2: mismo id -> misma conversación, transcripción actualizada
    s.registrar_conversacion(conv_id="A", mac="m",
        mensajes=[{"rol": "user", "texto": "me duele la cabeza"},
                  {"rol": "bot", "texto": "¿desde cuándo?"},
                  {"rol": "user", "texto": "desde ayer"},
                  {"rol": "bot", "texto": "descansa y toma agua"}],
        titulo="Dolor de cabeza", prioridad="urgente")
    # otra conversación, dos horas después
    s.registrar_conversacion(conv_id="B", mac="m",
        mensajes=[{"rol": "user", "texto": "ahora tengo tos"},
                  {"rol": "bot", "texto": "cuídate del frío"}],
        titulo="Tos", prioridad="rutina")

    cs = s.conversaciones(mac="m")
    assert len(cs) == 2                       # dos conversaciones, no cuatro turnos
    assert cs[0]["titulo"] == "Tos"           # la más reciente primero
    a = next(c for c in cs if c["id"] == "A")
    assert a["titulo"] == "Dolor de cabeza"   # el título no cambia
    assert a["prioridad"] == "urgente"        # sube al máximo
    assert a["n_turnos"] == 4

    full = s.conversacion("A")
    assert len(full["transcripcion"]) == 4
    assert full["transcripcion"][-1]["texto"] == "descansa y toma agua"


def test_titulo_desde_primer_mensaje() -> None:
    s = _store()
    s.put_perfil("m", nombre="M")
    s.registrar_conversacion(conv_id="X", mac="m",
        mensajes=[{"rol": "user", "texto": "no puedo dormir y me sudan las manos."}],
        titulo="")   # sin pista -> se saca del primer mensaje
    assert s.conversaciones(mac="m")[0]["titulo"] == "no puedo dormir y me sudan las manos"


def test_sync_dos_niveles() -> None:
    s = _store()
    s.enlace_hub = False  # sin enlace al hub central
    s.put_perfil("m", nombre="M", sector="Centro")
    s.log_consulta(mac="m", motivo="tos", texto="x", respuesta="y",
                   prioridad="rutina", fuente="modelo", lora=_LORA)
    assert s.pendientes_de_sync() == 1
    assert s.feed() == []  # el panel lee de hub.db y aún no llegó
    s.enlace_hub = True
    movidas = s.sync_device_to_hub()
    assert movidas["consultas"] == 1
    assert s.pendientes_de_sync() == 0
    assert len(s.feed()) == 1


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
    raise SystemExit(fallos)
