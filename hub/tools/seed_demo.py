"""Siembra datos de demo en device.db + hub.db para ver el panel con contenido.

    cd hub && python tools/seed_demo.py [--reset]

No toca el modelo. Los textos de respuesta son los curados de guias.py.
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUB))

from guias import EMERGENCIAS, FIRST_AID, GUIAS, MOTIVOS  # noqa: E402
from recursos import SECTORES  # noqa: E402
from store import Store  # noqa: E402
NOMBRES = [
    "Ana López", "Diego Chox", "María Tuy", "Juan Sicay", "Rosa Ixtos",
    "Pedro Cúmez", "Lucía Mux", "Manuel Coj", "Catarina Sirin", "José Tzaj",
    "Elena Batz", "Francisco Ajché", "Petrona Sal", "Tomás Quexel",
]


def _mac(i: int) -> str:
    return f"AA:BB:CC:{i:02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}"


def _lora_falso(texto: str) -> dict:
    b = len(texto.encode())
    comp = max(10, int(b * 0.25) + 5)
    tramas = max(1, (comp + 62) // 63)
    return {"bytes_in": b, "bytes_comprimido": comp, "tramas": tramas,
            "ratio": round(b / comp, 2), "airtime_ms": tramas * 390.0}


def sembrar(reset: bool) -> None:
    if reset:
        for f in ("device.db", "hub.db"):
            (HUB / "data" / f).unlink(missing_ok=True)

    st = Store()
    random.seed(7)
    ahora = time.time()
    n_pac = 12
    macs: list[str] = []

    for i in range(n_pac):
        mac = _mac(i)
        macs.append(mac)
        st.put_perfil(
            mac,
            nombre=NOMBRES[i % len(NOMBRES)],
            edad=str(random.randint(2, 78)),
            sector=random.choice(SECTORES),
            alergias=random.choice(["", "", "penicilina", "asma", "diabetes"]),
        )
        # 1-4 conversaciones por persona, repartidas en los últimos 6 días
        for j in range(random.randint(1, 4)):
            mid = random.choice(list(GUIAS))
            g = GUIAS[mid]
            resp = g["orientacion"]
            edad_dias = random.random() * 6
            t = ahora - edad_dias * 86400
            st.device.execute("UPDATE pacientes SET creado_ts=? WHERE mac=?",
                              (t - 3600, mac))
            conv_id = f"{mac}-{j}-{int(t)}"
            # transcripción: motivo elegido + 2 repreguntas respondidas + orientación
            preg = g["preguntas"][:2]
            turnos = [{"rol": "user", "texto": f"Consulta por: {MOTIVOS[mid]}"}]
            for q in preg:
                turnos.append({"rol": "bot", "texto": q})
                turnos.append({"rol": "user", "texto": random.choice(
                    ["Sí", "No", "Desde ayer", "Un poco", "Desde hace dos días",
                     "No sé", "Más o menos"])})
            turnos.append({"rol": "bot", "texto": resp})
            st.registrar_conversacion(
                conv_id=conv_id, mac=mac, mensajes=turnos, motivo=mid,
                titulo=MOTIVOS[mid].capitalize(), prioridad=g["prioridad"],
            )
            cid = st.log_consulta(
                mac=mac, motivo=mid,
                texto=f"Consulta por: {MOTIVOS[mid]}",
                respuesta=resp, prioridad=g["prioridad"], fuente="modelo",
                lora=_lora_falso(resp), conversacion_id=conv_id,
            )
            for db in (st.device, st.hub):
                db.execute("UPDATE consultas SET ts=? WHERE id=?", (t, cid))
                db.execute("UPDATE conversaciones SET iniciada_ts=?, actualizada_ts=? "
                           "WHERE id=?", (t - 180, t, conv_id))
                db.commit()

    # un par de emergencias, una sin atender
    for k, (tipo, abierta) in enumerate([("mordedura", True), ("sangrado", False), ("respira", True)]):
        mac = random.choice(macs)
        pasos = " ".join(FIRST_AID[tipo])
        t = ahora - k * 900
        conv_id = f"{mac}-emg-{int(t)}"
        st.registrar_conversacion(
            conv_id=conv_id, mac=mac,
            mensajes=[{"rol": "user", "texto": f"🚨 {EMERGENCIAS[tipo]}"},
                      {"rol": "bot", "texto": pasos}],
            motivo=tipo, titulo="🚨 " + EMERGENCIAS[tipo].capitalize(),
            prioridad="emergencia", es_emergencia=True,
        )
        cid = st.log_consulta(
            mac=mac, motivo=tipo, texto=EMERGENCIAS[tipo], respuesta=pasos,
            prioridad="emergencia", fuente="curado", lora=_lora_falso(pasos),
            es_emergencia=True, tipo_emergencia=tipo, conversacion_id=conv_id,
        )
        for db in (st.device, st.hub):
            db.execute("UPDATE consultas SET ts=? WHERE id=?", (t, cid))
            db.execute("UPDATE alertas SET ts=? WHERE consulta_id=?", (t, cid))
            db.execute("UPDATE conversaciones SET iniciada_ts=?, actualizada_ts=? WHERE id=?",
                       (t, t, conv_id))
            db.commit()
        if not abierta:
            aid = st.hub.execute(
                "SELECT id FROM alertas WHERE consulta_id=?", (cid,)
            ).fetchone()["id"]
            st.atender_alerta(aid)

    r = st.resumen()
    print(f"sembrado: {r['pacientes']} pacientes · {r['conversaciones_total']} conversaciones · "
          f"{r['consultas_total']} consultas · {r['emergencias_abiertas']} emergencias abiertas · "
          f"{len(r['sectores'])} sectores")
    for s in r["sectores"]:
        print(f"  {s['sector']:22} {s['consultas']:2} consultas  "
              f"{s['alertas_abiertas']} alerta(s)  prioridad_max={s['prioridad_max']}")


if __name__ == "__main__":
    sembrar("--reset" in sys.argv)
