import csv
import io
import json
import re
from datetime import date, datetime, timedelta

import requests
from flask import Flask, Response, request, send_from_directory

app = Flask(__name__, static_folder=None)

INTERVALS = ["00-04", "04-08", "08-12", "12-16", "16-20", "20-24"]
DAYS_BACK = 7
CSV_URL = "https://www.iso-ne.com/histRpts/5min-rt-final/lmp_5min_{date}_{interval}.csv"
HOURLY_CSV_URL = "https://www.iso-ne.com/histRpts/rt-lmp/lmp_rt_final_{date}.csv"

_location_names = {}

ZONE_PREFIX_RE = re.compile(r"^\.[A-Za-z]\.")


def clean_location_name(name):
    return ZONE_PREFIX_RE.sub("", name)


def get_location_names():
    if _location_names:
        return _location_names
    today = date.today()
    for offset in range(1, 8):
        day = today - timedelta(days=offset)
        url = HOURLY_CSV_URL.format(date=day.strftime("%Y%m%d"))
        try:
            resp = requests.get(url, timeout=15)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        reader = csv.reader(io.StringIO(resp.text))
        for row in reader:
            if not row or row[0] != "D" or len(row) < 6:
                continue
            _location_names[row[3]] = clean_location_name(row[4])
        if _location_names:
            break
    return _location_names


def date_interval_windows():
    today = date.today()
    for offset in range(DAYS_BACK - 1, -1, -1):
        day = today - timedelta(days=offset)
        for interval in INTERVALS:
            yield day, interval


def fetch_window(day, interval, location_id):
    url = CSV_URL.format(date=day.strftime("%Y%m%d"), interval=interval)
    try:
        resp = requests.get(url, timeout=15)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    points = []
    reader = csv.reader(io.StringIO(resp.text))
    for row in reader:
        if not row or row[0] != "D":
            continue
        if row[1] != location_id:
            continue
        local_time = row[2]
        lmp = row[6]
        try:
            hh, mm, ss = local_time.split(":")
            ts = datetime(day.year, day.month, day.day, int(hh), int(mm), int(ss))
        except ValueError:
            continue
        try:
            price = float(lmp)
        except ValueError:
            continue
        points.append({"t": ts.isoformat(), "price": price})
    return points


@app.route("/api/isone/stream")
def isone_stream():
    location_id = request.args.get("id", "").strip()

    def event(payload):
        return f"data: {json.dumps(payload)}\n\n"

    def generate():
        if not location_id:
            yield event({"error": "missing id"})
            return

        windows = list(date_interval_windows())
        total = len(windows)
        names = get_location_names()
        yield event({
            "range_start": windows[0][0].isoformat(),
            "range_end": windows[-1][0].isoformat(),
            "total": total,
            "name": names.get(location_id, f"Site {location_id}"),
        })

        for i, (day, interval) in enumerate(windows, start=1):
            points = fetch_window(day, interval, location_id)
            yield event({
                "progress": i,
                "total": total,
                "window": f"{day.isoformat()} {interval}",
                "points": points or [],
            })

        yield event({"done": True})

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.route("/")
def root():
    return send_from_directory(".", "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3215, threaded=True)
