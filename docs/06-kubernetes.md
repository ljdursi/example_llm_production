# Phase 2: Kubernetes

## When (and whether)

Compose on one box is a legitimate way to run this service for a long time.
Move when at least one of these is true:

- **More than one GPU node** — compose has no answer to "schedule this model
  onto whichever box has free GPUs"; k8s does.
- **You want the platform handling restarts, node failures, and rolling
  upgrades** instead of SSH-and-restart.
- **Autoscaling is on the horizon** — it's k8s-native machinery
  ([07-scaling-out.md](07-scaling-out.md) needs this phase first).
- **Institutional convergence** — if your organization is building k8s
  operational muscle anyway, this service is a good tenant.

The `k8s/` tree exists *now*, mirrored service-for-service with compose, so
the team can study the mapping before committing —
[k8s/README.md](../k8s/README.md) has the translation table and deploy
commands. The important structural fact: `k8s/base/kustomization.yaml` mounts
**the same `gateway/litellm-config.yaml`** as compose. Model routing has one
source of truth on both tracks; a migration can run both in parallel against
the same upstream config while you cut DNS over.

## Cluster prerequisites for the GPU parts

1. **A cluster.** For a small dedicated pilot (1–3 nodes), lightweight
   distributions like k3s are entirely adequate and dramatically easier to
   operate than kubeadm-from-scratch; a slice of an institutional cluster is
   even better because someone else patches the control plane.
2. **[NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/)**
   (Helm install) — manages drivers, container toolkit, and device plugin so
   pods can request `nvidia.com/gpu`; also deploys dcgm-exporter for
   monitoring. This replaces everything you did by hand on the compose GPU box.
3. **Secrets + registry access** — the four `kubectl create secret` commands
   in [k8s/README.md](../k8s/README.md).

Then `kubectl apply -k k8s/base/` (gateway+db) and `kubectl apply -k k8s/nim/`
(the NIM). Update `api_base` in the gateway config to the in-cluster Service
name (`http://nim-coder.llm-service:8000/v1`), expose the gateway via your
standard Ingress, and **rerun `make smoke` / `make perf` / `make eval`
pointed at the new URL** — the suites are the acceptance test for this
migration exactly as they were for Phase 1.

## Long-hand first, then operators

`k8s/nim/nim-coder.yaml` deploys a NIM the verbose way — Deployment, PVC for
the weight cache, Service, probes — because you should see all the moving
parts once. After that, adopt the
**[NVIDIA NIM Operator](https://github.com/NVIDIA/k8s-nim-operator)**: each
model becomes a ~15-line `NIMService` custom resource, and the operator owns
weight-cache management, rollouts, and (later) autoscaling integration. When
"add a summarization model" means *one small CR + one gateway stanza*, you've
reached the operating posture this repo was aiming you at.

For non-NIM backends, the same maturity path exists in the community: vLLM's
Helm charts, or (CNCF-adjacent) [llm-d](https://llm-d.ai) and
[KServe](https://kserve.github.io/website/) for a general model-serving
control plane — heavier, but the standard if your institution builds a shared
ML platform beyond LLMs.

## What deliberately stays the same

The gateway remains one Deployment in front of everything (bump `replicas`
for availability — it's stateless); Postgres remains boring (or better,
becomes your institution's managed Postgres); users still see one URL, and
their keys survive untouched because they live in the database, not the
deployment. Kubernetes changed *where things run*, not *what the service is* —
if users noticed the migration, something went wrong.
