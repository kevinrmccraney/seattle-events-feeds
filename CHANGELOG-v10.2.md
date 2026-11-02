# Changelog v10.2

- Rabbit Box now parses canonical Squarespace `/events/<slug>` event cards and rejects calendar/map utility links as titles.
- Triple Door now parses canonical `/go/events/` occurrences from the first-party Mainstage Calendar, excluding Rabbit Box and non-Mainstage entries.
- Chop Suey now parses individual TicketWeb `/event/` cards rather than flattened page text.
- Abbey Arts now deduplicates Humanitix + Google Calendar records by normalized title and occurrence time, preferring richer records.
- Adds minimum inventory guards for Paramount, Neptune, Moore, Substation, Chop Suey, Triple Door, Rabbit Box, Fremont Abbey, and Ballard Homestead.
- Inventory below the configured floor writes `inventory_below_expected` status and preserves the last good RSS file.
- Feed names, importer registry, and Supabase schema are unchanged.
