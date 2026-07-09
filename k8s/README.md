# Kubernetes track

The **same stack as `docker-compose.yaml`, translated piece by piece** into
Kubernetes manifests. Every compose service has a counterpart here, so you can
learn the mapping by diffing:

| compose service | here | translation notes |
|---|---|---|
| `gateway` | `base/litellm/` | config file → ConfigMap; `.env` secrets → Secret; port → Service |
| `db` | `base/postgres/` | volume → PersistentVolumeClaim via StatefulSet |
| `webui` | (add the same way as gateway; left as the first exercise) | |
| `nim-coder` (selfhost overlay) | `nim/` | `--gpus` → `resources.limits."nvidia.com/gpu"`; needs the [NVIDIA GPU Operator](https://github.com/NVIDIA/gpu-operator) on the cluster |
| prometheus scrape config | `monitoring/servicemonitor.yaml` | static targets → ServiceMonitor discovered by your Prometheus Operator |

## Deploy

```bash
# secrets first (mirror of .env — never committed):
kubectl create namespace llm-service
kubectl -n llm-service create secret generic llm-secrets \
  --from-literal=NVIDIA_API_KEY=nvapi-... \
  --from-literal=LITELLM_MASTER_KEY=sk-... \
  --from-literal=POSTGRES_PASSWORD=...

# the gateway config — the SAME file compose uses (rerun this to change routing):
kubectl -n llm-service create configmap litellm-config \
  --from-file=config.yaml=../gateway/litellm-config.yaml \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k base/          # gateway + postgres
kubectl apply -k nim/           # self-hosted NIM (needs GPU nodes + GPU Operator)
```

Expose the gateway with whatever your institution already uses (Ingress +
cert-manager, or a LoadBalancer Service). The gateway is the **only** thing
that needs external exposure; model backends stay cluster-internal.

## When to actually move here

Compose is fine for one box. Kubernetes earns its complexity when you have
**more than one GPU node**, want **restarts/scheduling/upgrades handled for
you**, or want **autoscaling** (which is k8s-native — see
`docs/03-01-scaling-out.md`). Don't move before one of those is true; do read
this directory before then so the move is a translation, not a rewrite.

Operational notes, GPU Operator setup, NIM Operator (which replaces `nim/` with
a one-screen custom resource), and Helm alternatives: `docs/02-01-kubernetes.md`.
