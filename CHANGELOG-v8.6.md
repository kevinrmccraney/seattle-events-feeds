# Changelog v8.6

- Rabbit Box parsing is now event-URL-first.
- Each unique `/events/<slug>` URL becomes one candidate event card.
- Titles are derived only from meaningful anchors pointing to that exact event URL.
- Generic utility labels such as Map, Google Calendar, ICS, Tickets, and View Event
  are explicitly rejected as titles.
- Event blocks spanning multiple event URLs are rejected instead of mixing data
  between neighboring cards.
- Added regression coverage for multiple Rabbit Box cards and the prior `Map`
  title bug.
- No importer or Supabase schema changes.
