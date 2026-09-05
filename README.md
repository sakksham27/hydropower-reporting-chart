# Hydropower Reporting Tool

A small local dashboard for exploring real-time locational marginal price
(LMP) data by pricing node, across two ISOs (ISO-NE and NYISO), with
live-streaming charts.

## What it does

- The home page lets you jump straight to a site: toggle ISO-NE or NYISO,
  pick a site by name from a live autocomplete list, and it opens the right
  dashboard with that site's chart already loading. It also has a short
  intro, a feature card per ISO, and a glossary of LMP/PTID/ISO terms for
  first-time visitors.
- Enter a site ID and the app pulls the last 7 days of real-time price data
  for that site directly from the ISO's public historical reports, filters
  it to that site, and streams it back to the browser as it's fetched
  (rather than waiting for the whole multi-day job before showing anything).
  ISO-NE requires looping over 5-minute-interval report files per day; NYISO
  publishes one CSV per day already filterable by ID, so no sub-day looping
  is needed there.
- Up to 4 sites can be charted at once, each in its own quadrant (auto- or
  fixed-scaled Y-axis, your choice per chart), plus a combined chart
  overlaying all of them with a color-coded legend.
- Every chart supports zoom-to-rectangle, pan, hover tooltips, an expand
  view, and a per-site CSV export.
- A Top 5 Price Records table (deduped within a 10-minute window per site,
  sortable by any column) summarizes the week's biggest price events across
  whichever sites are currently plotted, with a one-line summary below it
  naming the single best price of the week.
- Site names are resolved server-side: ISO-NE's hourly LMP report includes a
  Location ID -> Name mapping (with zone/hub/interface prefixes like `.Z.`
  stripped); NYISO's daily CSV already includes the name next to each PTID.

ISO-NE and NYISO share one dashboard implementation (`static/dashboard.js`,
rendered via `templates/dashboard.html`) parametrized by each ISO's API
endpoints - the two stay in feature parity without duplicated code.

## Running it

```bash
pip install -r requirements.txt
python3 app.py
```

Then open http://localhost:3215.

## Project layout

```
.
├── app.py                  # Flask app: page routes + both ISOs' SSE data-streaming endpoints
├── requirements.txt
├── templates/
│   ├── index.html          # Home
│   └── dashboard.html       # Shared ISO-NE / NYISO dashboard, parametrized per route
└── static/
    ├── style.css            # shared styling
    └── dashboard.js          # shared dashboard logic (charts, zoom/pan, table, tooltips)
```

Routes: `/` (Home), `/iso-ne`, `/nyiso` (both accept an optional
`?id=<site_id>` to auto-load that site's chart on page load), the site-list
endpoints `/api/isone/locations` / `/api/nyiso/locations`, and the SSE data
streams `/api/isone/stream?id=<location_id>` / `/api/nyiso/stream?id=<ptid>`.

## License

MIT - see [LICENSE](LICENSE).
