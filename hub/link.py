"""Simulador del enlace LoRa — fragmentación, airtime real y salto de repetidor.

Hoy el transporte real es HTTP local; este módulo impone y reporta las restricciones
que tendría el enlace LoRa (bytes por trama, airtime, límite de dwell, 2 saltos) para
que la demo muestre números verdaderos, no decorado.

Airtime con la ecuación de Semtech (SX1276 §4.1.1.7). Solo matemática de stdlib, sin red.

Conflicto de spec resuelto: a SF9/BW125, una trama de 200 B dura ~1005 ms y viola el
límite de dwell de 400 ms de US915. Por eso el **dwell manda el MTU**: la trama PHY
máxima es 66 B (~390 ms); menos 3 B de cabecera de trama => 63 B de payload por trama.
"""

from __future__ import annotations

import math

# --- parámetros de radio (LoRa US915, config conservadora de largo alcance) ----
SF = 9
BW = 125_000  # Hz
CR = 1  # coding rate 4/(4+CR) = 4/5
N_PREAMBLE = 8
CRC = 1  # CRC de payload activo
IH = 0  # cabecera explícita (implicit header = 0)
DE = 0  # low-data-rate optimize: solo SF11/12 @125k
REGION = "US915"
DWELL_MS = 400  # límite de permanencia por transmisión (FCC / LoRaWAN US915)

FRAME_HEADER = 3  # bytes: msg_id(1) · idx(1) · total(1)
REPETIDOR_PROC_MS = 50  # store-and-forward del repetidor
HOPS = ("Aldea", "Repetidor", "Hub")


def tiempo_simbolo() -> float:
    """Tsym en ms."""
    return (2**SF) / BW * 1000.0


def airtime_trama(pl_bytes: int) -> float:
    """Airtime en ms de una trama con `pl_bytes` de payload PHY (Semtech)."""
    tsym = tiempo_simbolo()
    t_preamble = (N_PREAMBLE + 4.25) * tsym
    num = 8 * pl_bytes - 4 * SF + 28 + 16 * CRC - 20 * IH
    den = 4 * (SF - 2 * DE)
    payload_symb = 8 + max(math.ceil(num / den) * (CR + 4), 0)
    return t_preamble + payload_symb * tsym


def _mtu_phy_por_dwell() -> int:
    """Mayor payload PHY cuyo airtime no pasa el límite de dwell."""
    pl = 1
    while airtime_trama(pl + 1) <= DWELL_MS:
        pl += 1
    return pl


MTU_PHY = _mtu_phy_por_dwell()  # == 66 a SF9/BW125/US915
PAYLOAD_MTU = MTU_PHY - FRAME_HEADER  # == 63


def fragmentar(data: bytes, *, msg_id: int = 0, mtu: int = PAYLOAD_MTU) -> list[bytes]:
    """Parte `data` (el envelope del códec) en tramas con cabecera de 3 B."""
    trozos = [data[i : i + mtu] for i in range(0, len(data), mtu)] or [b""]
    total = len(trozos)
    if total > 255:
        raise ValueError(f"mensaje de {len(data)} B necesita {total} tramas (>255)")
    return [
        bytes([msg_id & 0xFF, idx, total]) + trozo for idx, trozo in enumerate(trozos)
    ]


def reensamblar(frames: list[bytes]) -> bytes:
    """Inverso de `fragmentar`. Verifica índices contiguos y `total` consistente."""
    if not frames:
        raise ValueError("sin tramas")
    partes = sorted(frames, key=lambda f: f[1])
    total = partes[0][2]
    if len(partes) != total or [f[1] for f in partes] != list(range(total)):
        raise ValueError("tramas faltantes o duplicadas")
    return b"".join(f[FRAME_HEADER:] for f in partes)


def simular(data: bytes, *, hops: int = 2, msg_id: int = 0) -> dict:
    """Simula el envío de `data` por el enlace y devuelve las métricas reales."""
    frames = fragmentar(data, msg_id=msg_id)
    airtime_una_via = sum(airtime_trama(len(f)) for f in frames)
    bytes_aire = sum(len(f) for f in frames)
    total_ms = hops * airtime_una_via + (hops - 1) * REPETIDOR_PROC_MS

    detalle_hops = [
        {
            "i": i,
            "de": HOPS[i] if i < len(HOPS) else f"salto{i}",
            "a": HOPS[i + 1] if i + 1 < len(HOPS) else f"salto{i + 1}",
            "tramas": len(frames),
            "bytes": bytes_aire,
            "ms": round(airtime_una_via, 1),
        }
        for i in range(hops)
    ]
    dwell_ok = all(airtime_trama(len(f)) <= DWELL_MS for f in frames)
    return {
        "tramas": len(frames),
        "bytes": len(data),  # envelope del códec
        "bytes_en_aire": bytes_aire,  # incluye cabeceras de trama
        "airtime_ms": round(total_ms, 1),  # todos los saltos + repetidor
        "airtime_una_via_ms": round(airtime_una_via, 1),
        "saltos": hops,
        "hops": detalle_hops,
        "dwell_ok": dwell_ok,
        "duty_cycle": {
            "region": REGION,
            "limite": f"dwell {DWELL_MS} ms por trama",
            "ok": dwell_ok,
            "nota": (
                "EU868 no tiene límite de dwell pero sí 1% de ciclo de trabajo "
                "(~36 s de aire por hora); permitiría tramas de hasta 222 B."
            ),
        },
    }


if __name__ == "__main__":
    print(f"Tsym={tiempo_simbolo():.3f} ms  MTU_PHY={MTU_PHY} B  PAYLOAD_MTU={PAYLOAD_MTU} B")
    for pl in (50, 66, 67, 100, 200):
        print(f"  PL {pl:3} B -> {airtime_trama(pl):7.1f} ms  {'OK' if airtime_trama(pl) <= DWELL_MS else 'VIOLA DWELL'}")
    for n in (8, 50, 100, 200):
        s = simular(b"x" * n)
        print(f"  msg {n:3} B -> {s['tramas']} tramas, {s['airtime_ms']} ms (2 saltos)")
