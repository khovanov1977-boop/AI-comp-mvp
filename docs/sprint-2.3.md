# Sprint 2.3: Memory Editing UI

Sprint 2.3 makes saved memories easier to manage during local testing.

Added:
- `PATCH /memories/{memory_id}` for updating a memory item.
- Validation for memory category and non-empty content.
- Importance clamping to the existing `1..5` range.
- Chat side panel editing for:
  - memory category;
  - memory content;
  - memory importance.
- Memory importance is shown in the UI.
- Memory summary shows how many saved memories exist and how many are visible in the current working set.
- Category counters explain why different characters can show different memory totals.

Behavior:
- Existing memory delete and manual memory creation still work.
- Automatic memory extraction is unchanged.
- The panel shows a limited working set sorted by importance and recency.
- No database migration is required.

Not included:
- Bulk memory editing.
- Memory merge UI.
- LLM-based memory review.
