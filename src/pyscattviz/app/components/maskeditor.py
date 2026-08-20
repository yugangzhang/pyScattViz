"""The panel for authoring an exclusion mask, and drawing one on a panel.

Hot-pixel removal decides what is a *defect*. This decides what is *unwanted*,
which is a different judgement and one only the person doing the analysis can
make: a substrate Bragg peak, the specular rod, the Yoneda streak are all real
signal, and all things you may want out of an azimuthal average before
comparing one sample against another.

Two ways in, because a region is sometimes easier to name than to draw and
sometimes the other way round:

**Numerically** — a q ring, an azimuthal wedge, a box in the panel's own axes.
This is what you want for "drop the substrate ring at 1.9 Å⁻¹", and it is
reproducible across a beamtime because it is a number.

**By drawing** — box- or lasso-select on the q-image or the q–φ map and press
the button. Streamlit hands back the selection in data coordinates, so the
shape is stored in q, not in pixels, and it stays correct when the frame or the
zoom changes.

Either way the mask is a file (see :mod:`pyscattviz.masking`), so it is applied
to the panels, to the line cuts, to the re-integrated 1-D curve, and to the
batch export from one definition rather than four.
"""

from __future__ import annotations

import streamlit as st

from pyscattviz.app.state import action_key, coerce_choice
from pyscattviz.masking import (
    MaskRegion,
    MaskSet,
    delete_mask,
    list_masks,
    load_mask,
    mask_path,
    save_mask,
)

__all__ = [
    "current_mask",
    "render_mask_editor",
    "render_selection_capture",
    "selection_to_region",
]

_SPACE_LABEL = {"qimage": "q-image (qx, qz)", "qphi": "q–φ (q, φ)"}


def _state_key(prefix: str) -> str:
    return f"{prefix}_maskset"


def current_mask(prefix: str) -> MaskSet:
    """The mask this page is editing, created empty on first use."""

    key = _state_key(prefix)
    if not isinstance(st.session_state.get(key), MaskSet):
        st.session_state[key] = MaskSet(name="mask")
    return st.session_state[key]


def _set_mask(prefix: str, mask_set: MaskSet) -> None:
    st.session_state[_state_key(prefix)] = mask_set


def selection_to_region(event, space: str) -> MaskRegion | None:
    """Convert a Streamlit plotly selection into a region, or None.

    A box becomes a rect and a lasso becomes a polygon. Both arrive in data
    coordinates, which is the whole reason this is worth wiring up: the region
    is stored in q and stays right when the frame changes.
    """

    if not event:
        return None
    selection = event.get("selection") if hasattr(event, "get") else None
    if not selection:
        return None

    boxes = selection.get("box") or []
    if boxes:
        box = boxes[0]
        xs, ys = box.get("x") or [], box.get("y") or []
        if len(xs) >= 2 and len(ys) >= 2:
            return MaskRegion(
                kind="rect",
                space=space,
                coords=(float(min(xs)), float(max(xs)), float(min(ys)), float(max(ys))),
            )

    lassos = selection.get("lasso") or []
    if lassos:
        lasso = lassos[0]
        xs, ys = lasso.get("x") or [], lasso.get("y") or []
        if len(xs) >= 3 and len(xs) == len(ys):
            return MaskRegion(
                kind="polygon",
                space=space,
                coords=tuple((float(a), float(b)) for a, b in zip(xs, ys)),
            )
    return None


def render_selection_capture(prefix: str, event, space: str, container=None) -> bool:
    """Offer to add whatever was just drawn on a panel. True if it was added."""

    host = container if container is not None else st
    region = selection_to_region(event, space)
    if region is None:
        return False

    columns = host.columns([3, 1])
    columns[0].caption(f"Drawn: {region.describe()}")
    if columns[1].button(
        "Add to mask",
        key=action_key(st.session_state, f"{prefix}_add_drawn_{space}"),
        use_container_width=True,
    ):
        mask_set = current_mask(prefix)
        mask_set.regions.append(region)
        _set_mask(prefix, mask_set)
        st.rerun()
    return False


def _render_add_form(prefix: str, mask_set: MaskSet) -> None:
    """Numeric entry for the three named shapes."""

    kinds = {
        "Ring (|q| band)": "ring",
        "Wedge (φ band)": "wedge",
        "Box": "rect",
    }
    coerce_choice(st.session_state, f"{prefix}_mask_kind", list(kinds))
    columns = st.columns([1.4, 1, 1, 1.1])
    kind = kinds[columns[0].selectbox("Shape", list(kinds), key=f"{prefix}_mask_kind")]

    if kind == "ring":
        lo = columns[1].number_input(
            "q from", value=0.0, step=0.05, format="%.4f", key=f"{prefix}_mask_ring_lo"
        )
        hi = columns[2].number_input(
            "q to", value=0.0, step=0.05, format="%.4f", key=f"{prefix}_mask_ring_hi"
        )
        coords, space = (float(lo), float(hi)), "qimage"
        ready = hi > lo
    elif kind == "wedge":
        lo = columns[1].number_input(
            "φ from", value=0.0, step=5.0, format="%.1f", key=f"{prefix}_mask_wedge_lo"
        )
        hi = columns[2].number_input(
            "φ to", value=0.0, step=5.0, format="%.1f", key=f"{prefix}_mask_wedge_hi"
        )
        coords, space = (float(lo), float(hi)), "qphi"
        ready = hi != lo
    else:
        space = (
            "qimage"
            if columns[1].selectbox(
                "In", list(_SPACE_LABEL.values()), key=f"{prefix}_mask_rect_space"
            )
            == _SPACE_LABEL["qimage"]
            else "qphi"
        )
        names = ("qx", "qz") if space == "qimage" else ("q", "φ")
        row = st.columns(4)
        x0 = row[0].number_input(
            f"{names[0]} from", value=0.0, step=0.05, format="%.4f", key=f"{prefix}_mask_rect_x0"
        )
        x1 = row[1].number_input(
            f"{names[0]} to", value=0.0, step=0.05, format="%.4f", key=f"{prefix}_mask_rect_x1"
        )
        y0 = row[2].number_input(
            f"{names[1]} from", value=0.0, step=0.05, format="%.4f", key=f"{prefix}_mask_rect_y0"
        )
        y1 = row[3].number_input(
            f"{names[1]} to", value=0.0, step=0.05, format="%.4f", key=f"{prefix}_mask_rect_y1"
        )
        coords = (float(x0), float(x1), float(y0), float(y1))
        ready = x1 != x0 and y1 != y0

    if columns[3].button(
        "Add region",
        key=action_key(st.session_state, f"{prefix}_mask_add"),
        disabled=not ready,
        use_container_width=True,
    ):
        mask_set.regions.append(MaskRegion(kind=kind, space=space, coords=coords))
        _set_mask(prefix, mask_set)
        st.rerun()


def _render_region_list(prefix: str, mask_set: MaskSet) -> None:
    if not mask_set.regions:
        st.caption("No regions yet. Add one above, or box/lasso-select on a panel.")
        return

    st.caption(f"{len(mask_set.regions)} region(s) — untick to suspend one without losing it")
    removed = None
    for index, region in enumerate(mask_set.regions):
        columns = st.columns([0.5, 4, 0.8])
        enabled = columns[0].checkbox(
            "on",
            value=bool(region.enabled),
            key=f"{prefix}_mask_on_{index}",
            label_visibility="collapsed",
        )
        if enabled != region.enabled:
            mask_set.regions[index] = MaskRegion(
                kind=region.kind,
                space=region.space,
                coords=region.coords,
                label=region.label,
                enabled=enabled,
            )
        columns[1].markdown(f"`{region.describe()}`")
        if columns[2].button(
            "✕",
            key=action_key(st.session_state, f"{prefix}_mask_del_{index}"),
            help="Remove this region",
        ):
            removed = index
    if removed is not None:
        mask_set.regions.pop(removed)
        _set_mask(prefix, mask_set)
        st.rerun()


def _render_files(prefix: str, mask_set: MaskSet) -> None:
    saved = list_masks()
    columns = st.columns([1.6, 1, 1, 1])
    name = columns[0].text_input("Mask name", value=mask_set.name, key=f"{prefix}_mask_name")
    if name != mask_set.name:
        mask_set.name = name
        _set_mask(prefix, mask_set)

    if columns[1].button(
        "Save",
        key=action_key(st.session_state, f"{prefix}_mask_save"),
        use_container_width=True,
        disabled=not mask_set.regions,
    ):
        written = save_mask(mask_set)
        if written:
            st.success(f"Saved {written}")
        else:
            st.error("Could not write the mask file.")

    if saved:
        coerce_choice(st.session_state, f"{prefix}_mask_pick", saved)
        chosen = columns[2].selectbox(
            "Saved", saved, key=f"{prefix}_mask_pick", label_visibility="collapsed"
        )
        if columns[3].button(
            "Load",
            key=action_key(st.session_state, f"{prefix}_mask_load"),
            use_container_width=True,
        ):
            loaded = load_mask(chosen)
            if loaded is None:
                st.error(f"Could not read the mask {chosen!r}.")
            else:
                _set_mask(prefix, loaded)
                st.rerun()
        if st.button(
            f"Delete “{chosen}”",
            key=action_key(st.session_state, f"{prefix}_mask_delete"),
        ):
            delete_mask(chosen)
            st.rerun()
    else:
        columns[2].caption("No saved masks yet")

    st.caption("Saved to")
    st.code(str(mask_path(mask_set.name)), language=None)


def render_mask_editor(prefix: str, container=None, expanded: bool = False) -> MaskSet:
    """Draw the whole panel and return the mask this page should apply."""

    host = container if container is not None else st
    mask_set = current_mask(prefix)

    label = "🎭 Exclusion mask"
    if mask_set.enabled_regions():
        label += f" ({len(mask_set.enabled_regions())} region(s))"
    with host.expander(label, expanded=expanded):
        st.caption(
            "Regions you want **out** of the average — a substrate ring, the "
            "specular rod, a Bragg spot from the wafer. This is a judgement, not "
            "a defect test, so nothing here is automatic. A region is stored in q, "
            "so it applies to the q-image, the q–φ map, the line cuts and the "
            "1-D curve alike, and to every frame in a batch."
        )
        keep_only = st.checkbox(
            "Keep only these regions (invert)",
            value=bool(mask_set.keep_only),
            key=f"{prefix}_mask_keep_only",
            help="For when the part you want is easier to draw than the part you do not.",
        )
        if keep_only != mask_set.keep_only:
            mask_set.keep_only = keep_only
            _set_mask(prefix, mask_set)

        _render_add_form(prefix, mask_set)
        st.divider()
        _render_region_list(prefix, mask_set)
        st.divider()
        _render_files(prefix, mask_set)

    return mask_set
