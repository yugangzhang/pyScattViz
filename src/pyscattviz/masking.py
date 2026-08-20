"""User-defined masks over the reduced 2D products.

Hot-pixel removal answers "is this pixel a detector defect?". This answers a
different question: "do I want this region in my average?" — and the answer is
often no even when the signal is perfectly real. A substrate Bragg peak, the
specular rod, a beamstop shadow, the Yoneda streak: all real, all things you
want out of an azimuthal average before comparing samples.

So a mask here is *authored*, not detected. It is a small list of regions:

``rect``
    A box in the product's own axes — qx/qz on a q-image, q/φ on a caked map.
``ring``
    A |q| band. On a q-image that is an annulus around the origin; on a q–φ map
    the same thing is a column band. This is the one for a substrate powder
    ring.
``wedge``
    An azimuthal band. On a q–φ map a row band; on a q-image the pie slice.
``polygon``
    Anything else, including whatever a lasso drew on screen.

Two things make this worth having rather than a per-product afterthought.

**A region is defined once and applies to both products.** A polygon drawn on
the q-image is in (qx, qz); a q–φ map is in (q, φ). :func:`build_mask` converts
between them, so a spot excluded on the picture is excluded from the caked map
and therefore from the 1-D curve integrated out of it. Draw it where you can
see it, and it takes effect where it matters.

**A mask is a file.** :func:`save_mask` writes JSON to the per-user config
folder, so the same exclusions can be reloaded next session and applied to a
whole batch rather than re-drawn per frame.

Masks are stored as *regions to exclude*. ``keep_only`` inverts the whole set,
for the case where the region of interest is easier to draw than everything
around it.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np

__all__ = [
    "KINDS",
    "MaskRegion",
    "MaskSet",
    "SPACES",
    "build_mask",
    "delete_mask",
    "list_masks",
    "load_mask",
    "mask_path",
    "masks_dir",
    "region_mask",
    "save_mask",
]

KINDS = ("rect", "ring", "wedge", "polygon")
SPACES = ("qimage", "qphi")


@dataclass(frozen=True)
class MaskRegion:
    """One region to exclude.

    ``space`` says which product's coordinates ``coords`` are in, not which
    product the region applies to — it applies to both, converted as needed.

    ``coords`` by kind:

    - ``rect``    ``(x0, x1, y0, y1)`` in the space's own axes
    - ``ring``    ``(q_lo, q_hi)``
    - ``wedge``   ``(phi_lo, phi_hi)`` in degrees
    - ``polygon`` ``((x0, y0), (x1, y1), ...)``
    """

    kind: str
    space: str = "qimage"
    coords: tuple = ()
    label: str = ""
    enabled: bool = True

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown mask kind {self.kind!r}; expected one of {KINDS}")
        if self.space not in SPACES:
            raise ValueError(f"unknown space {self.space!r}; expected one of {SPACES}")

    def describe(self) -> str:
        """A one-line summary for a list the user reads."""

        if self.label:
            return self.label
        if self.kind == "rect":
            x0, x1, y0, y1 = self.coords
            names = ("qx", "qz") if self.space == "qimage" else ("q", "φ")
            return f"rect {names[0]} {x0:.3g}…{x1:.3g}, {names[1]} {y0:.3g}…{y1:.3g}"
        if self.kind == "ring":
            return f"ring q {self.coords[0]:.3g}…{self.coords[1]:.3g}"
        if self.kind == "wedge":
            return f"wedge φ {self.coords[0]:.4g}…{self.coords[1]:.4g}°"
        return f"polygon ({len(self.coords)} points, {self.space})"


@dataclass
class MaskSet:
    """A named list of regions, plus how to combine them."""

    name: str = "mask"
    regions: list = field(default_factory=list)
    keep_only: bool = False

    def enabled_regions(self) -> list:
        return [item for item in self.regions if item.enabled]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "keep_only": bool(self.keep_only),
            "regions": [asdict(item) for item in self.regions],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> MaskSet:
        regions = []
        for item in payload.get("regions") or []:
            try:
                regions.append(
                    MaskRegion(
                        kind=str(item["kind"]),
                        space=str(item.get("space", "qimage")),
                        coords=_as_coords(item.get("coords")),
                        label=str(item.get("label", "")),
                        enabled=bool(item.get("enabled", True)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return cls(
            name=str(payload.get("name") or "mask"),
            regions=regions,
            keep_only=bool(payload.get("keep_only", False)),
        )


def _as_coords(value):
    """Normalize JSON lists back into the tuples the dataclass expects."""

    if value is None:
        return ()
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        return tuple(tuple(float(v) for v in point) for point in value)
    return tuple(float(v) for v in value)


# --------------------------------------------------------------------------
# Rasterizing
# --------------------------------------------------------------------------


def _grids(x_axis, y_axis, space: str):
    """Return ``(x, y, q, phi)`` grids for one product's axes.

    ``q`` and ``phi`` are the polar view: on a q-image they are computed from
    qx/qz, on a caked map they *are* the axes. Having both means a region can be
    written in whichever pair suits it and still apply here.
    """

    x = np.asarray(x_axis, dtype=float)
    y = np.asarray(y_axis, dtype=float)
    xx, yy = np.meshgrid(x, y)
    if space == "qphi":
        q, phi = xx, yy
        # (q, φ) -> Cartesian, so a polygon drawn on the q-image can be tested.
        radians = np.radians(phi)
        cart_x, cart_y = q * np.cos(radians), q * np.sin(radians)
    else:
        cart_x, cart_y = xx, yy
        q = np.hypot(xx, yy)
        phi = np.degrees(np.arctan2(yy, xx))
    return cart_x, cart_y, q, phi


def _between(values, lo, hi) -> np.ndarray:
    low, high = (float(lo), float(hi)) if lo <= hi else (float(hi), float(lo))
    return (values >= low) & (values <= high)


def _phi_between(phi, lo, hi) -> np.ndarray:
    """Azimuthal band, wrapping through ±180 the short way round.

    A wedge from 170° to -170° is the 20° band across the seam, not the 340°
    band the other way. Wrapping is what makes a wedge drawn near the seam do
    what it looked like it would do.
    """

    span = (float(hi) - float(lo)) % 360.0
    offset = (np.asarray(phi, dtype=float) - float(lo)) % 360.0
    return offset <= span


def region_mask(region: MaskRegion, x_axis, y_axis, space: str) -> np.ndarray:
    """Rasterize one region onto a product's grid. True = excluded."""

    cart_x, cart_y, q, phi = _grids(x_axis, y_axis, space)

    if region.kind == "ring":
        return _between(q, *region.coords[:2])

    if region.kind == "wedge":
        return _phi_between(phi, *region.coords[:2])

    if region.kind == "rect":
        x0, x1, y0, y1 = (float(v) for v in region.coords[:4])
        if region.space == space:
            grid_x, grid_y = (q, phi) if space == "qphi" else (cart_x, cart_y)
            return _between(grid_x, x0, x1) & _between(grid_y, y0, y1)
        # Written in the other product's axes: treat it as its polygon.
        corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        return _polygon_mask(corners, region.space, cart_x, cart_y, q, phi)

    if region.kind == "polygon":
        return _polygon_mask(region.coords, region.space, cart_x, cart_y, q, phi)

    return np.zeros(cart_x.shape, dtype=bool)


def _polygon_mask(points, point_space: str, cart_x, cart_y, q, phi) -> np.ndarray:
    """Inside-polygon test, with the grid expressed in the polygon's own space."""

    vertices = np.asarray([[float(a), float(b)] for a, b in points], dtype=float)
    if vertices.shape[0] < 3:
        return np.zeros(cart_x.shape, dtype=bool)

    if point_space == "qphi":
        grid_x, grid_y = q, phi
    else:
        grid_x, grid_y = cart_x, cart_y

    from matplotlib.path import Path as _Path

    flat = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    inside = _Path(vertices).contains_points(flat)
    return inside.reshape(grid_x.shape)


def build_mask(mask_set: MaskSet | None, x_axis, y_axis, space: str) -> np.ndarray | None:
    """Combine every enabled region into one boolean array. True = excluded.

    Returns None when there is nothing to apply, so a caller can skip the work
    rather than allocate an all-False array per frame.
    """

    if mask_set is None:
        return None
    regions = mask_set.enabled_regions()
    if not regions:
        return None

    x = np.asarray(x_axis, dtype=float)
    y = np.asarray(y_axis, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or not x.size or not y.size:
        return None

    out = np.zeros((y.size, x.size), dtype=bool)
    for region in regions:
        try:
            out |= region_mask(region, x, y, space)
        except (TypeError, ValueError, IndexError):
            continue
    if mask_set.keep_only:
        return ~out
    return out


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def masks_dir() -> Path:
    """Folder holding the saved masks."""

    from pyscattviz.exporting import config_dir

    return config_dir() / "masks"


def safe_name(name: str) -> str:
    cleaned = _SAFE.sub("_", str(name).strip()).strip("._-")
    return cleaned or "mask"


def mask_path(name: str) -> Path:
    return masks_dir() / f"{safe_name(name)}.json"


def save_mask(mask_set: MaskSet) -> Path | None:
    """Write the mask as JSON. Returns None if the folder is not writable."""

    path = mask_path(mask_set.name)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mask_set.to_dict(), indent=2), encoding="utf-8")
    except OSError:
        return None
    return path


def load_mask(name: str) -> MaskSet | None:
    try:
        payload = json.loads(mask_path(name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return MaskSet.from_dict(payload)


def list_masks() -> list:
    """Every saved mask name, alphabetically."""

    try:
        with os.scandir(masks_dir()) as entries:
            return sorted(
                entry.name[:-5]
                for entry in entries
                if entry.is_file() and entry.name.endswith(".json")
            )
    except OSError:
        return []


def delete_mask(name: str) -> bool:
    try:
        mask_path(name).unlink()
    except OSError:
        return False
    return True


def with_region(mask_set: MaskSet, region: MaskRegion) -> MaskSet:
    """Return a copy with one region appended — handy from a UI callback."""

    return replace(mask_set, regions=[*mask_set.regions, region])
