# Sprint 2.6: User Profile v2 + Name Forms

Sprint 2.6 adds an editable global user profile and explicit name forms without asking the model to invent Russian declensions or nicknames.

User profile:
- `display_name`: interface label; it is not automatically used as direct address;
- `formal_name`: formal or respectful address;
- `preferred_name`: default name across characters;
- `casual_name`: retained as reserved profile data but not used by the current addressing policy;
- `vocative_name`: exact direct-address form, for example `Лёш`;
- `age`: optional integer from `1` to `120`;
- city, country, timezone, and language remain editable.

Role-based addressing:
- `colleague` and legacy `mentor` use the formal name for both ordinary and direct address.
- `friend`, `relative`, `romantic`, and `companion` use the preferred name normally.
- Those close roles use the exact direct-address form when addressing the user directly.
- If the direct-address form is blank, the preferred name is used unchanged.
- If a role's primary form is blank, the other formal/preferred form is used as a safe fallback.
- The orchestrator computes `default_name`, `direct_address_name`, and `address_policy` before prompt construction.
- The prompt receives the selected forms rather than choosing among all stored variants.
- The display name alone does not authorize direct name address.
- Blank or placeholder values never establish a user name.
- The model must not derive, decline, shorten, or invent a missing form.
- Legacy character-specific `user_nickname` values remain stored for compatibility but are no longer used for addressing.
- Existing guidance to use the user's name sparingly remains active.

Name frequency:
- A selected name is available, not required; ordinary replies should omit it.
- After the character uses either selected form, all user-name forms are suppressed for the next five assistant replies.
- Recent messages cannot override this cooldown even when they contain the user's name.
- An explicit request such as `обратись ко мне по имени` temporarily overrides the cooldown.
- Romance, high attachment, emotionality, excitement, and roleplay intensity do not increase name frequency.

Privacy:
- Every new field is optional.
- Empty fields are represented as unknown and cannot be treated as facts.
- Age is never estimated from dates, writing style, relationships, or memory fragments.
- Updating the global profile affects all characters owned by the user.

UI:
- The chat side panel contains a collapsible `User profile` editor.
- Formal, preferred, and direct-address forms are visible in the editor.
- Reserved casual-name data and the legacy per-character override are not shown.
- The profile editor explains that optional fields may be left blank.

API:
- `PATCH /users/profile` updates the owner of the supplied character.
- Age outside `1..120` is rejected.

Compatibility:
- Existing databases receive the optional profile columns through development schema sync.
- Existing user values and character-specific names remain unchanged.
- No new AI provider or external API is used.

Status: implemented locally, awaiting user verification.
