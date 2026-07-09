# Phase 1: swapping a placeholder for a self-hosted NIM

The hosted endpoints at build.nvidia.com **are NIM containers run by NVIDIA**.
Self-hosting means running the same container on your hardware — same model,
same API, same metrics. That's why this phase is an operations change, not a
behavior change, and why everything you built in Phase 0 (tests, accounting,
UI, client configs) carries over untouched.

## 0. Prerequisites

- A GPU box with the NVIDIA driver and
  [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  (`docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi` should work).
- An NGC key in `.env` (`NGC_API_KEY`), and
  `docker login nvcr.io -u '$oauthtoken' -p $NGC_API_KEY`.
- **Sizing:** check the model card's support matrix at build.nvidia.com /
  NGC for GPU + VRAM requirements per precision. Rule of thumb: weights alone
  need ~2 bytes/parameter at FP16, ~1 at FP8 — a 32B coder model wants ≥2×
  A100/H100-class GPUs at FP16, or one 80GB GPU with an FP8 profile. **If your
  pilot hardware is smaller, self-host a smaller model** (e.g. a 7B coder) —
  proving the *operational pattern* is the point of Phase 1, not matching the
  hosted model's quality on day one.

## 1. Capture the "before" picture

```bash
make perf MODEL=coder && make eval && make smoke
```

You are about to change what's behind `coder`. These runs are the acceptance
criteria for the swap.

## 2. Start the NIM (no traffic to it yet)

```bash
make selfhost      # = docker compose -f docker-compose.yaml -f docker-compose.selfhost.yaml up -d
docker compose logs -f nim-coder
```

First boot downloads weights (tens of GB) and may build an optimized engine
for your exact GPU — this can take tens of minutes and is cached in a volume;
subsequent boots take minutes. Ready when
`curl http://localhost:8000/v1/health/ready` returns 200.

Talk to it *directly* first — worth doing once to see there's no magic:

```bash
curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model": "qwen/qwen2.5-coder-32b-instruct", "messages": [{"role":"user","content":"hello"}]}'
curl -s http://localhost:8000/metrics | head    # Prometheus metrics, free of charge
```

Note it required no API key: **the NIM itself does no auth**. It must only
ever be reachable by the gateway and monitoring — on this compose network
that's true by default (the `:8000` host port is exposed for your testing;
firewall it or drop the `ports:` stanza once satisfied). The gateway remains
the sole front door.

## 3. Cut over routing

In `gateway/litellm-config.yaml`, the `coder` stanza's `litellm_params` become
(the file has this as a template):

```yaml
      model: openai/qwen/qwen2.5-coder-32b-instruct
      api_base: http://nim-coder:8000/v1
      api_key: none
```

Then `docker compose restart gateway`. For a cautious cutover, instead *add*
this as a second `coder` stanza — the gateway load-balances across both, you
watch the self-hosted one take traffic, then remove the hosted stanza.

## 4. Verify — this is the payoff for building tests in Phase 0

```bash
make smoke                 # wiring: identical tests, new backend
make eval                  # quality: does 'coder' still write working code?
make perf MODEL=coder      # compare to step 1: TTFT likely improves (no WAN);
                           # throughput now reflects YOUR GPUs, and concurrency
                           # sweeps now mean something — this is your capacity
```

Wire up monitoring while the perf run is generating load: the NIM's `/metrics`
is already listed in `monitoring/prometheus/prometheus.yml`, and the Grafana
overview dashboard should show queue depth, TTFT, and (with dcgm-exporter
running) GPU utilization moving. Details: [06-monitoring.md](06-monitoring.md).

Users noticed nothing. Their key, URL, and model name are unchanged.

## Variations on the pattern

- **Different/smaller model**: same recipe, different image tag + model id.
- **A vLLM or SGLang backend instead of NIM**: also OpenAI-compatible — the
  gateway stanza looks identical (`api_base` pointing at it). NIM buys you
  pre-optimized engines, a support path, and uniform packaging across model
  families; vLLM buys you bleeding-edge models and community breadth. The
  architecture is agnostic — you can even run one of each and A/B them behind
  one model name.
- **Multi-modal later**: vision NIMs speak the same chat API (image content
  parts in messages) — another stanza, another container, no new architecture.

When one box / one replica stops being enough:
[07-kubernetes.md](07-kubernetes.md), then [08-scaling-out.md](08-scaling-out.md).

---

**◀ Prev** [03 · Guardrails](03-guardrails.md) · **[Up](../README.md)** · **Next ▶** [05 · Testing](05-testing-performance-and-quality.md)
