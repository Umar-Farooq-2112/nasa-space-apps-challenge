"""Offline tests for frame rendering helpers. Run: .venv/Scripts/python -m pytest -q"""
import numpy as np

from backend.cutouts import display_wcs, fill_nan


def test_fill_nan_saturated_core_bright_bad_pixel_blends():
    a = np.zeros((9, 9))
    a[3:6, 3:6] = 100
    a[4, 4] = np.nan          # saturated star core
    a[1, 7] = np.nan          # isolated bad pixel in empty sky
    f = fill_nan(a)
    assert f[4, 4] > 50 and abs(f[1, 7]) < 1e-9 and not np.isnan(f).any()


def test_display_grid_is_north_up_and_centred():
    w = display_wcs("133.7598_-7.2422_0.1")
    n = w.pixel_shape[0]
    c = (n - 1) / 2
    ra, dec = w.pixel_to_world_values(c, c)
    assert abs(ra - 133.7598) < 1e-6 and abs(dec + 7.2422) < 1e-6
    _, dec_up = w.pixel_to_world_values(c, c + 1)
    ra_right, _ = w.pixel_to_world_values(c + 1, c)
    assert dec_up > dec and ra_right < ra   # +y = north, +x = west (east left)
