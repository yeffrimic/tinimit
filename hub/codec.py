"""Códec del enlace — DEFLATE crudo + diccionario preestablecido + envelope compacto.

Es el mismo esquema que correría en el firmware del ESP32 (miniz/heatshrink con el
mismo `zdict`), por eso: DEFLATE crudo (`wbits=-15`, sin cabecera zlib/gzip), envelope
binario de cabecera fija, y el diccionario en un archivo aparte byte-idéntico.

Solo `zlib` + `struct` de la stdlib. Sin red.

Envelope (5 bytes de cabecera, big-endian, `>B H B B`):

    offset  size  campo       valores
      0      1    tipo        TIPOS
      1      2    id          uint16 BE, secuencia del hub, wrap mod 65536.
                              El downlink repite el id del uplink (correlación).
      3      1    prioridad   PRIORIDADES
      4      1    lang        LANGS
      5      …    payload     DEFLATE crudo (zdict=DICC) del texto UTF-8
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

DICC: bytes = (Path(__file__).with_name("dictionary.txt")).read_bytes()

TIPOS: dict[str, int] = {
    "consulta": 1,
    "repregunta": 2,
    "orientacion": 3,
    "emergencia": 4,
    "emergencia_ack": 5,
    "perfil": 6,
}
PRIORIDADES: dict[str, int] = {"rutina": 0, "urgente": 1, "emergencia": 2}
LANGS: dict[str, int] = {"es": 0, "cak": 1, "quc": 2, "kek": 3, "mam": 4}  # ISO 639-3

_R_TIPOS = {v: k for k, v in TIPOS.items()}
_R_PRIORIDADES = {v: k for k, v in PRIORIDADES.items()}
_R_LANGS = {v: k for k, v in LANGS.items()}

_HEADER = struct.Struct(">BHBB")


def _deflate(texto: str) -> bytes:
    co = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY, DICC)
    return co.compress(texto.encode("utf-8")) + co.flush()


def _inflate(payload: bytes) -> str:
    do = zlib.decompressobj(-15, DICC)
    return (do.decompress(payload) + do.flush()).decode("utf-8")


def encode(
    texto: str,
    *,
    tipo: str = "orientacion",
    id: int = 0,
    prioridad: str = "rutina",
    lang: str = "es",
) -> bytes:
    """Serializa `texto` a un envelope binario listo para el enlace."""
    try:
        cab = _HEADER.pack(TIPOS[tipo], id & 0xFFFF, PRIORIDADES[prioridad], LANGS[lang])
    except KeyError as e:
        raise ValueError(f"valor de envelope inválido: {e}") from None
    return cab + _deflate(texto)


def decode(blob: bytes) -> dict:
    """Inverso de `encode`. Lanza `ValueError` si la cabecera está corrupta."""
    if len(blob) < _HEADER.size:
        raise ValueError("envelope demasiado corto")
    t, mid, p, lg = _HEADER.unpack(blob[: _HEADER.size])
    if t not in _R_TIPOS or p not in _R_PRIORIDADES or lg not in _R_LANGS:
        raise ValueError(f"enum de envelope desconocido: tipo={t} prioridad={p} lang={lg}")
    return {
        "tipo": _R_TIPOS[t],
        "id": mid,
        "prioridad": _R_PRIORIDADES[p],
        "lang": _R_LANGS[lg],
        "texto": _inflate(blob[_HEADER.size :]),
    }


def stats(
    texto: str,
    *,
    tipo: str = "orientacion",
    id: int = 0,
    prioridad: str = "rutina",
    lang: str = "es",
) -> dict:
    """Métricas de compresión para reportar en el chip / panel / README."""
    blob = encode(texto, tipo=tipo, id=id, prioridad=prioridad, lang=lang)
    bruto = len(texto.encode("utf-8"))
    payload = len(blob) - _HEADER.size
    return {
        "bytes": bruto,
        "bytes_payload": payload,  # solo el DEFLATE, sin cabecera
        "bytes_comprimido": len(blob),  # envelope completo = lo que va al aire
        "ratio": round(bruto / len(blob), 2) if blob else 0.0,
    }


def roundtrip_ok(texto: str, **kw) -> bool:
    try:
        return decode(encode(texto, **kw))["texto"] == texto
    except Exception:
        return False
