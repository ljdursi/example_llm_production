# Performance testing

`run-perf.sh` drives synthetic load through the gateway with
[AIPerf](https://github.com/ai-dynamo/aiperf) (NVIDIA open source, `pip
install aiperf`; the successor to genai-perf with the same CLI shape) and
reports the four numbers that define how an LLM service *feels*:

| Metric | What it is | What users experience |
|---|---|---|
| **TTFT** (time to first token) | Delay before the first token streams back | "Is it thinking or is it broken?" — the latency users notice most |
| **Inter-token latency** | Gap between subsequent tokens | Reading speed of the stream; >~50ms starts to feel sluggish |
| **Request latency** | Full round trip | Matters for non-streaming API use (scripts, batch jobs) |
| **Output tokens/sec** | Aggregate generation throughput | Capacity: how many concurrent users one backend can carry |

## The discipline that matters more than any single number

1. **Baseline everything.** Run `make perf` today against the hosted endpoints
   and commit the CSV. Numbers with nothing to compare to are trivia.
2. **Test before and after every backend change.** Swapping to a self-hosted
   NIM? Baseline the hosted endpoint, swap, rerun with identical parameters,
   diff. This is the acceptance test for Phase 1.
3. **Sweep concurrency.** `CONCURRENCY=1` measures the best case;
   `CONCURRENCY=16` measures the queue. The shape of TTFT-vs-concurrency tells
   you when you need a second GPU (or Phase 3) long before users complain.
4. **Match your workload.** `ISL`/`OSL` default to 512/256; a paper-summarizer
   is more like `ISL=8000 OSL=500`, and long inputs stress a very different
   part of the serving stack (prefill → TTFT) than long outputs (decode →
   tokens/sec). Test what your researchers will actually send.

## Tokenizer (why `make perf` needs one, and the `TOKENIZER` knob)

AIPerf builds synthetic prompts and counts tokens client-side, so it needs a
tokenizer. Left to itself it resolves `--model` as a HuggingFace repo id — but
our `--model` is a gateway *alias* (`coder`, `general`), opaque by design and
never a valid HF id, so AIPerf aborts with an ambiguous/unknown-tokenizer
error. `run-perf.sh` therefore passes `--tokenizer` explicitly, defaulting to
`gpt2` (small, ungated, works anywhere). Override it to match the model
actually behind the name for accurate input-token counts:

```bash
TOKENIZER=Qwen/Qwen2.5-Coder-32B-Instruct make perf MODEL=coder
```

The counts are approximate across tokenizer families, which is fine here —
these runs exist to be diffed against each other with identical settings, and
the gateway/backend report the authoritative token counts in `/spend` anyway.

Two caveats when testing *hosted* build.nvidia.com endpoints: you're measuring
their shared, rate-limited service plus WAN latency (fine as a functional
baseline, not a capacity statement), and be a good citizen with request counts.
Against your own NIM, watch the Grafana overview dashboard while the test runs
— seeing queue depth and GPU utilization move under load is the fastest way to
build serving intuition.

**Alternatives:** AIPerf is LLM-aware (it understands tokens and streaming).
Generic load tools — k6, Locust (both widely used; k6 is CNCF) — work too but
you'd reimplement token timing yourself; vLLM's `benchmark_serving.py` is
another solid community option. (If you find older guides using **genai-perf**:
same tool lineage, now deprecated in favor of AIPerf — the flags mostly
transfer.)
