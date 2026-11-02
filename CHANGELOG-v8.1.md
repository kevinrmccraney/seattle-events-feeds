# Changelog v8.1

- Triple Door now reads the first-party mainstage calendar and uses per-performance `occurrence_id` values.
- Rabbit Box now reads its first-party Squarespace events calendar rather than Triple Door's ticket listing.
- Fremont Abbey and Ballard Homestead now read the public Google Calendar ICS feeds published on Abbey Arts' calendar page, avoiding Humanitix collection 403 responses.
- Showbox now uses the Crocodile centralized calendar as its source, routing `The Showbox` / `Showbox SoDo` events into the existing `showbox` feed.
- Existing feed keys and importer registry paths are unchanged.
- Status sidecars continue to be written on both success and source failure.
