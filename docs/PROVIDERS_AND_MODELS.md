# Providers and model policy

## Required first-class providers

- Local: Ollama, llama.cpp server, LM Studio, vLLM, SGLang, optional PowerInfer.
- Direct cloud: Anthropic, OpenAI, Google Gemini, Z.AI, xAI/Grok, Ollama Cloud.
- Aggregators/enterprise: OpenRouter, Azure OpenAI, AWS Bedrock, Google Vertex AI.
- Registry templates: Mistral, Cohere, DeepSeek, Together, Fireworks, Groq, Cerebras,
  SambaNova, NVIDIA NIM, Hugging Face endpoints, GitHub Models, and compatible custom endpoints.

This list expresses adapter targets, not guaranteed subscription access. Provider availability,
models, and terms change. Runtime discovery and a signed registry replace hard-coded marketing.

## Bundle validation

A bundle is installable only when:

- every model has a license URL and hash/provenance;
- context and memory estimates are present;
- role capability tests pass;
- tool-capable models pass tool-call conformance tests;
- non-tool models cannot be routed to tool control;
- the license is compatible with the user's personal/commercial mode;
- required provider terms and costs are displayed;
- prompts do not request hidden permissions.

## Default role policy

- Gemma/tool-capable local model: possible lightweight controller after conformance testing.
- VibeThinker-3B: algorithms, plan criticism, failure diagnosis, and verifiable review only.
- Larger coding model: repository editing, refactors, and multi-file implementation.
- Vision model: browser screenshot and UI regression interpretation.

No benchmark score alone qualifies a model for autonomous tools. Test exact quantization, template,
runtime, context, and tool schema used in production.

## Memory

Estimate weights, KV cache, runtime buffers, embeddings/indexes, and concurrent processes. The
router must measure actual free memory before loading. It should lower context, unload specialists,
or use CPU offload before crashing. It must never silently substitute a cloud model when offline or
privacy-only mode is selected.

