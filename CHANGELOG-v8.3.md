# Changelog v8.3

- Triple Door now crawls the paginated server-rendered detail list instead of
  relying on month-grid cards or per-event requests. Full dates are parsed from
  the detail blocks and Rabbit Box entries are excluded.
- Rabbit Box now consumes the collection-wide Squarespace iCal endpoint
  (`/events?format=ical`), eliminating listing-page pagination/markup problems.
- Abbey Arts now uses the public Humanitix host page for its full current event
  inventory and routes Fremont Abbey vs Ballard Homestead by venue text.
  The public Google calendars remain a fallback if the host page is unavailable.
- No feed names, importer registry, or Supabase schema changed.
