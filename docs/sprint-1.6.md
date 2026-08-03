# Sprint 1.6: Persona Prompt Contract v2

Sprint 1.6 improves companion realism by strengthening the prompt contract sent to real LLM providers.

Added:
- Character gender in orchestrator context.
- Explicit identity rules for character name, user name, relationship mode, language, and gender.
- Speech rules that tell the model to speak only as the character in first person.
- Rules against confusing character and user names.
- Rules against third-person stage directions about the character.
- Rules against mechanically repeating the user's message.
- Rules for concise replies, lower filler, and more initiative.
- A rule that the model must not pretend to browse the internet or verify live schedules unless tool results are provided.

This sprint does not add web browsing, tool calling, Alembic, or new real provider logic.

Expected effect:
- Fewer gender/name mixups.
- Less profile dumping.
- Less repetitive wording.
- More natural Russian-language companion replies.
- Better separation between current MVP capabilities and future web tools.
