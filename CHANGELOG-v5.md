# Changelog v5

- Added `tractor.xml` producer using Tractor Tavern's public Opendate calendar.
- Filters Tractor-promoted events at other venues out of the Tractor feed.
- Uses stable Opendate numeric event IDs when available.
- Added `clockout.xml` producer using Clock-Out Lounge's public ICS feed.
- Clock-Out parser handles RFC5545 line folding, local/UTC times, UID identity, age/doors/support, cancellation state, and sold-out markers.
- Added both sources to producer registration, source links, status sidecars, and documentation.
- Offline test suite expanded from 6 to 10 tests.
- Chateau Ste. Michelle intentionally deferred.
