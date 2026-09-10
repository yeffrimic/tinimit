"""Registro de rendimiento del modelo Psy (MedPsy) — carga, TTFT, throughput.

    cd hub && python tools/perf_log.py [--json salida.json] [--md salida.md]

Corre 4 prompts representativos de los caminos reales del hub (frase cálida,
orientación completa, clasificación de motivo, nota de emergencia) y mide:
carga del modelo, TTFT (time-to-first-token), tiempo de generación, caracteres y
tokens (del stats de llama.cpp cuando está, si no estimados), throughput.

Toda la inferencia es local sobre `@qvac/sdk`. No hay ninguna llamada de red a un
proveedor de modelos.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUB))

from qvac_engine import Engine, _DEVICE, _MODEL_NAME  # noqa: E402

# --- prompts representativos (mismos system prompts que usa medical.py) ---------
_SYS_ORIENT = (
    "Eres una promotora de salud de confianza de una aldea de Guatemala. Le hablas a un "
    "vecino que puede leer poco y tiene pocos recursos. Sé cálida y cercana. Frases MUY "
    "cortas, palabras de todos los días, nada de términos médicos. SIEMPRE das algo "
    "concreto para hacer en casa. Di con qué señales debe ir al puesto de salud. No des "
    "diagnósticos.\n\nResponde SIEMPRE así:\nPRIORIDAD: <rutina|urgente|emergencia>\n"
    "ORIENTACION: <máximo 55 palabras>"
)
_SYS_CALIDA = (
    "Eres una promotora de salud cercana de una aldea de Guatemala. Escribe SOLO UNA "
    "frase corta EN ESPAÑOL (máximo 16 palabras), cálida, que reconozca lo que la "
    "persona te contó. NO des consejos. Empieza directo con la frase."
)
_SYS_CLASIF = (
    "Clasifica la consulta de salud de un vecino en UNA de estas categorías: fiebre, "
    "dolor, diarrea, tos, herida, embarazo, nino, medicamento, otro. Si no encaja, di "
    "'ninguno'. Termina con: CATEGORIA: <palabra>"
)
_SYS_EMERG = (
    "Eres un asistente de un puesto de salud rural. Ya se enviaron los pasos de primeros "
    "auxilios. Añade UNA nota corta (máximo 35 palabras), en español sencillo, sobre qué "
    "vigilar mientras llega la ayuda. No repitas los pasos."
)

CASOS = [
    {
        "nombre": "frase_calida",
        "camino": "consulta_guiada → apertura cálida del modelo",
        "system": _SYS_CALIDA + " No pienses en voz alta; responde directo.",
        "turns": [{"role": "user", "content":
                   "Vino por fiebre. Me contó: 38 grados desde anoche, escalofríos, algo de tos."}],
        "predict": 420, "temp": 0.3,
    },
    {
        "nombre": "orientacion_completa",
        "camino": "consulta_libre → _orientar (respuesta principal al vecino)",
        "system": _SYS_ORIENT + "\n\nBásate en esta orientación estándar ya revisada y "
        "adáptala al caso (mismo consejo, tono cálido, máx. 55 palabras). No añadas "
        "tratamientos nuevos:\n«Da abundante líquido en pocas cantidades y seguido. "
        "Paracetamol según el peso. No abrigar de más. Acude si la fiebre pasa de 3 "
        "días, sube de 39 y no baja, o hay señales de alarma.»",
        "turns": [
            {"role": "user", "content":
             "Datos de la persona: edad 34, sector Panimaché I.\n\n"
             "Consulta por: fiebre"},
            {"role": "assistant", "content": "¿Pudiste medir la temperatura?"},
            {"role": "user", "content": "38 y medio, desde anoche, con escalofríos y me duele el cuerpo"},
        ],
        "predict": 800, "temp": 0.3,
    },
    {
        "nombre": "clasificar_motivo",
        "camino": "consulta_libre (idioma maya) → _clasificar_motivo",
        "system": _SYS_CLASIF,
        "turns": [{"role": "user", "content": "me arde mucho el estómago y tengo náuseas desde ayer"}],
        "predict": 256, "temp": 0.0,
    },
    {
        "nombre": "nota_emergencia",
        "camino": "emergencia → nota corta del modelo",
        "system": _SYS_EMERG,
        "turns": [{"role": "user", "content":
                   "Tipo de emergencia: mordedura de serpiente o animal.\n"
                   "Lo que describe el vecino: le mordió una barba amarilla en el pie hace 20 minutos, "
                   "ya se está hinchando.\nDatos de la persona: edad 41, sector Xepiacul."}],
        "predict": 400, "temp": 0.2,
    },
]


def _hardware() -> dict:
    hw: dict = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or platform.machine(),
        "device_config": _DEVICE,
    }
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    hw["cpu"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    try:
        with open("/proc/meminfo") as f:
            kb = int(f.readline().split()[1])
            hw["ram_gb"] = round(kb / 1e6, 1)
    except (OSError, ValueError):
        pass
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if out:
            hw["gpu"] = out
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return hw


def _plano(o):
    """Convierte recursivamente el stats de QVAC (objetos anidados) a algo serializable."""
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    if isinstance(o, dict):
        return {k: _plano(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plano(v) for v in o]
    for attr in ("model_dump", "dict", "_asdict"):
        fn = getattr(o, attr, None)
        if callable(fn):
            try:
                return _plano(fn())
            except Exception:  # noqa: BLE001
                pass
    d = getattr(o, "__dict__", None)
    if d:
        return {k: _plano(v) for k, v in d.items() if not k.startswith("_")}
    return str(o)


def _tok_out(m: dict) -> tuple[int, str]:
    """Tokens generados: del stats de QVAC si viene, si no estimado por chars."""
    st = _plano(m.get("raw_stats")) or {}
    for k in ("generated_tokens", "emitted_tokens", "predicted_tokens", "predicted_n",
              "n_predicted", "completion_tokens", "output_tokens"):
        if isinstance(st.get(k), (int, float)) and st[k] > 0:
            return int(st[k]), "medido"
    total = m.get("chars_out", 0) + m.get("chars_think", 0)
    return round(total / 3.6), "estimado (chars/3.6)"


def _sdk(m: dict, *keys):
    st = _plano(m.get("raw_stats")) or {}
    for k in keys:
        if isinstance(st.get(k), (int, float)):
            return st[k]
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    _docs = HUB.parent / "docs"
    ap.add_argument("--json", type=Path, default=_docs / "rendimiento.json")
    ap.add_argument("--md", type=Path, default=_docs / "rendimiento.md")
    args = ap.parse_args()

    eng = Engine()
    hw = _hardware()
    print(f"Modelo: {_MODEL_NAME}  ·  device: {_DEVICE}")
    print(f"Hardware: {hw.get('cpu','?')} · {hw.get('gpu','sin GPU')} · {hw.get('ram_gb','?')} GB RAM\n")

    print("Cargando el modelo (la 1ª vez descarga los pesos GGUF del registro de QVAC)…")
    t0 = time.monotonic()
    await eng.connect()
    await eng._ensure_model()  # noqa: SLF001
    carga_s = round(time.monotonic() - t0, 1)
    print(f"  carga: {carga_s} s\n")

    # calentamiento (descarta la 1ª que suele incluir compilación de kernels)
    await eng.generate(system="di hola", turns=[{"role": "user", "content": "hola"}],
                       max_tokens=8, temperature=0.0)

    resultados = []
    for c in CASOS:
        m: dict = {}
        t = time.monotonic()
        salida = await eng.generate(system=c["system"], turns=c["turns"],
                                    max_tokens=c["predict"], temperature=c["temp"],
                                    metrics=m)
        wall = round(time.monotonic() - t, 2)
        toks, origen = _tok_out(m)
        ttft_ms = _sdk(m, "time_to_first_token")
        tps = _sdk(m, "tokens_per_second")
        if tps is None and m.get("gen_s"):
            tps = round(toks / m["gen_s"], 1)
        r = {
            "caso": c["nombre"], "camino": c["camino"],
            "predict": c["predict"], "temp": c["temp"],
            "prompt_tokens": _sdk(m, "prompt_tokens"),
            "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else (
                round(m["ttft_s"] * 1000, 1) if m.get("ttft_s") else None),
            "gen_s": m.get("gen_s"), "wall_s": wall,
            "tokens_salida": toks, "tokens_origen": origen,
            "tok_por_s": round(tps, 1) if tps is not None else None,
            "chars_out": m.get("chars_out"), "chars_think": m.get("chars_think"),
            "raw_stats": _plano(m.get("raw_stats")),
            "muestra_salida": salida[:160],
        }
        resultados.append(r)
        print(f"· {c['nombre']:22} TTFT {r['ttft_ms']} ms · gen {r['gen_s']}s · "
              f"prompt {r['prompt_tokens']} / gen {toks} tok · {r['tok_por_s']} tok/s")

    await eng.close()

    reporte = {
        "modelo": _MODEL_NAME,
        "cuantizacion": "Q4_K_M" if "Q4_K_M" in _MODEL_NAME else (
            "Q4_1" if "Q4_1" in _MODEL_NAME else "ver nombre del modelo"),
        "base": "Qwen3-4B-Thinking (MedPsy-4B de QVAC)",
        "sdk": "@qvac/sdk (tetherto.qvac_sdk) — runtime Bare + llama.cpp, 100% local",
        "hardware": hw,
        "carga_modelo_s": carga_s,
        "fecha": time.strftime("%Y-%m-%d %H:%M %z"),
        "casos": resultados,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(reporte, ensure_ascii=False, indent=2, default=str))
    _escribir_md(args.md.resolve(), reporte)
    print(f"\n→ {args.json}\n→ {args.md.resolve()}")


def _escribir_md(path: Path, r: dict) -> None:
    hw = r["hardware"]
    lines = [
        "# Registro de rendimiento — MedPsy en Tinimit",
        "",
        f"Generado por `python hub/tools/perf_log.py` el {r['fecha']}.",
        "",
        "## Modelo",
        "",
        f"- **Modelo**: `{r['modelo']}` — {r['base']}",
        f"- **Cuantización**: {r['cuantizacion']}",
        f"- **Runtime**: {r['sdk']}",
        f"- **Device**: `{hw.get('device_config')}` "
        f"({'GPU: ' + hw['gpu'] if hw.get('gpu') else 'CPU'})",
        "",
        "## Hardware",
        "",
        f"- CPU: {hw.get('cpu','?')}",
        f"- GPU: {hw.get('gpu','sin GPU dedicada')}",
        f"- RAM: {hw.get('ram_gb','?')} GB",
        f"- SO: {hw.get('os','?')} · Python {hw.get('python','?')}",
        "",
        f"**Carga del modelo**: {r['carga_modelo_s']} s "
        "(incluye descarga de pesos GGUF la primera vez; luego es de disco).",
        "",
        "## Prompts (caminos reales del hub)",
        "",
        "Tokens y throughput vienen del `completionStats` de QVAC; TTFT también "
        "(en ms). Se corre un calentamiento previo que se descarta.",
        "",
        "| Caso | predict | prompt tok | gen tok | TTFT | tok/s | gen (s) |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]
    for c in r["casos"]:
        lines.append(
            f"| {c['caso']} | {c['predict']} | {int(c['prompt_tokens']) if c['prompt_tokens'] else '—'} | "
            f"{c['tokens_salida']} | {c['ttft_ms']} ms | {c['tok_por_s']} | {c['gen_s']} |"
        )
    lines += ["", "### Detalle por caso", ""]
    for c in r["casos"]:
        lines += [
            f"**{c['caso']}** — {c['camino']}",
            "",
            f"- predict {c['predict']}, temp {c['temp']}",
            f"- prompt {int(c['prompt_tokens']) if c['prompt_tokens'] else '—'} tok · generados {c['tokens_salida']} tok "
            f"({c['tokens_origen']})",
            f"- TTFT {c['ttft_ms']} ms · generación {c['gen_s']} s · total {c['wall_s']} s "
            f"· {c['tok_por_s']} tok/s",
            f"- salida {c['chars_out']} caracteres"
            + (f" + {c['chars_think']} de razonamiento `<think>` (descartado)"
               if c['chars_think'] else ""),
        ]
        if c.get("raw_stats"):
            lines.append("- stats del motor: `"
                         + json.dumps(c["raw_stats"], ensure_ascii=False, default=str) + "`")
        lines += [f"- muestra: «{c['muestra_salida']}…»", ""]
    lines += [
        "## Notas",
        "",
        "- El TTFT del caso `orientacion_completa` incluye el bloque de razonamiento "
        "`<think>` de Qwen3-Thinking (el hub lo descarta vía el evento `thinkingDelta`).",
        "- MedPsy-1.7B (`HEALTHCARE_1_7B_MEDICAL_Q4_K_M`) y MedGemma-4B "
        "(`MEDGEMMA_4B_IT_Q4_1`, sin `<think>`) están disponibles por `ALDEA_MODEL` y "
        "son ~2–3× más rápidos para hardware más modesto.",
        "- Las repreguntas, primeros auxilios y disclaimers **no** llaman al modelo: son "
        "texto curado (`guias.py`), respuesta inmediata.",
    ]
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
