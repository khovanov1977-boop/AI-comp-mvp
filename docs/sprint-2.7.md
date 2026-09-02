# Sprint 2.7: Response Length + Style Control

Status: completed and pushed.

## Goal

Let the character choose a natural response length from the current conversation without increasing the provider output ceiling or cutting generated text after the fact.

## Context-adaptive length

- Greetings, acknowledgements, simple questions, and routine dialogue are usually 1-3 sentences and about 10-60 words.
- Emotional support and shared scenes can use 2-5 sentences and up to about 120 words when the feeling or action needs acknowledgement.
- Explanations, advice, and story questions can use 3-7 sentences and up to about 180 words when the detail adds value.
- Explicit requests for a long story receive a complete installment of about 120-180 words with a natural stopping point.
- These are contextual guidelines, not user-selected modes or quotas.

## Conversational intent

- A social check-in such as `как ты?`, `как дела?`, or `ты в порядке?` receives a direct answer in one sentence or at most two.
- The character does not pad a check-in with routine events, scenery, biography, or several new topics.
- An introspective question such as `что ты чувствуешь?`, `что у тебя внутри?`, or `расскажи о своих чувствах` receives a more open answer in about 3-6 sentences.
- Introspection names specific feelings and their current cause from character state, scene, and recent conversation without exposing state labels or numbers.
- The distinction between check-in and introspection takes priority over high emotionality, relationship closeness, or scene intensity.

## Prompt behavior

- The model chooses length from the user's intent, emotional weight, and the amount of useful information needed.
- Simple turns stay short even when personality emotionality, relationship closeness, or dramatic atmosphere is high.
- Long stories are returned as complete installments with natural stopping points.
- Every response must finish on a complete sentence.
- Personality, emotionality, and roleplay intensity do not override the length rules.

## Technical limits

- The provider `max_tokens` setting remains 500.
- Replies are guided before generation; no text is cut after generation.
- No response-length setting is stored on the character.

## UX decision

- There is no manual response-length control in character creation or settings.
- Natural conversational behavior remains the character's responsibility rather than a user-managed parameter.
