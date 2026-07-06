#!/usr/bin/env bash
# Performance testing with AIPerf (NVIDIA's open-source LLM load generator,
# github.com/ai-dynamo/aiperf — the successor to genai-perf, whose CLI it
# keeps; NVIDIA's NIM benchmarking guides now use AIPerf).
#
#   make perf                 # test the 'coder' model through the gateway
#   make perf MODEL=general
#   CONCURRENCY=8 tests/perf/run-perf.sh coder
#
# Reports TTFT (time to first token), inter-token latency, request latency,
# and output tokens/sec — the four numbers that define LLM service feel.
# Results land in tests/perf/results/<model>-<timestamp>/ so you can diff runs:
# ALWAYS capture a baseline before a change (backend swap, upgrade, new GPU)
# and compare after. See tests/perf/README.md for how to read the numbers.
set -euo pipefail

MODEL="${1:-coder}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:4000}"
CONCURRENCY="${CONCURRENCY:-4}"        # simultaneous users to simulate
REQUESTS="${REQUESTS:-32}"             # total requests to measure
ISL="${ISL:-512}"                      # input sequence length (tokens)
OSL="${OSL:-256}"                      # output sequence length (tokens)

cd "$(dirname "$0")"
source ../../.env 2>/dev/null || true
: "${LITELLM_MASTER_KEY:?set LITELLM_MASTER_KEY (or put it in .env)}"

# AIPerf is a plain pip package. Use it if installed; otherwise run it
# ephemerally via uv (https://docs.astral.sh/uv/) if that's available.
if command -v aiperf >/dev/null 2>&1; then
  AIPERF=(aiperf)
elif command -v uvx >/dev/null 2>&1; then
  AIPERF=(uvx aiperf)
else
  echo "aiperf not found. Install it with one of:" >&2
  echo "  pip install aiperf          (in a venv)" >&2
  echo "  pipx install aiperf" >&2
  echo "  uv tool install aiperf" >&2
  exit 1
fi

STAMP=$(date +%Y%m%d-%H%M%S)
OUTDIR="results/${MODEL}-${STAMP}"
mkdir -p "$OUTDIR"

"${AIPERF[@]}" profile \
  --model "$MODEL" \
  --endpoint-type chat \
  --url "${GATEWAY_URL}" \
  --streaming \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  --synthetic-input-tokens-mean "$ISL" \
  --output-tokens-mean "$OSL" \
  --concurrency "$CONCURRENCY" \
  --request-count "$REQUESTS" \
  --artifact-dir "$OUTDIR"

echo
echo "Results in ${OUTDIR}/"
echo "Tip: rerun with CONCURRENCY=1 and CONCURRENCY=16 to see how the"
echo "backend degrades under load — that curve is what capacity planning is."
