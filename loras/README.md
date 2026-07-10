# `loras/` — LoRA adapters for the multi-LoRA NIM

This directory is where you drop LoRA adapters for the `nim-general` service to
serve. It is mounted read-only into the NIM at `/opt/nim/loras`
(`NIM_PEFT_SOURCE`), which rescans it every 60s — so adding an adapter needs no
restart. See [docs/01-03-comparing-fine-tunes-with-lora.md](../docs/01-03-comparing-fine-tunes-with-lora.md)
for the full walkthrough.

Adapter contents are **gitignored** (they're large and reader-supplied); only
this README is tracked. The layout NIM expects — **each adapter is a
subdirectory whose name becomes the model id** you send in the OpenAI `model`
field:

```
loras/
├── README.md                       ← this file (the only tracked thing here)
└── llama31-8b-greek-dialect/       ← directory name = the adapter's model id
    ├── adapter_config.json
    └── adapter_model.safetensors   (or adapter_model.bin)
```

Populate it as in doc 01-03, step 1:

```bash
mkdir -p loras/llama31-8b-greek-dialect
huggingface-cli download Stergios/llama3.1-8b-instruct-lora \
  --local-dir loras/llama31-8b-greek-dialect
# NIM uses the BASE model's tokenizer — remove any tokenizer files the adapter ships:
rm -f loras/llama31-8b-greek-dialect/tokenizer*.json \
      loras/llama31-8b-greek-dialect/special_tokens_map.json \
      loras/llama31-8b-greek-dialect/chat_template.jinja
```

Then start the NIM with `make lora` and confirm the adapter appears at
`/v1/models` alongside the base. The adapter's `base_model_name_or_path` must
match the NIM's base (`meta-llama/Llama-3.1-8B-Instruct`), or it fails at load.
