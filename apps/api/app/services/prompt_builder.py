from dataclasses import dataclass

from app.schemas.orchestrator import OrchestratorContext


@dataclass(frozen=True)
class ProviderMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ProviderPrompt:
    system: str
    messages: list[ProviderMessage]


def build_provider_prompt(context: OrchestratorContext) -> ProviderPrompt:
    profile = context.profile
    state = context.state
    memory_lines = []
    for category, memories in context.memory.items():
        if not memories:
            continue
        memory_lines.append(f"{category}:")
        memory_lines.extend(f"- {memory.content}" for memory in memories)

    system_sections = [
        f"Character: {context.character_name}",
        f"Relationship mode: {context.relationship_mode}",
        "Profile:",
        f"- personality_description: {profile.personality_description}",
        f"- communication_style: {profile.communication_style}",
        f"- biography: {profile.biography}",
        f"- boundaries: {profile.boundaries}",
        f"- likes: {profile.likes}",
        f"- dislikes: {profile.dislikes}",
        f"- language: {profile.language}",
        f"- user_nickname: {profile.user_nickname}",
        "State:",
        f"- mood: {state.mood}",
        f"- trust: {state.trust}",
        f"- attachment: {state.attachment}",
        f"- energy: {state.energy}",
        "Memory:",
        *(memory_lines or ["- none"]),
    ]

    messages = [ProviderMessage(role=message.role, content=message.content) for message in context.recent_messages]
    current_message_is_last = (
        bool(messages)
        and messages[-1].role == "user"
        and messages[-1].content == context.current_user_message
    )
    if not current_message_is_last:
        messages.append(ProviderMessage(role="user", content=context.current_user_message))
    return ProviderPrompt(system="\n".join(system_sections), messages=messages)
