# Changelog v8.2

- Triple Door now follows each live `/go/events/...occurrence_id=...` performance link and parses its first-party detail page.
- Rabbit Box now follows each first-party `/events/...` item and parses its detail page.
- Abbey Arts venue routing now recognizes the published physical addresses for Fremont Abbey and Ballard Homestead, fixing undercount/zero-routing from ICS location strings.
- Added regression coverage confirming all currently visible Sunset Tavern matches are retained.
- No importer or Supabase schema changes.
