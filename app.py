import csv
import io
import json
import re
from datetime import date, datetime, timedelta

import requests
from flask import Flask, Response, render_template, request

app = Flask(__name__)

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


@app.route("/api/isone/locations")
def isone_locations():
    names = get_location_names()
    locations = sorted(
        ({"id": loc_id, "name": name} for loc_id, name in names.items()),
        key=lambda loc: loc["name"],
    )
    return {"locations": locations}


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


NYISO_CSV_URL = "https://oasis-postings.prod.nysdi.com/RT_LBMP_GEN/CSV/{yyyy}/{mm}/{dd}/realtime_gen-{yyyymmdd}.csv"

_nyiso_location_names = {}


def get_nyiso_location_names():
    if _nyiso_location_names:
        return _nyiso_location_names
    today = date.today()
    for offset in range(0, 8):
        day = today - timedelta(days=offset)
        url = NYISO_CSV_URL.format(
            yyyy=day.strftime("%Y"), mm=day.strftime("%m"), dd=day.strftime("%d"),
            yyyymmdd=day.strftime("%Y%m%d"),
        )
        try:
            resp = requests.get(url, timeout=20)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        reader = csv.reader(io.StringIO(resp.text))
        next(reader, None)
        for row in reader:
            if len(row) < 4:
                continue
            _nyiso_location_names[row[2]] = row[1]
        if _nyiso_location_names:
            break
    return _nyiso_location_names


def nyiso_date_range():
    today = date.today()
    for offset in range(DAYS_BACK - 1, -1, -1):
        yield today - timedelta(days=offset)


def fetch_nyiso_day(day, location_id):
    url = NYISO_CSV_URL.format(
        yyyy=day.strftime("%Y"), mm=day.strftime("%m"), dd=day.strftime("%d"),
        yyyymmdd=day.strftime("%Y%m%d"),
    )
    try:
        resp = requests.get(url, timeout=20)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    points = []
    reader = csv.reader(io.StringIO(resp.text))
    next(reader, None)
    for row in reader:
        if len(row) < 4 or row[2] != location_id:
            continue
        try:
            ts = datetime.strptime(row[0], "%m/%d/%Y %H:%M:%S")
        except ValueError:
            continue
        try:
            price = float(row[3])
        except ValueError:
            continue
        points.append({"t": ts.isoformat(), "price": price})
    return points


@app.route("/api/nyiso/locations")
def nyiso_locations():
    names = get_nyiso_location_names()
    locations = sorted(
        ({"id": loc_id, "name": name} for loc_id, name in names.items()),
        key=lambda loc: loc["name"],
    )
    return {"locations": locations}


@app.route("/api/nyiso/stream")
def nyiso_stream():
    location_id = request.args.get("id", "").strip()

    def event(payload):
        return f"data: {json.dumps(payload)}\n\n"

    def generate():
        if not location_id:
            yield event({"error": "missing id"})
            return

        days = list(nyiso_date_range())
        total = len(days)
        names = get_nyiso_location_names()
        yield event({
            "range_start": days[0].isoformat(),
            "range_end": days[-1].isoformat(),
            "total": total,
            "name": names.get(location_id, f"Site {location_id}"),
        })

        for i, day in enumerate(days, start=1):
            points = fetch_nyiso_day(day, location_id)
            yield event({
                "progress": i,
                "total": total,
                "window": day.isoformat(),
                "points": points or [],
            })

        yield event({"done": True})

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/iso-ne")
def iso_ne_page():
    return render_template(
        "dashboard.html",
        iso_name="ISO-NE",
        nav_active="iso-ne",
        example_id="321",
        stream_url="/api/isone/stream",
        locations_url="/api/isone/locations",
        file_prefix="iso-ne",
    )


@app.route("/nyiso")
def nyiso_page():
    return render_template(
        "dashboard.html",
        iso_name="NYISO",
        nav_active="nyiso",
        example_id="24138",
        stream_url="/api/nyiso/stream",
        locations_url="/api/nyiso/locations",
        file_prefix="nyiso",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3215, threaded=True)
