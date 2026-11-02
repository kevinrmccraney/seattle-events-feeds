# Changelog v6

- Added shared Nectar Lounge / Hidden Hall calendar connector.
- Publishes `feeds/nectar.xml` and `feeds/hidden-hall.xml` from the same public calendar.
- Uses stable numeric Tixr event IDs.
- Routes events by the calendar's actual venue, excluding promoted/moved shows at other rooms such as Neumos.
- Normalizes title, support, start time, venue, age restriction, promoter, Tixr event/ticket URL, sold-out state, cancellation/reschedule state, and image when present.
- Adds source status sidecars for both feeds.
- Adds offline tests for venue routing and moved-show exclusion.
