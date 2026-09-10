#!/usr/bin/env bash
# Arranca el hub de Aldea Salud. La inferencia es 100% local (QVAC).
set -euo pipefail
cd "$(dirname "$0")"

VENV="${ALDEA_VENV:-/home/yeffrimic/Documents/qvac/.venv}"
# modelo por defecto: MedPsy-4B (lo define qvac_engine.py). Alternativas:
#   HEALTHCARE_1_7B_MEDICAL_Q4_K_M  ·  MEDGEMMA_4B_IT_Q4_1  ·  QWEN3_1_7B_INST_Q4
[ -n "${ALDEA_MODEL:-}" ] && export ALDEA_MODEL
export ALDEA_DEVICE="${ALDEA_DEVICE:-gpu}"                  # gpu | cpu
export ALDEA_DEBUG="${ALDEA_DEBUG:-}"                       # =1 imprime prompt + respuesta del modelo

exec "$VENV/bin/python" -m uvicorn server:app --host 0.0.0.0 --port "${ALDEA_PORT:-8000}"
