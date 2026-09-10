"""Hub central de Tinimit — FastAPI.

Sirve el kiosko y expone la orientación médica. La inferencia corre 100% local en
el runtime de QVAC (ver `qvac_engine.py`); este proceso no habla con ninguna API de
modelos. La nube, si se usa, es solo para exponer la interfaz o como túnel de bytes.

Arranque:
    cd hub
    ALDEA_MODEL=MEDGEMMA_4B_IT_Q4_1 \
    /home/yeffrimic/Documents/qvac/.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000

Prueba de que no hay inferencia en la nube:
    grep -riE "openai|anthropic|groq|api[_-]?key|https?://" hub/*.py
    # -> solo cadenas de documentación; ninguna llamada de red saliente
"""

from __future__ import annotations

import itertools
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_DEBUG = os.environ.get("ALDEA_DEBUG", "") not in ("", "0", "false", "no")


def _dbg(*a) -> None:
    if _DEBUG:
        print(*a, file=sys.stderr)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import codec
import link
import medical
from guias import EMERGENCIAS, GUIAS, MOTIVOS
from qvac_engine import Engine
from store import get_store

_KIOSK_HTML = Path(__file__).resolve().parents[1] / "prototipo" / "kiosk.html"
_PANEL_HTML = Path(__file__).with_name("panel.html")
_INSUMOS_HTML = Path(__file__).with_name("insumos.html")

engine = Engine()
store = get_store()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await engine.connect()
    print(f"Hub listo. Modelo: {engine.model_name} (carga perezosa en la 1ª consulta).")
    print("Kiosko en http://127.0.0.1:8000  ·  Panel en /panel  ·  API en /api/*")
    yield
    await engine.close()


app = FastAPI(title="Tinimit — Hub", lifespan=lifespan)

# El kiosko se sirve desde `GET /` (mismo origen) hoy y también desde el SoftAP del
# ESP32 (192.168.4.1, también mismo origen). CORS abierto cubre el caso de servir el
# kiosko desde otro puerto en desarrollo. Sin `allow_credentials` (no hay cookies).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# modelos de entrada/salida
# ---------------------------------------------------------------------------
class Mensaje(BaseModel):
    rol: str
    texto: str


class ConsultaIn(BaseModel):
    mac: str
    motivo: str | None = None
    mensajes: list[Mensaje] = Field(default_factory=list)
    lang: str = "es"  # "es" | "cak" — para el envelope del códec
    conversacion_id: str = ""  # id de conversación (lo genera el kiosko)


class EmergenciaIn(BaseModel):
    mac: str
    tipo: str
    descripcion: str = ""
    lang: str = "es"
    conversacion_id: str = ""


class PerfilIn(BaseModel):
    nombre: str = ""
    edad: str = ""
    sector: str = ""
    alergias: str = ""


def _normalizar(mensajes: list[Mensaje]) -> list[dict]:
    """Acepta rol 'user'/'assistant' y también los alias del kiosko ('bot','sys')."""
    mapa = {"user": "user", "tu": "user", "assistant": "assistant", "bot": "assistant"}
    out: list[dict] = []
    for m in mensajes:
        rol = mapa.get(m.rol.lower())
        if rol and m.texto.strip():
            out.append({"rol": rol, "texto": m.texto.strip()})
    return out


_seq = itertools.count(1)


def _next_id() -> int:
    return next(_seq) & 0xFFFF


def _dir_stats(
    texto: str, *, tipo: str, prioridad: str, lang: str, msg_id: int, hops: int
) -> tuple[dict, dict]:
    """Comprime `texto` con el códec real y simula su envío por el enlace."""
    env = codec.encode(texto, tipo=tipo, id=msg_id, prioridad=prioridad, lang=lang)
    sim = link.simular(env, hops=hops, msg_id=msg_id & 0xFF)
    bruto = len(texto.encode("utf-8"))
    stats = {
        "bytes": bruto,
        "bytes_comprimido": len(env),  # envelope completo = lo que va al aire
        "tramas": sim["tramas"],
        "airtime_ms": sim["airtime_ms"],
        "ratio": round(bruto / len(env), 2) if env else 0.0,
    }
    return stats, sim


def _lora(
    texto_in: str,
    texto_out: str,
    *,
    tipo_in: str,
    tipo_out: str,
    prioridad: str,
    lang: str,
    hops: int = 2,
) -> dict:
    """Coste real del enlace LoRa para un intercambio uplink + downlink.

    Las 5 claves estables (`bytes_in, bytes_comprimido, tramas, airtime_ms, saltos`)
    describen el DOWNLINK — la respuesta que el vecino espera y que el chip del kiosko
    muestra bajo cada burbuja del bot.
    """
    mid = _next_id()
    up, up_sim = _dir_stats(
        texto_in, tipo=tipo_in, prioridad=prioridad, lang=lang, msg_id=mid, hops=hops
    )
    down, down_sim = _dir_stats(
        texto_out, tipo=tipo_out, prioridad=prioridad, lang=lang, msg_id=mid, hops=hops
    )
    tot_bruto = up["bytes"] + down["bytes"]
    tot_comp = up["bytes_comprimido"] + down["bytes_comprimido"]
    return {
        "bytes_in": down["bytes"],
        "bytes_comprimido": down["bytes_comprimido"],
        "tramas": down["tramas"],
        "airtime_ms": down["airtime_ms"],
        "saltos": hops,
        "ratio": down["ratio"],
        "provisional": False,
        "id": mid,
        "uplink": up,
        "downlink": down,
        "airtime_total_ms": round(up["airtime_ms"] + down["airtime_ms"], 1),
        "ratio_total": round(tot_bruto / tot_comp, 2) if tot_comp else 0.0,
        "hops": down_sim["hops"],
        "dwell_ok": up_sim["dwell_ok"] and down_sim["dwell_ok"],
    }


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "modelo": engine.model_name,
        "modelo_cargado": engine.loaded,
        "motivos": list(MOTIVOS),
        "emergencias": list(EMERGENCIAS),
    }


def _perfil_con_historial(mac: str, conv_id: str = "") -> dict | None:
    perfil = store.get_perfil(mac)
    hist = store.contexto_historial(mac, excluir_conv=conv_id)
    if hist:
        perfil = {**(perfil or {}), "historial": hist}
    return perfil


def _titulo_consulta(motivo: str | None, mensajes: list[dict]) -> str:
    """Título de la conversación: la etiqueta del motivo si hay, si no se deja que
    `store` lo saque del primer mensaje."""
    if motivo and motivo in MOTIVOS:
        return MOTIVOS[motivo].capitalize()
    return ""


def _transcripcion(mensajes: list[dict], respuesta: str) -> list[dict]:
    turnos = [{"rol": m["rol"], "texto": m["texto"]} for m in mensajes]
    if respuesta:
        turnos.append({"rol": "assistant", "texto": respuesta})
    return turnos


@app.post("/api/consulta")
async def api_consulta(body: ConsultaIn) -> dict:
    mensajes = _normalizar(body.mensajes)
    if not any(m["rol"] == "user" for m in mensajes):
        raise HTTPException(422, "Hace falta al menos un mensaje de la persona.")

    perfil = _perfil_con_historial(body.mac, body.conversacion_id)
    recursos = store.recursos_inventario()
    _dbg(f"\n▼ /api/consulta  mac={body.mac}  motivo={body.motivo!r}  lang={body.lang}"
         f"  conv={body.conversacion_id or '—'}")
    for m in mensajes:
        _dbg(f"    {m['rol']}: {m['texto']}")
    if perfil and perfil.get("historial"):
        _dbg(f"    (historial→modelo: {perfil['historial']})")
    if body.motivo and body.motivo in GUIAS:
        res = await medical.consulta_guiada(
            engine, motivo=body.motivo, mensajes=mensajes, perfil=perfil,
            recursos=recursos, lang=body.lang,
        )
    else:
        res = await medical.consulta_libre(
            engine, mensajes=mensajes, perfil=perfil, recursos=recursos, lang=body.lang
        )

    ultimo_usuario = next(
        (m["texto"] for m in reversed(mensajes) if m["rol"] == "user"), ""
    )
    lora = _lora(
        ultimo_usuario,
        res.respuesta,
        tipo_in="consulta",
        tipo_out="repregunta" if res.estado == "seguimiento" else "orientacion",
        prioridad=res.prioridad,
        lang=body.lang,
    )

    _dbg(f"▲ estado={res.estado}  prioridad={res.prioridad}  fuente={res.fuente}  "
         f"idioma={res.idioma}  tramas={lora['tramas']}  ratio={lora['ratio']}×")
    _dbg(f"    respuesta: {res.respuesta[:200]}")

    # la conversación se actualiza en cada turno (repregunta o final) para que el
    # panel tenga la transcripción al día y el kiosko un id estable que retomar
    conv_id = store.registrar_conversacion(
        conv_id=body.conversacion_id,
        mac=body.mac,
        mensajes=_transcripcion(mensajes, res.respuesta),
        motivo=body.motivo or "",
        titulo=_titulo_consulta(body.motivo, mensajes),
        prioridad=res.prioridad,
        es_emergencia=False,
    )

    if res.estado == "final":
        texto = " · ".join(m["texto"] for m in mensajes if m["rol"] == "user")
        store.log_consulta(
            mac=body.mac,
            motivo=body.motivo or "",
            texto=texto,
            respuesta=res.respuesta,
            prioridad=res.prioridad,
            fuente=res.fuente,
            lora=lora,
            conversacion_id=conv_id,
        )

    return {
        "estado": res.estado,
        "respuesta": res.respuesta,
        "prioridad": res.prioridad,
        "fuente": res.fuente,
        "idioma_respuesta": res.idioma,  # "es" si cayó a español de respaldo
        "conversacion_id": conv_id,
        "lora": lora,
    }


@app.post("/api/emergencia")
async def api_emergencia(body: EmergenciaIn) -> dict:
    perfil = store.get_perfil(body.mac)
    res = await medical.emergencia(
        engine, tipo=body.tipo, descripcion=body.descripcion, perfil=perfil,
        lang=body.lang,
    )
    texto_out = " ".join(res.primeros_auxilios) + (" " + res.nota if res.nota else "")
    lora = _lora(
        body.descripcion or body.tipo,
        texto_out,
        tipo_in="emergencia",
        tipo_out="emergencia_ack",
        prioridad="emergencia",
        lang=body.lang,
    )
    desc = body.descripcion or EMERGENCIAS.get(res.tipo, res.tipo)
    conv_id = store.registrar_conversacion(
        conv_id=body.conversacion_id,
        mac=body.mac,
        mensajes=[{"rol": "user", "texto": f"🚨 {desc}"},
                  {"rol": "assistant", "texto": texto_out}],
        motivo=res.tipo,
        titulo="🚨 " + EMERGENCIAS.get(res.tipo, res.tipo).capitalize(),
        prioridad="emergencia",
        es_emergencia=True,
    )
    store.log_consulta(
        mac=body.mac,
        motivo=res.tipo,
        texto=desc,
        respuesta=texto_out,
        prioridad="emergencia",
        fuente=res.fuente,
        lora=lora,
        es_emergencia=True,
        tipo_emergencia=res.tipo,
        conversacion_id=conv_id,
    )
    return {
        "ack": "Alerta recibida por el hub. El puesto de salud fue notificado.",
        "tipo": res.tipo,
        "prioridad": res.prioridad,
        "primeros_auxilios": res.primeros_auxilios,
        "nota": res.nota,
        "fuente": res.fuente,
        "idioma_respuesta": res.idioma,
        "conversacion_id": conv_id,
        "meta": {
            "mac": body.mac,
            "sector": (perfil or {}).get("sector", ""),
            "lora": lora,
        },
    }


@app.get("/api/perfil/{mac}")
async def get_perfil(mac: str) -> dict:
    perfil = store.get_perfil(mac)
    if perfil is None:
        raise HTTPException(404, "Sin perfil para esa MAC.")
    return perfil


@app.put("/api/perfil/{mac}")
async def put_perfil(mac: str, body: PerfilIn) -> dict:
    return store.put_perfil(mac, **body.model_dump())


# ---------------------------------------------------------------------------
# panel del hub (administración)
# ---------------------------------------------------------------------------
@app.get("/api/panel/resumen")
async def panel_resumen() -> dict:
    return store.resumen()


@app.get("/api/panel/feed")
async def panel_feed(desde_id: int = 0) -> dict:
    return {
        "conversaciones": store.conversaciones(limit=80),
        "consultas": store.feed(desde_id=desde_id),
        "alertas": store.alertas_abiertas(),
    }


@app.get("/api/panel/conversaciones")
async def panel_conversaciones(mac: str = "", limit: int = 80) -> dict:
    return {"conversaciones": store.conversaciones(mac=mac or None, limit=limit)}


@app.get("/api/panel/conversacion/{conv_id}")
async def panel_conversacion(conv_id: str) -> dict:
    c = store.conversacion(conv_id)
    if c is None:
        raise HTTPException(404, "No encuentro esa conversación.")
    return c


@app.get("/api/panel/buscar")
async def panel_buscar(q: str = "") -> dict:
    return {"pacientes": store.buscar_pacientes(q.strip()) if q.strip() else []}


@app.get("/api/panel/paciente/{mac}")
async def panel_paciente(mac: str) -> dict:
    p = store.paciente(mac)
    if p is None:
        raise HTTPException(404, "Sin datos para esa MAC.")
    return p


@app.post("/api/panel/alerta/{alerta_id}/atender")
async def panel_atender(alerta_id: int) -> dict:
    store.atender_alerta(alerta_id)
    return {"ok": True}


@app.get("/api/panel/recursos")
async def panel_recursos() -> dict:
    from recursos import (
        HIERBAS, HIERBAS_EVITAR, NO_HAY_EN_LA_ALDEA, SECTORES,
        cobertura_por_sector,
    )
    puntos = store.puntos()
    return {
        "puntos": puntos,
        "sectores": SECTORES,
        "cobertura": cobertura_por_sector(puntos),
        "hierbas": HIERBAS,
        "hierbas_evitar": HIERBAS_EVITAR,
        "no_hay_en_la_aldea": NO_HAY_EN_LA_ALDEA,
    }


@app.post("/api/panel/recursos/{punto_id}/{item}")
async def panel_recurso_ajustar(punto_id: str, item: str, cantidad: int) -> dict:
    r = store.ajustar_recurso(punto_id, item, cantidad)
    if r is None:
        raise HTTPException(404, "Ese recurso no está en ese punto.")
    return r


@app.post("/api/panel/enlace")
async def panel_enlace(activo: bool = True) -> dict:
    """Demo: simula el enlace device -> hub central. Al reactivarlo, sincroniza."""
    store.enlace_hub = activo
    movidas = store.sync_device_to_hub() if activo else {}
    return {"enlace_hub": store.enlace_hub, "sincronizado": movidas}


@app.post("/api/sync")
async def api_sync() -> dict:
    return {"sincronizado": store.sync_device_to_hub()}


@app.get("/panel", response_class=HTMLResponse)
async def panel() -> str:
    if not _PANEL_HTML.exists():
        raise HTTPException(500, f"No encuentro {_PANEL_HTML}")
    return _PANEL_HTML.read_text(encoding="utf-8")


@app.get("/insumos", response_class=HTMLResponse)
async def insumos() -> str:
    if not _INSUMOS_HTML.exists():
        raise HTTPException(500, f"No encuentro {_INSUMOS_HTML}")
    return _INSUMOS_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# kiosko
# ---------------------------------------------------------------------------
_SKELETON = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Tinimit</title>
</head>
<body>
{cuerpo}
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def kiosko() -> str:
    if not _KIOSK_HTML.exists():
        raise HTTPException(500, f"No encuentro {_KIOSK_HTML}")
    return _SKELETON.format(cuerpo=_KIOSK_HTML.read_text(encoding="utf-8"))
