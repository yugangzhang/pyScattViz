# pyScattViz plotting API

I consolidated my earlier pyViz package into `pyscattviz.plotting`. This keeps
the plotting functions and the scattering-review application in one supported
installation.

## Import

```python
import pyscattviz.plotting as pv
```

Existing notebooks that used `import pyViz as pv` only need the import line
changed. Function names and the main calling patterns remain the same.

## Publication theme and I(q)

```python
import numpy as np
import pyscattviz.plotting as pv

pv.set_theme("science")
q = np.logspace(-3, 0, 300)
i_q = 2e4 * q**-2.2

ax = pv.plot1d(
    i_q,
    x=q,
    logx=True,
    logy=True,
    xlabel=r"q ($\AA^{-1}$)",
    ylabel="I(q)",
    title="Circular average",
)
pv.save_fig(ax.figure, "circular_average.svg")
```

`plot1d_multi` accepts dictionaries or tuples and assigns distinct colors:

```python
datasets = [
    {"x": q, "y": i_q, "label": "sample A"},
    {"x": q, "y": 0.5 * i_q, "label": "sample B"},
]
pv.plot1d_multi(datasets, logx=True, logy=True)
```

## q-space images

```python
ax = pv.imshow(
    q_image,
    log=True,
    cmap="pv_vge_hdr",
    colorbar=True,
    xlabel=r"$q_x$ ($\AA^{-1}$)",
    ylabel=r"$q_z$ ($\AA^{-1}$)",
)
```

For transformed displays, `imshow_z` supports `linear`, `log`, `gamma`, and
`radial` intensity transforms. `z_range` provides percentile-based contrast.

## Layouts and overlays

```python
fig, axes = pv.create_axes(1, 2, figsize=(10, 4))
pv.plot1d(i_q, x=q, ax=axes[0], logx=True, logy=True)
pv.imshow(q_image, ax=axes[1], log=True, cmap="pv_vge_hdr")
pv.add_vlines(axes[0], [0.1, 0.2], color="crimson")
pv.add_text_box(axes[0], "selected peaks")
pv.save_fig(fig, "combined_figure.pdf")
```

Additional layout helpers create ratio panels, named mosaics, and inset axes.
Mask overlays display labeled regions over detector or q-space images.

## 3D and N-D data

```python
pv.surface(qx_grid, qz_grid, intensity_grid, cmap="plasma")
pv.scatter3d(qx, qy, qz, c=intensity)
pv.correlation_matrix(dataframe)
pv.pairplot(dataframe, hue="sample")
```

Add `interactive=True` to the main 1D, 2D, 3D, and N-D functions for a Plotly
figure when that backend is supported.

## Themes and custom colormaps

Themes are `science`, `notebook`, `present`, and `poster`. Use a context when a
temporary style is preferable:

```python
with pv.theme_context("present"):
    pv.plot1d(i_q, x=q)
```

`pv.list_cmaps()` reports the bundled scattering colormaps. Their names begin
with `pv_` for compatibility with earlier figures, including `pv_vge`,
`pv_vge_hdr`, `pv_albula`, `pv_hdr_goldish`, `pv_cyclic`, and `pv_jet_ext`.

## Export

```python
pv.save_fig(fig, "figure.png", dpi=300)
png_bytes = pv.fig_to_bytes(fig, format="png", dpi=300)
svg_bytes = pv.fig_to_bytes(fig, format="svg")
```

PNG is appropriate for raster images and slides. SVG or PDF preserves vectors
for line plots and publication editing.
