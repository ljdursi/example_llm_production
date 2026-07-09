# Comparing fine-tunes: a LoRA adapter as the candidate

[07-evaluating-and-replacing-a-model.md](07-evaluating-and-replacing-a-model.md)
is the general procedure — evaluate a candidate under a new name, decide against
a bar you set in advance, migrate with a canary. This page is that procedure
made **concrete**, with the candidate that comes up most often on an academic
service: not a different vendor model, but a **LoRA fine-tune of a model you
already serve**, handed to you by a researcher who asks "is mine better for my
task?"

It's the cheapest possible candidate to stand up. A LoRA adapter is a few
hundred MB of low-rank deltas over frozen base weights; NVIDIA NIM serves
**many adapters over one base deployment**, so evaluating a fine-tune costs you
a file copy and a config stanza — **not** a second model's worth of GPU. The
same GPUs, the same base weights, one extra name at the gateway.

> **This is Phase 1+ — it needs a GPU.** Unlike doc 07's no-GPU hosted-vs-hosted
> comparison, you can't upload your own adapter to build.nvidia.com. You need a
> self-hosted NIM (doc 04) whose base model is one the adapter was trained on.
> The worked example below runs on a **single ~24 GB GPU** (Llama-3.1-8B).

## Why the gateway makes this almost free

The insight that makes this a two-line change: **NIM selects a LoRA adapter by
the `model` field of an ordinary OpenAI request** — you send the adapter's name
where you'd normally send a model id. That is *exactly* how LiteLLM already
addresses backends. So a base-vs-fine-tune comparison is just two `model_list`
stanzas pointing at the **same `api_base`**, differing only in the model string:

```yaml
  # the base model you already serve — no adapter
  - model_name: general
    litellm_params:
      model: openai/meta/llama-3.1-8b-instruct   # the id the NIM lists at /v1/models
      api_base: http://nim-general:8000/v1
      api_key: none

  # the candidate: SAME base weights + a LoRA adapter, under a NEW name
  - model_name: general-lora                      # temporary; drop after cutover
    litellm_params:
      model: openai/llama31-8b-greek-dialect       # = the adapter's directory name
      api_base: http://nim-general:8000/v1         # same NIM, same GPUs
      api_key: none
```

Users on `general` are untouched while you evaluate `general-lora` — the doc 07
pattern, now costing one adapter directory instead of a whole second model.

## 1. Get an adapter and lay it out the way NIM expects

The worked example uses a real, openly-licensed research fine-tune:
[`Stergios/llama3.1-8b-instruct-lora`](https://huggingface.co/Stergios/llama3.1-8b-instruct-lora),
a Greek-**dialect** adapter (Pontic, Cretan, Cypriot, …) over
`meta-llama/Llama-3.1-8B-Instruct`, from the University of Crete CLLT Lab. It's
a good teaching case because base and fine-tune **visibly differ**: the base
answers a Greek prompt in Standard Greek; the adapter produces dialect. A
difference you can see is a difference you can eval.

NIM discovers adapters from a directory tree where **each adapter is a
subdirectory whose name becomes the adapter's model id**:

```
loras/
└── llama31-8b-greek-dialect/     ← this directory name is what you put in `model`
    ├── adapter_config.json
    └── adapter_model.safetensors
```

```bash
mkdir -p loras/llama31-8b-greek-dialect
huggingface-cli download Stergios/llama3.1-8b-instruct-lora \
  --local-dir loras/llama31-8b-greek-dialect

# NIM's docs say to EXCLUDE tokenizer files from HF adapters — the base NIM's
# tokenizer is authoritative, and a stray adapter tokenizer causes conflicts.
# This repo (like many HF adapters) ships them, so remove them:
rm -f loras/llama31-8b-greek-dialect/tokenizer*.json \
      loras/llama31-8b-greek-dialect/special_tokens_map.json \
      loras/llama31-8b-greek-dialect/chat_template.jinja
```

**What NIM needs from a HuggingFace-format adapter** (check the candidate before
you trust it — a bad `adapter_config.json` fails at load with the unhelpful
`Exception: lora format could not be determined`):

| Field | Required value | This adapter |
|---|---|---|
| files | `adapter_config.json` + `adapter_model.safetensors` (or `.bin`) | ✓ |
| `base_model_name_or_path` | the base your NIM serves | `meta-llama/Llama-3.1-8B-Instruct` ✓ |
| `target_modules` | subset of `{q,k,v,o,gate,up,down}_proj` | all seven ✓ |
| `modules_to_save` | `null` — adapters that also save `lm_head`/`embed_tokens` aren't supported | `null` ✓ |
| `r` (rank) | ≤ `NIM_MAX_LORA_RANK` (default covers 16/32) | `16` ✓ |

## 2. Serve the base with LoRA enabled

Point a self-hosted NIM at the **Llama-3.1-8B base** (not the qwen coder NIM
from doc 04 — the adapter's base must match) and turn on PEFT. There's a
commented `nim-general` service in
[`docker-compose.selfhost.yaml`](../docker-compose.selfhost.yaml) with exactly
this wiring; the two lines that matter:

```yaml
    environment:
      NGC_API_KEY: ${NGC_API_KEY}
      NIM_PEFT_SOURCE: /opt/nim/loras     # directory of adapter subdirs (below)
      NIM_PEFT_REFRESH_INTERVAL: "60"     # rescan every 60s → drop in adapters
                                          # without restarting the NIM
    volumes:
      - ./loras:/opt/nim/loras            # your loras/ tree from step 1
```

`NIM_PEFT_REFRESH_INTERVAL` is the quiet luxury here: adding tomorrow's
candidate is `cp -r` into `loras/`, no restart, no downtime for `general`.

Bring it up and confirm the adapter is registered — it appears at `/v1/models`
**alongside** the base, as a peer model id:

```bash
docker compose -f docker-compose.yaml -f docker-compose.selfhost.yaml up -d nim-general
curl -s http://localhost:8000/v1/models | python3 -m json.tool
#   → "meta/llama-3.1-8b-instruct"   (base)
#   → "llama31-8b-greek-dialect"     (adapter — selectable by name)
```

Add the two gateway stanzas from the top of this page to
`gateway/litellm-config.yaml`, then `docker compose restart gateway`. Now
`general` and `general-lora` are both live behind the one NIM.

## 3. Compare — same suites, two names

**See the delta first.** One prompt, both names, side by side — this is the
"is there even a difference?" gut check before you spend effort scoring it:

```bash
for M in general general-lora; do
  echo "── $M ──"
  curl -s http://localhost:4000/v1/chat/completions \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$M\",\"messages\":[{\"role\":\"user\",
         \"content\":\"Απάντησε στην ποντιακή διάλεκτο: πώς είσαι σήμερα;\"}]}" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['choices'][0]['message']['content'])"
done
```

**Then score it like any candidate.** Everything doc 07 says about scoring
applies unchanged — the point of the shared eval harness is that the candidate's
*nature* (LoRA vs different model) doesn't change the procedure:

- **The regression floor.** `tests/eval/golden.jsonl` parametrizes probes **by
  model name**, so comparing the two costs zero code — just add rows with
  `"model": "general-lora"`. The highest-value probes here test what the
  adapter should *not* have broken. Fine-tuning is a capability trade: a dialect
  adapter can regress on general knowledge or code. Catch it:

  ```json
  {"model": "general",      "prompt": "What is the boiling point of water at sea level in Celsius?", "must_contain": ["100"]}
  {"model": "general-lora", "prompt": "What is the boiling point of water at sea level in Celsius?", "must_contain": ["100"]}
  ```

  If the second row fails, the fine-tune bought dialect fluency at the cost of
  facts — a real result, surfaced before any user hits it.

- **The head-to-head on the target task.** Dialect quality has no golden string;
  use **LLM-as-judge** (NeMo Evaluator, or promptfoo's side-by-side) exactly as
  doc 07 describes — "does `general-lora` answer in convincing Pontic more often
  than `general`?" Point either at the gateway, at each name in turn.

- **Performance.** `make perf MODEL=general` vs `make perf MODEL=general-lora`.
  Expect a **small** per-token cost from the adapter's extra GEMMs; NIM batches
  heterogeneous adapters into fused kernels, so it's usually minor, but it's a
  number you should have, not assume — see
  [05-testing-performance-and-quality.md](05-testing-performance-and-quality.md).

- **Cost** is the one axis that's *identical* — same base, same GPUs, same
  per-token price. That asymmetry is often the whole argument for a fine-tune
  over a bigger model: task-specific quality at the base model's cost.

## 4. Decide and migrate — back to doc 07

From here nothing is LoRA-specific. Write the acceptance bar down first, then run
([the decision gate](07-evaluating-and-replacing-a-model.md#the-decision-gate)).
If the adapter clears it, migrate with the same canary → watch → cut over →
keep-a-rollback steps from
[doc 07, Act 2](07-evaluating-and-replacing-a-model.md) — give `general` a second
stanza pointing at the adapter, watch the `requested_model` split in Grafana,
then retire `general-lora`. The cutover is a config edit and a restart; the
adapter file stays on disk, so rollback is a stanza away.

And the doc 07 courtesy to users applies with a LoRA twist: a fine-tune can shift
*behavior* subtly (tone, format, a domain lean) even when aggregate quality
holds. If researchers depend on the old behavior, a one-line changelog entry is
cheap trust insurance.

## Caveats worth knowing before you rely on this

- **Base must match the adapter.** The NIM's base model has to be the one the
  adapter was trained on. Mixed dims fail at load. (This is why the example uses
  a dedicated `nim-general` Llama-3.1-8B NIM, not doc 04's qwen coder.)
- **Multi-LoRA is model-specific.** NIM supports it for a set of bases —
  Llama-3-8B/70B and Llama-3.1-8B among them; check the model's NIM docs before
  assuming. It is **not** the same list as "models that have a NIM."
- **Backend/GPU gotcha.** On some GPU + backend combinations LoRA isn't
  supported (e.g. Llama-3.1-8B LoRA on an L40S under the TRT-LLM backend). If
  the base loads but adapters won't, check the NIM's support matrix / try the
  vLLM backend before assuming a bad adapter.
- **Rank budget.** NIM pre-allocates GPU cache to `NIM_MAX_LORA_RANK`; raising
  it to host a high-rank adapter costs memory for *every* slot. Most adapters
  are rank 8–32.
- **Licensing.** The base (Llama) is license-gated on both NGC and HuggingFace,
  and each adapter carries its own license — check both before serving to users.

---

**◀ Prev** [07 · Replacing a model](07-evaluating-and-replacing-a-model.md) · **[Up](../README.md)** · **Next ▶** [08 · Kubernetes](08-kubernetes.md)
