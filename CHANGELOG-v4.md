# v4 feed-producer changes

- Removes all Supabase/database writes from scraper code.
- Emits one normalized RSS 2.0 feed per source.
- Publishes source status sidecars for exact error propagation.
- Preserves the previous good RSS file when a producer fails.
- Keeps the validated Carbonhouse, DICE, and Seattle-only Showbox adapters.
- Fetches the full currently exposed upcoming calendar once per week.
