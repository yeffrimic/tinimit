# Registro de rendimiento — MedPsy en Tinimit

Generado por `python hub/tools/perf_log.py` el 2026-09-10 17:28 -0600.

## Modelo

- **Modelo**: `HEALTHCARE_4B_MEDICAL_Q4_K_M` — Qwen3-4B-Thinking (MedPsy-4B de QVAC)
- **Cuantización**: Q4_K_M
- **Runtime**: @qvac/sdk (tetherto.qvac_sdk) — runtime Bare + llama.cpp, 100% local
- **Device**: `gpu` (GPU: NVIDIA GeForce RTX 2060, 6144 MiB, 595.84)

## Hardware

- CPU: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz
- GPU: NVIDIA GeForce RTX 2060, 6144 MiB, 595.84
- RAM: 24.4 GB
- SO: Linux-7.0.11-76070011-generic-x86_64-with-glibc2.39 · Python 3.12.3

**Carga del modelo**: 12.7 s (incluye descarga de pesos GGUF la primera vez; luego es de disco).

## Prompts (caminos reales del hub)

Tokens y throughput vienen del `completionStats` de QVAC; TTFT también (en ms). Se corre un calentamiento previo que se descarta.

| Caso | predict | prompt tok | gen tok | TTFT | tok/s | gen (s) |
|---|--:|--:|--:|--:|--:|--:|
| frase_calida | 420 | 141 | 214 | 139.5 ms | 62.9 | 4.206 |
| orientacion_completa | 800 | 330 | 400 | 231.8 ms | 62.1 | 8.134 |
| clasificar_motivo | 256 | 116 | 248 | 85.9 ms | 62.6 | 5.039 |
| nota_emergencia | 400 | 163 | 400 | 135.8 ms | 61.9 | 8.059 |

### Detalle por caso

**frase_calida** — consulta_guiada → apertura cálida del modelo

- predict 420, temp 0.3
- prompt 141 tok · generados 214 tok (medido)
- TTFT 139.5 ms · generación 4.206 s · total 4.21 s · 62.9 tok/s
- salida 101 caracteres + 767 de razonamiento `<think>` (descartado)
- stats del motor: `{"time_to_first_token": 139.45000000000002, "tokens_per_second": 62.94075069492177, "cache_tokens": 0.0, "prompt_tokens": 141.0, "generated_tokens": 214.0, "emitted_tokens": 214.0, "avg_concurrent_seq": 1.0, "backend_device": {}}`
- muestra: «Agradezco tu confianza al compartir la fiebre alta de 38°C con escalofríos y tos leve desde anoche.…»

**orientacion_completa** — consulta_libre → _orientar (respuesta principal al vecino)

- predict 800, temp 0.3
- prompt 330 tok · generados 400 tok (medido)
- TTFT 231.8 ms · generación 8.134 s · total 8.13 s · 62.1 tok/s
- salida 331 caracteres + 1118 de razonamiento `<think>` (descartado)
- stats del motor: `{"time_to_first_token": 231.782, "tokens_per_second": 62.065213782077244, "cache_tokens": 0.0, "prompt_tokens": 330.0, "generated_tokens": 400.0, "emitted_tokens": 400.0, "avg_concurrent_seq": 1.0, "backend_device": {}}`
- muestra: «PRIORIDAD: <rutina>
ORIENTACION: Bebe mucha agua o jugo con poco azúcar a pequeños sorbos. Paracetamol según tu peso (pide consejo al farmacéutico). No uses abr…»

**clasificar_motivo** — consulta_libre (idioma maya) → _clasificar_motivo

- predict 256, temp 0.0
- prompt 116 tok · generados 248 tok (medido)
- TTFT 85.9 ms · generación 5.039 s · total 5.04 s · 62.6 tok/s
- salida 18 caracteres + 990 de razonamiento `<think>` (descartado)
- stats del motor: `{"time_to_first_token": 85.93900000000001, "tokens_per_second": 62.58725622516068, "cache_tokens": 0.0, "prompt_tokens": 116.0, "generated_tokens": 248.0, "emitted_tokens": 248.0, "avg_concurrent_seq": 1.0, "backend_device": {}}`
- muestra: «CATEGORIA: dolor…»

**nota_emergencia** — emergencia → nota corta del modelo

- predict 400, temp 0.2
- prompt 163 tok · generados 400 tok (medido)
- TTFT 135.8 ms · generación 8.059 s · total 8.06 s · 61.9 tok/s
- salida 18 caracteres + 1660 de razonamiento `<think>` (descartado)
- stats del motor: `{"time_to_first_token": 135.816, "tokens_per_second": 61.88146574296203, "cache_tokens": 0.0, "prompt_tokens": 163.0, "generated_tokens": 400.0, "emitted_tokens": 400.0, "avg_concurrent_seq": 1.0, "backend_device": {}}`
- muestra: «Monitorea signos…»

## Notas

- El TTFT del caso `orientacion_completa` incluye el bloque de razonamiento `<think>` de Qwen3-Thinking (el hub lo descarta vía el evento `thinkingDelta`).
- MedPsy-1.7B (`HEALTHCARE_1_7B_MEDICAL_Q4_K_M`) y MedGemma-4B (`MEDGEMMA_4B_IT_Q4_1`, sin `<think>`) están disponibles por `ALDEA_MODEL` y son ~2–3× más rápidos para hardware más modesto.
- Las repreguntas, primeros auxilios y disclaimers **no** llaman al modelo: son texto curado (`guias.py`), respuesta inmediata.
