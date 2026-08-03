# Sprint 1.8: Time + User Context

Sprint 1.8 adds user-local context to the companion foundation.

Added:
- User city, country, inferred timezone, and language fields.
- User context fields in character creation and character API responses.
- User context in the chat side panel.
- Structured orchestrator user context with current local date, time, and weekday.
- Time-of-day and daylight context for realistic situational replies.
- A small backend timezone resolver for common MVP test cities, with fallback behavior.
- Prompt contract rules that treat the user's local date/time as the shared reality.
- Prompt contract rules that prevent the model from adding the timezone offset twice.
- Prompt contract rules that require exact server-computed local time instead of estimating or shifting it.
- Prompt contract rules that prevent unrealistic time-based suggestions, such as sunset plans late at night.
- Prompt contract rules that assume the character shares the user's city/timezone unless a different location is explicitly established.

Behavior:
- Existing characters continue to work with default user context values.
- The backend uses `Europe/Moscow` as the default timezone for local MVP testing.
- If a timezone cannot be resolved, the backend falls back to UTC instead of failing.
- The UI does not ask users to type an IANA timezone manually.

Not included:
- Separate user settings screen.
- Character-specific city/timezone settings.
- Scene/place awareness.
- Web browsing or live internet tools.
