# Changelog v9

- Adds Seattle Theatre Group venue feeds:
  - `paramount`
  - `neptune`
  - `moore`
- Uses each venue's first-party STG events page.
- Emits one normalized event per occurrence/performance, including repeated productions.
- Routes by exact physical venue/address.
- Skips STG's recurring free theatre tours.
- Captures cancellation/postponement/reschedule state and sold-out state when present.
- No Supabase schema changes.
