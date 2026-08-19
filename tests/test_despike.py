"""Hot-pixel removal on the reduced 2D products.

The hard part is not finding bright pixels; it is not deleting the sharp
reflections that an oriented substrate produces. These tests encode the two
cases that a naive threshold gets wrong.
"""

import numpy as np
import pytest

from pyscattviz.despike import (
    apply_hot_mask,
    azimuthal_average,
    find_hot_pixels,
    find_hot_pixels_stack,
    hot_pixel_summary,
    remove_hot_pixels,
)


@pytest.fixture
def frame():
    """A smooth pattern with one stuck pixel and one real Bragg spot."""

    y, x = np.mgrid[0:60, 0:60]
    image = 100.0 + 400.0 * np.exp(-((x - 30) ** 2 + (y - 30) ** 2) / 200.0)
    image[10, 45] = 500_000.0  # stuck pixel: isolated, absurd
    # A real reflection is a few pixels across, not one.
    image[40:43, 12:15] += 3_000.0
    return image


def test_a_stuck_pixel_is_found(frame):
    hot = find_hot_pixels(frame)
    assert hot[10, 45]


def test_the_smooth_bright_centre_is_not_touched(frame):
    hot = find_hot_pixels(frame)
    assert not hot[28:33, 28:33].any()


def test_a_steep_gradient_is_not_a_spike():
    """A pixel at 1.0x its neighbours was being flagged by a global threshold."""

    y, x = np.mgrid[0:80, 0:80]
    steep = 10.0 ** (4.0 - 0.05 * x)  # orders of magnitude across the frame
    assert not find_hot_pixels(steep).any()


def test_non_finite_pixels_are_never_flagged(frame):
    frame[0, 0] = np.nan
    assert not find_hot_pixels(frame)[0, 0]


def test_a_flat_or_empty_image_is_handled():
    assert not find_hot_pixels(np.zeros((10, 10))).any()
    assert find_hot_pixels(np.array([])).shape == (0,)
    assert not find_hot_pixels(np.full((5, 5), np.nan)).any()


def test_persistence_separates_a_defect_from_a_reflection():
    """A defect recurs at the same pixel; a reflection moves with the sample."""

    rng = np.random.default_rng(0)
    frames = []
    for index in range(8):
        image = 100.0 + rng.normal(0, 3, (50, 50))
        image[20, 20] = 90_000.0  # the defect, every frame
        image[5 + index, 40] = 60_000.0  # a spot that moves
        frames.append(image)

    mask, info = find_hot_pixels_stack(frames, persist_frac=0.9)
    assert mask[20, 20]
    assert info["n_hot"] == 1
    assert info["frames"] == 8


def test_a_majority_vote_over_one_sample_would_keep_a_reflection():
    """Why the default is 0.9 and the stack should span samples."""

    rng = np.random.default_rng(1)
    frames = []
    for _ in range(6):
        image = 100.0 + rng.normal(0, 3, (40, 40))
        image[10, 10] = 50_000.0  # same spot in this sample's whole series
        frames.append(image)

    lenient, _ = find_hot_pixels_stack(frames, persist_frac=0.5)
    assert lenient[10, 10]  # a single sample cannot tell the difference


def test_stack_ignores_frames_of_the_wrong_shape():
    good = [np.zeros((10, 10)), np.zeros((10, 10))]
    mask, info = find_hot_pixels_stack([*good, np.zeros((5, 5))])
    assert info["frames"] == 2
    assert mask.shape == (10, 10)


def test_an_empty_stack_is_reported_not_raised():
    mask, info = find_hot_pixels_stack([])
    assert info["frames"] == 0 and mask.size == 0


def test_removal_blanks_to_nan_so_averages_skip_it(frame):
    cleaned = remove_hot_pixels(frame)
    assert np.isnan(cleaned[10, 45])
    assert np.nanmax(cleaned) < 10_000
    # the original is untouched
    assert frame[10, 45] == 500_000.0


def test_a_supplied_mask_is_used_verbatim(frame):
    mask = np.zeros(frame.shape, dtype=bool)
    mask[0, 0] = True
    cleaned = remove_hot_pixels(frame, mask=mask)
    assert np.isnan(cleaned[0, 0])
    assert cleaned[10, 45] == 500_000.0  # not searched for, so not removed


def test_a_mismatched_mask_is_ignored_rather_than_raising(frame):
    assert np.array_equal(
        apply_hot_mask(frame, np.zeros((3, 3), dtype=bool)), frame, equal_nan=True
    )


def test_the_summary_describes_what_went(frame):
    mask = find_hot_pixels(frame)
    summary = hot_pixel_summary(frame, mask)
    assert summary["count"] >= 1
    assert summary["max_removed"] == pytest.approx(500_000.0)
    summary_none = hot_pixel_summary(frame, np.zeros(frame.shape, dtype=bool))
    assert summary_none["count"] == 0


# ---------------------------------------------------------------------------
# Re-integrating the cleaned map
# ---------------------------------------------------------------------------
def test_azimuthal_average_skips_blanked_pixels():
    caked = np.full((10, 5), 2.0)
    caked[3, 2] = np.nan
    q, intensity = azimuthal_average(caked, np.linspace(0.1, 0.5, 5))
    np.testing.assert_allclose(intensity, 2.0)


def test_a_hot_pixel_moves_the_bin_until_it_is_removed():
    """One pixel in 20 at 100000 against 100 lifts the mean by 500x."""

    caked = np.full((20, 4), 100.0)
    caked[7, 1] = 100_000.0
    q = np.linspace(0.1, 0.4, 4)

    _q, raw = azimuthal_average(caked, q)
    _q, clean = azimuthal_average(remove_hot_pixels(caked), q)
    assert raw[1] > 5_000
    assert clean[1] == pytest.approx(100.0)


def test_the_azimuthal_window_selects_rows():
    caked = np.zeros((10, 3))
    phi = np.linspace(-180, 180, 10)
    caked[phi > 0, :] = 5.0
    _q, upper = azimuthal_average(caked, np.arange(3.0), phi, (10, 180))
    _q, lower = azimuthal_average(caked, np.arange(3.0), phi, (-180, -10))
    assert upper[0] == pytest.approx(5.0)
    assert lower[0] == pytest.approx(0.0)


def test_an_empty_window_falls_back_to_every_row():
    caked = np.full((6, 3), 4.0)
    phi = np.linspace(-180, 180, 6)
    _q, intensity = azimuthal_average(caked, np.arange(3.0), phi, (400, 500))
    np.testing.assert_allclose(intensity, 4.0)


def test_a_mismatched_q_axis_is_refused():
    with pytest.raises(ValueError):
        azimuthal_average(np.zeros((4, 5)), np.arange(3.0))
