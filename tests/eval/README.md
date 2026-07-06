# Quality evaluation

Three tiers, in order of effort. Start at tier 1 today; add tier 2 the first
time you change what's behind a model name; tier 3 when you start choosing
between models.

## Tier 1: golden probes (in this directory, runs in ~a minute)

`golden.jsonl` + `test_golden.py`: a handful of prompts with checkable
answers, run with `make eval`. Their job is **regression detection**, not
benchmarking — "after I swapped the backend / upgraded the NIM / tried the
FP8-quantized variant, does `coder` still write a working function and does
`general` still answer facts?" Add probes drawn from your researchers' actual
prompts; that's the highest-value eval work you can do at any tier.

## Tier 2: standardized benchmarks

When you need a number to compare against published results (e.g. "is the
quantized 7B really close enough to the 32B for our users?"), run real
benchmarks against the same gateway endpoint:

- **[NVIDIA NeMo Evaluator](https://github.com/NVIDIA-NeMo/Evaluator)** (open
  source) — launcher + containers for many benchmark suites (MMLU, coding
  benchmarks like HumanEval/MBPP, safety suites) that evaluate any
  OpenAI-compatible endpoint, i.e. your gateway URL + a minted key. This is
  the NVIDIA-supported path.
- **[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)**
  (EleutherAI) — the community standard, same idea:
  ```bash
  lm_eval --model local-chat-completions \
      --model_args model=coder,base_url=http://localhost:4000/v1,api_key=$KEY \
      --tasks humaneval --limit 20
  ```

Point either one at the **gateway**, not the backend directly — then the eval
also exercises your auth/routing path, and its cost shows up in accounting
like any other user (mint it a dedicated key named `eval`).

## Tier 3: task-specific eval sets

Once summarization arrives: collect ~30 papers with researcher-written
summaries and score model output against them (LLM-as-judge or ROUGE — see
promptfoo or NeMo Evaluator's custom-task support). Same pattern for any new
use case: **a small eval set built from real work, versioned in this repo,
run before every backend change.**
