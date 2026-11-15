"""Offline tests for the IRSA fetch logic (no network). Run: .venv/Scripts/python -m pytest -q"""
import json

import pytest

from backend import irsa


def test_spread_covers_whole_time_range():
    images = [[f"u{i}.fits", float(i)] for i in range(100)]
    picks = irsa.spread(images, 5)
    assert [p[1] for p in picks] == [0, 25, 50, 74, 99]
    assert irsa.spread(images[:3], 5) == images[:3]


def test_fetch_reuses_old_list_when_irsa_is_down(tmp_path, monkeypatch):
    saved = tmp_path / "images_D3.json"
    saved.write_text(json.dumps([["a.fits", 1.0], ["b.fits", 2.0]]))
    monkeypatch.setattr(irsa, "LIST_MAX_AGE", -1)  # list is "old", so fetch tries to search again
    monkeypatch.setattr(irsa.sky_index, "find_images", lambda *a: None)  # no local index

    def down(*a, **k):
        raise RuntimeError("IRSA down")
    got = []
    monkeypatch.setattr(irsa, "find_images", down)
    monkeypatch.setattr(irsa, "download", lambda uri, *a, **k: got.append(uri))
    job = {}
    irsa.fetch(1, 2, 0.1, "D3", tmp_path, job=job)
    assert sorted(got) == ["a.fits", "b.fits"] and job["total"] == 2

    saved.unlink()  # no old list to fall back on: the error must reach the user
    with pytest.raises(RuntimeError):
        irsa.fetch(1, 2, 0.1, "D3", tmp_path)
