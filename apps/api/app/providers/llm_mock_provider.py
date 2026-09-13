from types import SimpleNamespace

from app.providers.llm_mock import generate_reply
from app.schemas.llm import CharacterReply, plain_character_reply
from app.schemas.orchestrator import OrchestratorContext


class MockLLMProvider:
    name = "mock"

    def generate_reply(self, context: OrchestratorContext) -> CharacterReply:
        character = SimpleNamespace(
            name=context.character_name,
            profile=SimpleNamespace(communication_style=context.profile.communication_style),
        )
        return plain_character_reply(
            generate_reply(character, context.current_user_message, context.recent_messages)
        )
