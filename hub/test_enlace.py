"""Pruebas del enlace (codec + link) — sin modelo, sin red.

    cd hub && python test_enlace.py
"""

from __future__ import annotations

import statistics

import codec
import link
from guias import FIRST_AID, GENERIC_ORIENTACION, GENERIC_PREGUNTA, GUIAS


def test_roundtrip_exacto() -> None:
    textos = (
        [g["orientacion"] for g in GUIAS.values()]
        + [q for g in GUIAS.values() for q in g["preguntas"]]
        + [s for pasos in FIRST_AID.values() for s in pasos]
        + [GENERIC_PREGUNTA, GENERIC_ORIENTACION, "", "á" * 300, "texto\ncon\nsaltos"]
    )
    malos = [t for t in textos if not codec.roundtrip_ok(t)]
    assert not malos, f"round-trip falló en {len(malos)} textos"


def test_envelope_sobrevive() -> None:
    blob = codec.encode("hola", tipo="emergencia", id=513, prioridad="emergencia", lang="cak")
    d = codec.decode(blob)
    assert (d["tipo"], d["id"], d["prioridad"], d["lang"]) == (
        "emergencia", 513, "emergencia", "cak",
    ), d
    assert d["texto"] == "hola"


def test_envelope_corrupto_lanza() -> None:
    for mal in (b"", b"\x00\x00\x00\x00\x00", b"\xff\xff\xff\xff\xff\x00"):
        try:
            codec.decode(mal)
        except ValueError:
            continue
        raise AssertionError(f"decode({mal!r}) no lanzó ValueError")


def test_airtime_semtech() -> None:
    # valores de referencia SF9/BW125/CR4-5, ecuación de Semtech
    assert abs(link.airtime_trama(50) - 328.7) < 0.5
    assert abs(link.airtime_trama(66) - 390.1) < 0.5
    assert link.MTU_PHY == 66 and link.PAYLOAD_MTU == 63
    assert link.airtime_trama(67) > link.DWELL_MS  # una trama más grande viola dwell


def test_fragmentacion_y_dwell() -> None:
    data = b"x" * 200
    frames = link.fragmentar(data, msg_id=7)
    assert link.reensamblar(frames) == data
    assert all(len(f) <= link.MTU_PHY for f in frames)
    sim = link.simular(data, hops=2)
    assert sim["dwell_ok"] is True
    assert sim["saltos"] == 2 and len(sim["hops"]) == 2
    assert sim["tramas"] == 4  # 200 / 63 -> 4


def test_ratios_reportados() -> None:
    curadas = [g["orientacion"] for g in GUIAS.values()]
    media = statistics.mean(codec.stats(t, tipo="orientacion")["ratio"] for t in curadas)
    assert media > 15, f"las orientaciones curadas deberían comprimir mucho (media {media:.1f}x)"
    corta = codec.stats("dos días", tipo="consulta")
    assert corta["ratio"] >= 0.8  # mensajes muy cortos: ~1x, no expanden de forma absurda


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
