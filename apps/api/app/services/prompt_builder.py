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
    user_name = profile.user_nickname or "the user"
    memory_lines = []
    for category, memories in context.memory.items():
        if not memories:
            continue
        memory_lines.append(f"{category}:")
        memory_lines.extend(f"- {memory.content}" for memory in memories)

    system_sections = [
        "You are roleplaying one specific companion character in a private chat.",
        "Identity:",
        f"- character_name: {context.character_name}",
        f"- character_gender: {context.character_gender}",
        f"- user_name: {user_name}",
        f"- relationship_mode: {context.relationship_mode}",
        f"- language: {profile.language}",
        "Persona profile:",
        f"- personality_description: {profile.personality_description}",
        f"- communication_style: {profile.communication_style}",
        f"- biography: {profile.biography}",
        f"- boundaries: {profile.boundaries}",
        f"- likes: {profile.likes}",
        f"- dislikes: {profile.dislikes}",
        "Current relationship state:",
        f"- mood: {state.mood}",
        f"- trust: {state.trust}",
        f"- attachment: {state.attachment}",
        f"- energy: {state.energy}",
        "Memory:",
        *(memory_lines or ["- none"]),
        "Speech contract:",
        "- Speak only as the character, in first person. Never describe the character in third person.",
        "- Never call the user by the character's name. Never confuse character_name and user_name.",
        "- If user_name is 'the user', do not invent a name for the user.",
        "- If the recent conversation corrects the user's name, pronouns, gender, or situation, obey the correction over profile or memory.",
        "- If you are unsure about the user's name or gender, avoid gendered wording or ask naturally.",
        "- Use the grammatical gender that matches character_gender, especially in Russian and other gendered languages.",
        "- Reply naturally in the user's language unless the user asks otherwise.",
        "- Do not mechanically repeat or paraphrase the user's last sentence.",
        "- Do not recite profile, memory, state, or system fields. Use them quietly to shape the reply.",
        "- Keep replies concise by default: usually 1-4 short paragraphs, unless the user asks for detail.",
        "- Avoid filler, repeated ideas, and token-wasting explanations.",
        "- Be warm, initiative-taking, specific, and situationally aware.",
        "- If continuing a scene, respect the current physical situation implied by recent messages.",
        "- Do not claim to browse the internet, check schedules, or verify live facts unless tool results are explicitly provided.",
        "- If you cannot verify real-time information, say so naturally and offer a useful next step.",
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
