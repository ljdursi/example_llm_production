# Phase 3: scale-out serving — Dynamo, KV-aware routing, autoscaling

This is the ambitious end of the roadmap. Nothing here should be built until
monitoring says so — which is the payoff of having built monitoring first.
The signals, in escalating order:

1. `vllm:num_requests_waiting` sustained > 0 at busy hours → you need more
   capacity for that model (a second replica, or a bigger GPU).
2. Multiple replicas running, but TTFT still poor for interactive users →
   naive load balancing is wasting your KV cache → **KV-aware routing**.
3. Load is strongly time-varying (semester rhythms, paper deadlines) and
   GPUs sit idle off-peak while queueing at peak → **autoscaling**.

## Step 1: replicas, the boring way

Before any new machinery: `kubectl scale deployment nim-coder --replicas=2`
(GPU capacity permitting). The Service round-robins across pods; the gateway
notices nothing. For many workloads this is sufficient forever. Its limits:
round-robin is oblivious to which replica already holds a conversation's KV
cache, and to prefill-vs-decode load imbalance. When those costs show up in
your TTFT numbers, read on.

## Step 2: NVIDIA Dynamo — the serving layer grows a brain

[Dynamo](https://github.com/ai-dynamo/dynamo) (open source, Apache-2.0) is
NVIDIA's datacenter-scale inference framework. Where Phase 1–2 served each
model with N identical containers, Dynamo splits serving into cooperating
pieces:

- **KV-aware routing** — the piece you asked about by name. The router tracks
  which worker holds cached KV blocks for which prefixes and sends each
  request where its prefix is already cached, instead of recomputing prefill.
  Multi-turn chat, shared long system prompts (coding assistants!), and
  repeated-document workloads (paper summarization!) are exactly the shapes
  that benefit — your two flagship use cases are the textbook cases.
- **Disaggregated prefill/decode** — prefill (compute-bound) and decode
  (memory-bound) run on separate workers, sized independently. This is what
  fixes "long paper-summarization prompts destroy TTFT for interactive coder
  users while they share hardware."
- **Multi-engine** — Dynamo orchestrates vLLM, SGLang, or TensorRT-LLM
  underneath; your engine choice from Phase 1 isn't discarded.
- **Planner/autoscaling hooks** — see below.

Where it lands in *this* architecture: Dynamo (deployed on k8s via its
operator/Helm chart) presents an OpenAI-compatible **frontend** — so to the
gateway it's just another `api_base`. The cutover is, once again, one stanza
in `gateway/litellm-config.yaml`, validated by the same three test suites,
observed in the same Grafana. The pattern you've practiced twice
(hosted → NIM → Dynamo) is the same pattern the third time. And AIPerf
concurrency sweeps are how you *prove* KV-aware routing helped: compare
TTFT-vs-concurrency curves before/after, with realistic prefix-heavy
workloads rather than pure synthetic ones.

**Community alternative:** [llm-d](https://llm-d.ai) (Red Hat/Google/CoreWeave
lineage, vLLM-based, Kubernetes-native, a CNCF Sandbox project since March
2026) targets the same problems — KV-cache-aware scheduling via the Kubernetes
Gateway API Inference Extension — and is the right thing to evaluate if you
want the CNCF-ecosystem path. The concepts
transfer one-for-one; this repo's NVIDIA path is Dynamo because that's where
our support lies.

## Step 3: autoscaling

Two distinct problems; solve them in order of appearance:

- **Gateway/UI autoscaling** — trivial: stateless Deployments + a standard
  HorizontalPodAutoscaler on CPU. Rarely needed at academic scale.
- **Model-backend autoscaling** — the hard, expensive one. GPU pods take
  minutes to become ready (weight loading), so autoscale on *leading*
  indicators from the serving layer — queue depth (`vllm:num_requests_waiting`),
  KV-cache pressure — never on GPU utilization (a lagging, often-pinned
  signal). Mechanisms, simplest first:
  1. **KEDA** (CNCF) or an HPA on custom metrics, scaling the NIM Deployment
     on Prometheus queries you already collect. The NIM Operator supports
     exactly this pattern on `NIMService` resources.
  2. **Dynamo's planner**, which plans capacity across prefill/decode pools
     jointly — the right tool once you're disaggregated.

  Sizing reality for a pilot: autoscaling *up* needs spare GPUs to scale
  into. On a fixed academic allocation, the practical win is usually
  **scale-to-zero / scale-to-few off-peak** — freeing GPUs for batch research
  work overnight — rather than elastic peak absorption. KEDA does
  scale-to-zero well; budget for the cold-start minutes in user expectations.

## The end-state picture

```
users ─▶ gateway (unchanged since Phase 0)
            ├─▶ dynamo frontend ─▶ KV-aware router ─▶ prefill workers ─┐
            │        (coder, general, summarizer)     decode workers ◀─┘  ← autoscaled
            ├─▶ small/specialty NIMs (single-replica is fine forever for some models)
            └─▶ build.nvidia.com (still a fine backend for rarely-used or huge models)
```

Note the last line: the hosted endpoints never stop being useful. A hybrid
estate — self-hosted for the hot paths, hosted for the long tail — is not a
transitional state; for an academic service it's often the steady state.
