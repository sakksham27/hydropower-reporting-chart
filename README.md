# Hydropower Reporting Tool

A small local dashboard for exploring ISO-NE real-time locational marginal
price (LMP) data by pricing node, with live-streaming charts.

## What it does

- Enter an ISO-NE Location ID and the app pulls the last 7 days of 5-minute
  real-time LMP data for that site directly from ISO-NE's public historical
  reports, filters it to that site, and streams it back to the browser as
  it's fetched (rather than waiting ~20-30s for the whole job).
- Up to 4 sites can be charted at once, each in its own quadrant, plus a
  combined chart overlaying all of them with a color-coded legend.
- Every chart supports a zoom-to-rectangle tool (drag to zoom, double-click
  or the reset button to return to the full view) and an expand view.
- Site names (e.g. `.Z.CONNECTICUT` -> `CONNECTICUT`) are resolved from
  ISO-NE's hourly LMP report, which includes a Location ID -> Name mapping.

NYISO and a Home tab exist as placeholders for future work.

## Running it

```bash
pip install -r requirements.txt
python3 server.py
```

Then open http://localhost:3215.

## Project layout

- `server.py` - Flask backend; streams filtered ISO-NE LMP data over
  Server-Sent Events at `/api/isone/stream?id=<location_id>`.
- `index.html`, `iso-ne.html`, `nyiso.html` - the three pages (Home, ISO-NE,
  NYISO).
- `style.css` - shared styling.

## License

MIT - see [LICENSE](LICENSE).
