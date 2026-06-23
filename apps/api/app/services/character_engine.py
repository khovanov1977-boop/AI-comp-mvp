from app.models.character import Character, CharacterState


def update_state_after_message(character: Character) -> CharacterState:
    state = character.state
    state.mood = "attentive"
    state.trust_level = min(state.trust_level + 1, 100)
    state.attachment_level = min(state.attachment_level + 1, 100)
    state.energy_level = max(state.energy_level - 1, 0)
    return state
