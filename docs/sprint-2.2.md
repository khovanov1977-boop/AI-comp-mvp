# Sprint 2.2: Memory Quality v2

Sprint 2.2 improves automatic memory quality without adding a real AI memory classifier or database migrations.

Added:
- More conservative memory storage for questions.
- Normalized user name facts, such as `имя пользователя Алексей`.
- Better location fact extraction for:
  - birthplace;
  - current or past residence;
  - residence with an age boundary, such as `до 17 лет`.
- Durable identity facts receive higher importance.
- Existing identity facts are updated instead of duplicated for:
  - user name;
  - birth date;
  - birthplace;
  - residence.

Behavior:
- User messages are still saved exactly as written in chat history.
- Memory summaries can be more compact than the original message.
- Old database records are not normalized automatically.

Not included:
- LLM-based memory extraction.
- Full user profile model.
- Alembic migrations.
- Frontend changes.

