# Changelog v7.3

- Fixed El Corazón/Funhouse against the live calendar: anchors on internal `/shows/...` URLs instead of Opendate ticket URLs.
- Fixed Jazz Alley calendar parsing so `shownum` links can be associated with sibling/ancestor date ranges; preserves one row per performance.
- Fixed Royal Room parsing so date/time can come from the enclosing event container rather than the anchor text itself.
- Added live-structure-derived fixtures for all three connectors.
- Added RSS channel source links for the new feeds.
- Push-to-main, manual, and weekly refresh triggers remain enabled.
