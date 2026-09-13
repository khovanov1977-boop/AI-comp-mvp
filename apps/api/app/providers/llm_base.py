from typing import Protocol

from app.schemas.orchestrator import OrchestratorContext
from app.schemas.llm import CharacterReply


class LLMProvider(Protocol):
    name: str

    def generate_reply(self, context: OrchestratorContext) -> CharacterReply:
        """Generate an assistant reply from a structured orchestrator context."""
