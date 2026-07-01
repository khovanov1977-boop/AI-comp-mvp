# Sprint 1.4: LLM Provider Interface + Prompt Builder

Sprint 1.4 prepares the backend architecture for future real LLM integration.

Added:
- A unified LLM provider interface that accepts structured orchestrator context.
- A mock provider adapter that keeps the existing mock reply behavior.
- A deterministic prompt/messages builder for provider-ready input.
- Provider selection through `LLM_PROVIDER`, defaulting to `mock`.

Provider selection:
- Set `LLM_PROVIDER=mock` in `.env`.
- If the value is missing, the backend defaults to `mock`.
- Unsupported provider names raise a backend configuration error.

Real AI APIs are still not connected. No OpenAI, Anthropic, OpenRouter, or other real provider client was added.

Prepared for Sprint 1.5:
- A real provider can implement the same interface.
- The existing orchestrator context can be converted into provider messages through the prompt builder.
- The chat orchestrator no longer needs provider-specific logic.
