"""Envoltura del SDK de QVAC — carga perezosa del modelo médico y `completion`.

Toda la inferencia ocurre aquí, 100% local sobre el runtime de QVAC (Bare worker +
llama.cpp). No hay ninguna llamada de red a un proveedor de modelos: `load_model`
descarga los pesos GGUF del registro de QVAC la primera vez y luego corre offline.

Patrón tomado de las demos propias en `~/Documents/qvac/` (`app.py`, `qvac.py`):
`Client().connect()` en el arranque, `load_model` perezoso, `completion` streaming,
`unload_model` + `close()` al apagar.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from tetherto.qvac_sdk import Client, completion, load_model, unload_model
from tetherto.qvac_sdk import models as _models

# Modelo por defecto: MedPsy-4B de QVAC (Qwen3-4B-Thinking afinado en salud;
# mejor en HealthBench que MedGemma). Entra en 6 GB de VRAM.
# Alternativas por env ALDEA_MODEL:
#   HEALTHCARE_1_7B_MEDICAL_Q4_K_M  (MedPsy-1.7B, más rápido)
#   MEDGEMMA_4B_IT_Q4_1             (MedGemma, sin razonamiento, más rápido)
_MODEL_NAME = os.environ.get("ALDEA_MODEL", "HEALTHCARE_4B_MEDICAL_Q4_K_M")
_DEVICE = os.environ.get("ALDEA_DEVICE", "gpu")  # "gpu" | "cpu"

# ALDEA_DEBUG=1 -> imprime en stderr el prompt exacto que entra al modelo y su
# respuesta cruda, para verificar que la consulta llega y qué contesta la IA.
_DEBUG = os.environ.get("ALDEA_DEBUG", "") not in ("", "0", "false", "no")


def _sangrar(txt: str) -> str:
    return "\n".join("    " + l for l in (txt or "(vacío)").splitlines()) or "    (vacío)"


import re as _re

_THINK = _re.compile(r"<think>.*?</think>\s*", _re.DOTALL | _re.IGNORECASE)


def _quitar_think(txt: str) -> str:
    txt = _THINK.sub("", txt)
    # bloque de razonamiento sin cerrar (se agotaron los tokens): quita hasta </think>
    # o hasta la primera línea PRIORIDAD:
    if "<think>" in txt.lower():
        m = _re.search(r"</think>|(?=PRIORIDAD\s*[:\-])", txt, _re.IGNORECASE)
        txt = txt[m.end():] if m else ""
    return txt.lstrip()


def _resolve_model():
    try:
        return getattr(_models, _MODEL_NAME)
    except AttributeError:
        disponibles = [n for n in dir(_models) if n.isupper()]
        raise SystemExit(
            f"ALDEA_MODEL={_MODEL_NAME!r} no existe en tetherto.qvac_sdk.models.\n"
            f"Algunos válidos: {', '.join(disponibles[:12])} ..."
        )


_last_pct = -1


def _on_progress(p) -> None:
    global _last_pct
    pct = int(getattr(p, "percentage", 0))
    if pct == _last_pct and pct < 100:
        return
    _last_pct = pct
    line = f"  descargando modelo {pct}% ({p.downloaded / 1e6:.0f}/{p.total / 1e6:.0f} MB)"
    print(line, end="\r" if sys.stderr.isatty() else "\n", file=sys.stderr)
    if pct >= 100:
        print(file=sys.stderr)


class Engine:
    """Gestor de un único modelo con carga perezosa y acceso serializado.

    llama.cpp no admite peticiones concurrentes sobre el mismo contexto, así que
    `generate()` toma un lock: en un kiosko de aldea las consultas son de a una.
    """

    def __init__(self) -> None:
        self._client: Client | None = None
        self._model_id: str | None = None
        self._model_src = _resolve_model()
        self._lock = asyncio.Lock()
        self._load_lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return _MODEL_NAME

    @property
    def loaded(self) -> bool:
        return self._model_id is not None

    async def connect(self) -> None:
        if self._client is None:
            self._client = await Client().connect()

    async def _ensure_model(self) -> None:
        if self._model_id is not None:
            return
        async with self._load_lock:
            if self._model_id is not None:
                return
            await self.connect()
            assert self._client is not None
            config: dict = {"ctx_size": 4096}
            if _DEVICE == "gpu":
                config |= {"device": "gpu", "main-gpu": "dedicated"}
            else:
                config |= {"device": "cpu"}
            print(f"Cargando {_MODEL_NAME} en {_DEVICE} (la primera vez descarga los pesos)...",
                  file=sys.stderr)
            self._model_id = await load_model(
                self._client.transport,
                model_src=self._model_src,
                model_config=config,
                on_progress=_on_progress,
            )
            print(f"Modelo {_MODEL_NAME} listo.", file=sys.stderr)

    async def generate(
        self,
        *,
        system: str,
        turns: list[dict[str, str]],
        max_tokens: int = 320,
        temperature: float = 0.3,
        metrics: dict | None = None,
    ) -> str:
        """Genera una respuesta completa (no streaming hacia afuera).

        `turns` es una lista [{role: "user"|"assistant", content: str}, ...].
        El `system` se pliega en el primer turno de usuario porque las plantillas
        de chat de MedGemma/Qwen no tienen rol de sistema propio en este envoltorio.

        MedPsy (Qwen3-Thinking) razona antes de responder: ese razonamiento llega
        como `thinkingDelta` (lo descartamos) y, por si el motor no lo separa, se
        quita cualquier bloque `<think>…</think>` residual del texto final.
        """
        await self._ensure_model()
        assert self._client is not None and self._model_id is not None

        history = _build_history(system, turns)
        if _DEBUG:
            print("\n" + "═" * 70, file=sys.stderr)
            print(f"→ MODELO {_MODEL_NAME}  (predict={max_tokens} temp={temperature})", file=sys.stderr)
            for h in history:
                print(f"  [{h['role']}]\n{_sangrar(h['content'])}", file=sys.stderr)
        t0 = time.monotonic()
        t_first = None
        raw_stats = None
        async with self._lock:
            run = completion(
                self._client.transport,
                model_id=self._model_id,
                history=history,
                capture_thinking=True,
                generation_params={
                    "predict": max_tokens,
                    "temp": temperature,
                    "repeat_penalty": 1.15,
                },
            )
            out: list[str] = []
            thinking: list[str] = []
            async for event in run.events:
                if event.type == "contentDelta":
                    if t_first is None:
                        t_first = time.monotonic()
                    out.append(event.text)
                elif event.type == "thinkingDelta":
                    if t_first is None:
                        t_first = time.monotonic()
                    thinking.append(event.text)
                elif event.type == "completionStats":
                    raw_stats = getattr(event, "stats", None)
        t_end = time.monotonic()
        salida = _quitar_think("".join(out)).strip()

        if metrics is not None:
            metrics.update({
                "ttft_s": round((t_first - t0), 3) if t_first else None,
                "gen_s": round(t_end - t0, 3),
                "chars_out": len("".join(out)),
                "chars_think": len("".join(thinking)),
                "predict": max_tokens,
                "raw_stats": _stats_a_dict(raw_stats),
            })
        if _DEBUG:
            dur = time.monotonic() - t0
            if thinking:
                print(f"  (razonamiento {len(''.join(thinking))} car., descartado)",
                      file=sys.stderr)
            print(f"← RESPUESTA CRUDA ({dur:.1f}s)\n{_sangrar(salida)}", file=sys.stderr)
            print("═" * 70 + "\n", file=sys.stderr)
        return salida

    async def close(self) -> None:
        if self._client is not None:
            try:
                if self._model_id is not None:
                    await unload_model(self._client.transport, self._model_id)
            finally:
                await self._client.close()
                self._client = None
                self._model_id = None


def _stats_a_dict(s) -> dict | None:
    """El objeto `stats` de QVAC (estilo llama.cpp) llega como `Any`; lo pasamos a
    un dict plano para el registro de rendimiento."""
    if s is None:
        return None
    if isinstance(s, dict):
        return s
    for attr in ("model_dump", "dict", "_asdict"):
        fn = getattr(s, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:  # noqa: BLE001
                pass
    d = getattr(s, "__dict__", None)
    if d:
        return {k: v for k, v in d.items() if not k.startswith("_")}
    return {"repr": repr(s)}


def _build_history(system: str, turns: list[dict[str, str]]) -> list[dict]:
    history: list[dict] = []
    folded_system = False
    for turn in turns:
        role = turn["role"]
        content = turn["content"]
        if role == "user" and not folded_system:
            content = f"{system.strip()}\n\n---\n\n{content}"
            folded_system = True
        history.append({"role": role, "content": content})
    if not folded_system:
        history.insert(0, {"role": "user", "content": system.strip()})
    return history
