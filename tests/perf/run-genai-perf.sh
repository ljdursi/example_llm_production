#!/usr/bin/env bash
# Performance testing with genai-perf (NVIDIA's open-source LLM load generator,
# part of the Triton perf_analyzer project).
#
#   make perf                 # test the 'coder' model through the gateway
#   make perf MODEL=general
#   CONCURRENCY=8 tests/perf/run-genai-perf.sh coder
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

STAMP=$(date +%Y%m%d-%H%M%S)
OUTDIR="results/${MODEL}-${STAMP}"
mkdir -p "$OUTDIR"

# genai-perf ships in the Triton SDK container, so no local install is needed.
# (Alternative: pip install genai-perf into a venv and drop the docker wrapper.)
docker run --rm --net host \
  -v "$(pwd)/${OUTDIR}:/artifacts" \
  -e OPENAI_API_KEY="${LITELLM_MASTER_KEY}" \
  nvcr.io/nvidia/tritonserver:25.01-py3-sdk \
  genai-perf profile \
    --model "$MODEL" \
    --endpoint-type chat \
    --url "${GATEWAY_URL}" \
    --streaming \
    --synthetic-input-tokens-mean "$ISL" \
    --output-tokens-mean "$OSL" \
    --concurrency "$CONCURRENCY" \
    --request-count "$REQUESTS" \
    --artifact-dir /artifacts

echo
echo "Results in ${OUTDIR}/ (see profile_export_genai_perf.csv)"
echo "Tip: rerun with CONCURRENCY=1 and CONCURRENCY=16 to see how the"
echo "backend degrades under load — that curve is what capacity planning is."
