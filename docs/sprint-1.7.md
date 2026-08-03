# Sprint 1.7: Chat UX Realism + Reliability

Sprint 1.7 improves the chat experience when using real LLM providers.

Added:
- Typing indicator while the assistant response is pending.
- A short reveal delay based on reply length so long answers do not appear instantly.
- User-friendly provider error messages.
- Retry button for failed provider calls.
- Backend retry endpoint: `POST /chat/retry`.

Reliability behavior:
- The original user message is saved before the LLM provider call.
- Retry reuses the last failed user message and does not create a duplicate user message.
- Provider errors are returned as structured API errors instead of unhandled backend failures.

This sprint does not add web browsing, tool calling, Alembic, or new LLM providers.
