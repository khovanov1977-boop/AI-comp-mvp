from typing import Protocol

from app.schemas.orchestrator import OrchestratorContext


class LLMProvider(Protocol):
    name: str

    def generate_reply(self, context: OrchestratorContext) -> str:
        """Generate an assistant reply from a structured orchestrator context."""
