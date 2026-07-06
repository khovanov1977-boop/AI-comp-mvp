# Sprint 1.5: OpenAI-Compatible Real LLM Provider

Sprint 1.5 adds backend support for a real LLM through an OpenAI-compatible chat completions API.

Added:
- `LLM_PROVIDER=openai_compatible`.
- OpenAI-compatible provider calls `POST {LLM_BASE_URL}/chat/completions`.
- Provider config for base URL, API key, model, timeout, temperature, and max tokens.
- Clean errors for missing config, timeout, non-200 responses, malformed responses, and empty content.
- Tests that use mocked HTTP calls only.

How it works:
- The chat orchestrator still builds structured orchestrator context.
- The existing prompt builder converts context into provider-ready messages.
- The OpenAI-compatible provider sends those messages to the configured endpoint.
- Prompt construction is not duplicated inside the provider.

The model is not hardcoded because the MVP should support self-hosted, open, or minimally filtered OpenAI-compatible model runtimes.

Mock config:

```env
LLM_PROVIDER=mock
```

Local Ollama / OpenAI-compatible example:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=huihui_ai/gemma-4-abliterated:12b
LLM_API_KEY=ollama
```

Cloud GPU endpoint example:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-endpoint.example.com/v1
LLM_MODEL=huihui_ai/gemma-4-abliterated:12b
LLM_API_KEY=your_key
```

The target model for a later manual test is `huihui_ai/gemma-4-abliterated:12b`.

Real model runtime setup, GPU hosting, Ollama installation, and model download are outside Sprint 1.5.
