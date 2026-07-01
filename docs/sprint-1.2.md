# Sprint 1.2: Orchestrator Context + Prompt Contract

Sprint 1.2 prepares the backend contract for future real LLM integration.

Implemented:

- A structured orchestrator context builder for chat replies.
- A typed Pydantic context contract containing character profile, state, grouped memory, recent messages, and the current user message.
- A dev endpoint for inspecting the generated context:

```text
POST /debug/orchestrator-context
```

This endpoint does not call any AI provider.

Real AI APIs are still not connected. The existing mock LLM provider remains in place.
