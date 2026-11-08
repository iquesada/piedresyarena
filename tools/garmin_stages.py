#!/usr/bin/env python3
"""Fill a trip's Spanish stages from the rides recorded in Garmin Connect.

For each stage, the cycling activities of its date give the figures (distance, elevation),
the stage place (where the ride starts), the villages on the way and a simplified track.

Usage (from the repo root, with the .venv):
  .venv/bin/python tools/garmin_stages.py login                      # once; asks for email, password, MFA code
  .venv/bin/python tools/garmin_stages.py fetch <trip>               # report only
  .venv/bin/python tools/garmin_stages.py fetch <trip> --write       # also update the stage files
  .venv/bin/python tools/garmin_stages.py get <api path>             # raw Garmin Connect API call, prints JSON

Needs `pip install -r tools/requirements-garmin.txt` (python-garminconnect: Garmin has no personal API).
"""
import argparse
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES = ROOT / 'src/content/stages/es'
CACHE = ROOT / '.cache/garmin'
TOKENS = '~/.garminconnect'
NOMINATIM = 'https://nominatim.openstreetmap.org/reverse'
USER_AGENT = 'piedresyarena-garmin-stages/1 (https://www.piedresyarena.com)'
VILLAGES_COMMENT = re.compile(r'<!-- Pueblos en ruta \(Garmin\):.*?-->\n\n', re.S)
SIMPLIFY_M = 8  # track tolerance: invisible at any map zoom, ~100-300 points per day
SAMPLE_KM = 5  # one reverse geocoding per this many km of track
PLACE_KEYS = ('village', 'town', 'city', 'hamlet', 'municipality')


# --- geometry -------------------------------------------------------------------------

def distance_m(a, b):
    """Haversine distance between two (lat, lng) points, in metres."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def simplify(points, tolerance_m=SIMPLIFY_M):
    """Douglas-Peucker over a local flat projection; keeps the first and last points."""
    if len(points) < 3:
        return list(points)
    lat0 = math.radians(points[0][0])
    xy = [(p[1] * 111320 * math.cos(lat0), p[0] * 110540) for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = xy[i], xy[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        far, far_d = None, tolerance_m
        for k in range(i + 1, j):
            x, y = xy[k]
            d = abs(dy * (x - x1) - dx * (y - y1)) / norm if norm else math.hypot(x - x1, y - y1)
            if d > far_d:
                far, far_d = k, d
        if far is not None:
            keep[far] = True
            stack += [(i, far), (far, j)]
    return [p for p, k in zip(points, keep) if k]


def trim(points, start_m=0, end_m=0):
    """Drop the first start_m and last end_m metres of track (privacy near home)."""
    def cut(pts, metres):
        done = 0
        for i in range(1, len(pts)):
            done += distance_m(pts[i - 1], pts[i])
            if done >= metres:
                return pts[i:]
        return pts[-1:]
    if start_m:
        points = cut(points, start_m)
    if end_m:
        points = cut(points[::-1], end_m)[::-1]
    return points


def samples(points, every_km=SAMPLE_KM):
    """The start, a point every every_km along the track, and the end."""
    out, done, next_at = [points[0]], 0, every_km * 1000
    for a, b in zip(points, points[1:]):
        done += distance_m(a, b)
        if done >= next_at:
            out.append(b)
            next_at += every_km * 1000
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


# --- Garmin ---------------------------------------------------------------------------

def is_ride(activity):
    key = activity.get('activityType', {}).get('typeKey', '')
    return 'cycl' in key or 'bik' in key


def rides_on(activities, day):
    """The rides that started on day (YYYY-MM-DD, local time), in order."""
    rides = [a for a in activities if is_ride(a) and a.get('startTimeLocal', '').startswith(day)]
    return sorted(rides, key=lambda a: a['startTimeLocal'])


def gpx_points(gpx):
    root = ET.fromstring(gpx)
    return [(float(p.get('lat')), float(p.get('lon'))) for p in root.iter() if p.tag.endswith('}trkpt') or p.tag == 'trkpt']


def garmin():
    try:
        from garminconnect import Garmin
    except ImportError:
        sys.exit('Install the Garmin client first: .venv/bin/pip install -r tools/requirements-garmin.txt')
    client = Garmin()
    try:
        client.login(TOKENS)
    except Exception as e:  # no tokens, or expired beyond refresh
        sys.exit(f'Garmin login failed ({e}). Run: .venv/bin/python tools/garmin_stages.py login')
    return client


def login():
    import getpass
    from garminconnect import Garmin
    client = Garmin(input('Garmin email: '), getpass.getpass('Garmin password: '),
                    prompt_mfa=lambda: input('MFA code: '))
    client.login(TOKENS)  # saves the tokens there; the password is not stored
    print(f'Logged in. Tokens saved in {TOKENS}.')


def gpx_of(client, activity_id):
    path = CACHE / f'{activity_id}.gpx'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(client.download_activity(activity_id, dl_fmt=client.ActivityDownloadFormat.GPX))
    return path.read_bytes()


# --- villages -------------------------------------------------------------------------

def place_name(point):
    """Village, town or city at point, from OpenStreetMap; cached, at most one request a second."""
    path = CACHE / 'nominatim' / f'{point[0]:.3f},{point[1]:.3f}.json'
    if not path.exists():
        query = urllib.parse.urlencode({'lat': point[0], 'lon': point[1], 'format': 'jsonv2', 'zoom': 14, 'accept-language': 'es'})
        req = urllib.request.Request(f'{NOMINATIM}?{query}', headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        time.sleep(1.1)
    address = json.loads(path.read_bytes()).get('address', {})
    return next((address[k] for k in PLACE_KEYS if k in address), None)


def villages(points):
    names = []
    for p in samples(points):
        name = place_name(p)
        if name and name not in names:
            names.append(name)
    return names


# --- stage files ----------------------------------------------------------------------

def set_fields(markdown, fields):
    """Set front matter fields (replacing or appending them), keeping every other line as is."""
    _, front, body = markdown.split('---\n', 2)
    lines = front.splitlines()
    for key, value in fields.items():
        line = f'{key}: {value}'
        i = next((i for i, l in enumerate(lines) if l.startswith(f'{key}:')), None)
        if i is None:
            lines.append(line)
        else:
            lines[i] = line
    return f'---\n' + '\n'.join(lines) + '\n---\n' + body


def set_villages(markdown, names):
    """Put the villages list as an HTML comment at the top of the body, replacing an older one."""
    _, front, body = markdown.split('---\n', 2)
    body = VILLAGES_COMMENT.sub('', body.lstrip('\n'))
    comment = f'<!-- Pueblos en ruta (Garmin): {", ".join(names)} -->\n\n' if names else ''
    return f'---\n{front}---\n\n{comment}{body}'


def stage_dates(trip):
    """(folder, YYYY-MM-DD) of each Spanish stage of trip, in date order."""
    out = []
    for md in sorted((STAGES / trip).glob('*/index.md')):
        m = re.search(r'^date: *"?(\d{4}-\d{2}-\d{2})', md.read_text(), re.M)
        if m:
            out.append((md.parent, m.group(1)))
    return sorted(out, key=lambda s: s[1])


def fetch(trip, write, trim_start, trim_end):
    stages = stage_dates(trip)
    if not stages:
        sys.exit(f'No Spanish stages in {STAGES / trip}')
    client = garmin()
    activities = client.get_activities_by_date(stages[0][1], stages[-1][1])
    for folder, day in stages:
        rides = rides_on(activities, day)
        print(f'\n{folder.name} ({day})')
        if not rides:
            print('  no ride in Garmin Connect')
            continue
        points = [p for r in rides for p in gpx_points(gpx_of(client, r['activityId']))]
        distance = round(sum(r.get('distance') or 0 for r in rides) / 1000, 1)
        elevation = round(sum(r.get('elevationGain') or 0 for r in rides))
        names = villages(points) if points else []
        print(f'  activities: {", ".join(str(r["activityId"]) for r in rides)}')
        print(f'  {distance} km, {elevation} m+')
        if points:
            print(f'  start {points[0][0]:.5f}, {points[0][1]:.5f}   end {points[-1][0]:.5f}, {points[-1][1]:.5f}')
        print(f'  villages: {", ".join(names) or "-"}')
        if not write:
            continue
        md = folder / 'index.md'
        fields = {'distance': distance, 'elevation': elevation}
        if points:
            fields |= {'lat': round(points[0][0], 5), 'lng': round(points[0][1], 5)}
            track = simplify(trim(points, trim_start, trim_end))
            (folder / 'track.json').write_text(json.dumps([[round(a, 5), round(b, 5)] for a, b in track], separators=(',', ':')) + '\n')
        md.write_text(set_villages(set_fields(md.read_text(), fields), names))
        print('  written')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('login', help='log in once and save the tokens')
    f = sub.add_parser('fetch', help="fill a trip's stages from its rides")
    f.add_argument('trip')
    f.add_argument('--write', action='store_true', help='update index.md and write track.json (default: report only)')
    f.add_argument('--trim-start', type=int, default=0, metavar='M', help='leave out the first M metres of each track')
    f.add_argument('--trim-end', type=int, default=0, metavar='M', help='leave out the last M metres of each track')
    g = sub.add_parser('get', help='raw API call, e.g. /activitylist-service/activities/search/activities?startDate=2023-11-11')
    g.add_argument('path')
    args = parser.parse_args(argv)
    if args.cmd == 'login':
        login()
    elif args.cmd == 'fetch':
        fetch(args.trip, args.write, args.trim_start, args.trim_end)
    else:
        # The client rejects query strings in the path: they go as params.
        url = urllib.parse.urlsplit(args.path)
        params = dict(urllib.parse.parse_qsl(url.query))
        print(json.dumps(garmin().connectapi(url.path, params=params), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
