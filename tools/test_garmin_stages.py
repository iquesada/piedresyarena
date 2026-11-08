"""Unit tests for tools/garmin_stages.py: the parts that need neither Garmin nor the network."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garmin_stages as gs  # noqa: E402

STAGE = '''---
title: "Colombia 1, de Bogotá a Bituima"
date: 2023-11-11
trip: "colombia-2023"
lat: 4.7110
lng: -74.0721
image: "./placeholder.jpg"
translationKey: "colombia-2023/1-de-bogota-a-bituima"
---

Este es mi primer día.
'''


def line(n, step=0.001):
    """n points going north from (0, 0), about 111 m apart."""
    return [(i * step, 0.0) for i in range(n)]


def test_distance_m_one_degree_of_latitude():
    assert gs.distance_m((0, 0), (1, 0)) == pytest.approx(111195, rel=1e-3)


def test_simplify_straight_line_keeps_only_the_ends():
    pts = line(50)
    assert gs.simplify(pts) == [pts[0], pts[-1]]


def test_simplify_keeps_a_corner():
    pts = line(10) + [(0.009, i * 0.001) for i in range(1, 10)]
    assert gs.simplify(pts) == [pts[0], pts[9], pts[-1]]


def test_simplify_short_tracks_untouched():
    assert gs.simplify([(0, 0), (1, 1)]) == [(0, 0), (1, 1)]


def test_trim_drops_metres_at_both_ends():
    pts = line(21)  # ~2.2 km
    out = gs.trim(pts, start_m=500, end_m=300)
    assert gs.distance_m(pts[0], out[0]) >= 500
    assert gs.distance_m(out[-1], pts[-1]) >= 300
    assert gs.distance_m(pts[0], out[0]) < 500 + 112


def test_trim_more_than_the_track_leaves_one_point():
    assert len(gs.trim(line(5), start_m=10_000)) == 1


def test_samples_every_km_plus_the_end():
    pts = line(100)  # ~11 km
    out = gs.samples(pts, every_km=5)
    assert out[0] == pts[0] and out[-1] == pts[-1]
    assert len(out) == 4  # start, ~5 km, ~10 km, end


def test_rides_on_picks_that_days_rides_in_order():
    acts = [
        {'activityId': 3, 'startTimeLocal': '2023-11-11 15:00:00', 'activityType': {'typeKey': 'gravel_cycling'}},
        {'activityId': 1, 'startTimeLocal': '2023-11-11 08:00:00', 'activityType': {'typeKey': 'road_biking'}},
        {'activityId': 2, 'startTimeLocal': '2023-11-11 12:00:00', 'activityType': {'typeKey': 'walking'}},
        {'activityId': 4, 'startTimeLocal': '2023-11-12 08:00:00', 'activityType': {'typeKey': 'cycling'}},
    ]
    assert [a['activityId'] for a in gs.rides_on(acts, '2023-11-11')] == [1, 3]


def test_gpx_points_with_namespace():
    gpx = b'''<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
    <trkpt lat="4.7" lon="-74.0"><ele>2600</ele></trkpt><trkpt lat="4.8" lon="-74.1"/></trkseg></trk></gpx>'''
    assert gs.gpx_points(gpx) == [(4.7, -74.0), (4.8, -74.1)]


def test_set_fields_replaces_and_appends():
    out = gs.set_fields(STAGE, {'lat': 4.71234, 'lng': -74.07, 'distance': 92.4, 'elevation': 1450})
    assert 'lat: 4.71234\nlng: -74.07\n' in out
    assert out.count('lat:') == 1
    assert 'translationKey: "colombia-2023/1-de-bogota-a-bituima"\ndistance: 92.4\nelevation: 1450\n---\n' in out
    assert out.endswith('Este es mi primer día.\n')


def test_set_villages_is_idempotent():
    once = gs.set_villages(STAGE, ['Mosquera', 'Facatativá'])
    assert '---\n\n<!-- Pueblos en ruta (Garmin): Mosquera, Facatativá -->\n\nEste es mi primer día.' in once
    assert gs.set_villages(once, ['Mosquera', 'Facatativá']) == once
    assert gs.set_villages(once, []) == gs.set_villages(STAGE, [])


def test_stage_dates_in_date_order(tmp_path, monkeypatch):
    for folder, date in [('2-b', '2023-11-12'), ('1-a', '2023-11-11'), ('10-c', '2023-11-20')]:
        (tmp_path / 't' / folder).mkdir(parents=True)
        (tmp_path / 't' / folder / 'index.md').write_text(STAGE.replace('2023-11-11', date))
    monkeypatch.setattr(gs, 'STAGES', tmp_path)
    assert [(p.name, d) for p, d in gs.stage_dates('t')] == [('1-a', '2023-11-11'), ('2-b', '2023-11-12'), ('10-c', '2023-11-20')]
