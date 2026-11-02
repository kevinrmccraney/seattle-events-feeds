# Changelog v9.1

- STG feeds now use occurrence-level venue-category pages:
  - `/event-category/paramount/`
  - `/event-category/neptune/`
  - `/event-category/moore/`
- Fixes undercounting from venue summary pages.
- Preserves multiple performances of the same production, including same-day shows.
- Tightens event-card boundaries so rows from neighboring venues cannot bleed together.
- Free theatre tours remain excluded.
- No importer or Supabase schema changes.
