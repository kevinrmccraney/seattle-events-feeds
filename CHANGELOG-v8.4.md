# Changelog v8.4

- Triple Door: consume the server-rendered Turbo Stream pagination endpoint exposed by the first-party calendar.
- Rabbit Box: parse the populated first-party events listing directly; remove dependence on the unreliable iCal response.
- Abbey Arts: parse Humanitix event-card anchor text directly and inspect hydration JSON for additional inventory.
- Royal Room: retry transient connection timeouts with increasing timeouts.
- No feed names, importer registry, or Supabase schema changes.
