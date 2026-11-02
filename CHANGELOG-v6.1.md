# Changelog v6.1

- Fixed Nectar/Hidden Hall live parsing:
  - no longer assumes the event title itself links to Tixr
  - detects complete event cards first
  - uses exact physical venue lines for routing
  - derives stable Tixr IDs from the ticket link
- Replaced Clock-Out ICS ingestion with direct parsing of the populated public TicketWeb calendar.
- Clock-Out now follows `?twpage=N` pagination.
- Preserves zero-event safety behavior; genuine parser failures still surface rather than silently publishing an empty feed.
