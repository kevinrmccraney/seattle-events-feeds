# Changelog v8.5

- Triple Door now uses the server-rendered Accesso ShoWare performance listing
  (`tickets.thetripledoor.net/performancelisting.asp`) instead of the main-site calendar.
- Triple Door emits one row per listed performance and excludes titles explicitly
  marked `at The Rabbit Box`.
- Abbey Arts adds a whole-page Humanitix text fallback so Ballard Homestead and
  additional Fremont Abbey events are recovered even when SSR omits event anchors.
- Feed names, importer registry, and Supabase schema are unchanged.
