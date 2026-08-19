# pyScattViz user guide

## Application flow

The application has eleven task pages in addition to Home.

1. **Data Sources & Mounts** builds the NSLS-II SFTP path, generates
   platform-specific commands for mounting, copying a subset, or registering a
   local folder, validates the result, and records the mapping.
2. **Data Selection** searches one or more roots for folders or files with
   AND/OR/EXCLUDE term lists, accepts a pasted list of full paths, and keeps the
   result in a dataset basket that can be saved under a name.
3. **File Selection** includes a folder navigator, scans filenames, applies
   boolean or exact-list filters, and saves canonical frame names.
4. **GISAXS Explorer** reviews low-q grazing-incidence results with GISAXS
   ranges and qx/qz cut widths.
5. **GIWAXS Explorer** reviews wide-q grazing-incidence results with GIWAXS
   ranges and orientation analysis.
6. **Transmission SAXS** uses SAXS detector defaults, low-q ranges, and log-q
   I(q) display.
7. **Transmission WAXS** uses WAXS detector defaults, high-q ranges, and
   linear-q display.
8. **Quick Plot** plots any list of full paths as 1D overlays, a stacked
   intensity map, or 2D images — no reduction layout required.
9. **Publication Plot** turns selected circular averages into static figures
   for papers, reports, and presentations.
10. **Plotting Studio** provides interactive 1D, 2D, and 3D workspaces plus an
    exportable multi-axes builder.
11. **Output Folder** sets where saved figures go and lists what has been
    written there.

## Choosing the data with term lists

**Data Selection** is the GUI form of the `ls_dir` helper from pyScatt. Three
lists drive every query:

| List | Meaning |
|---|---|
| Must contain (AND) | every term must match |
| May contain (OR) | at least one term must match |
| Must not contain (EXCLUDE) | no term may match |

An empty list imposes no condition. A term is a substring unless it contains a
shell wildcard (`*`, `?`, `[`), in which case it matches the whole name.
Matching ignores case. Separate terms with commas, semicolons, or new lines.

Match on the folder **name** to find `giwaxs` folders anywhere; match on the
whole **path** to express `Results AND giwaxs`, which is how a proposal tree is
usually searched. Limit the depth: four levels covers most proposal layouts and
keeps a broad search over a network mount from running away. A search that hits
the result cap says so rather than silently truncating.

Selected rows go into the **dataset basket**, an ordered list of full paths that
Quick Plot reads directly and that any explorer can be pointed at. Save it under
a name and it becomes a JSON file under `~/.pyscattviz/collections/` holding
nothing but paths.

The same functions are importable:

```python
from pyscattviz.discovery import filter_names, find_files, find_folders, ls_dir
```

## Plotting an arbitrary list of files

**Quick Plot** takes the basket, one folder, or a pasted list. It reads curves
(`.csv`, `.txt`, `.dat`, `.chi`, `.xy`), arrays (`.npz`, `.npy`), and images
(`.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg`). Comment blocks, missing headers,
Fit2D `.chi` header blocks, and comma/tab/semicolon/whitespace delimiters are
handled; `q_ca`/`iq_ca` and `q`/`I` are recognized automatically and any other
column can be chosen by name.

- **1D curves** overlays the selection with normalization (maximum, integral, or
  at a chosen x), additive or multiplicative offsets, log axes, an x range, and
  legend labels trimmed of the boilerplate every beamline stem carries. A
  matching matplotlib publication figure is available in the same tab.
- **Stacked map** interpolates every curve onto one x grid and shows the set as
  an intensity map or a waterfall — the fastest way to read an in-situ or angle
  series. Points outside a curve's own range stay blank rather than being
  extrapolated.
- **2D images** shows detector images and 2D arrays with robust percentile
  contrast, log or linear colour, equal aspect, and vertical flip.

## Selecting folders

A result root normally contains `cir_avg`, `q_image`, `qc`, and `qphi`.
Entering one product folder, such as `.../giwaxs/q_image`, focuses the viewer on
that product. Entering the parent `.../giwaxs` allows any available combination.

Folder lists can contain local disks, external drives, institutional network
storage, and SFTP mounts. A remote `/nsls2/data/...` path is translated only
after its mounted path has been tested and registered under **Data Sources &
Mounts**. Viewers open array data on demand through that filesystem mount.

File Selection supports direct path pasting and a safe command bar. Use `pwd`
to show the current folder, `ls [path]` to list it, `cd <path>` to move through
the tree, and `du [path]` for a size estimate. These are built-in read-only
operations; pyScattViz does not open a system shell. Quote paths containing
spaces. The `du` scan stops after 5,000 files to remain responsive on large
network trees.

## Selecting filenames

Use a boolean expression for reproducible groups:

```text
polymer_A AND (0.08deg OR 0.10deg) NOT calibration
```

Operator order is `NOT`, then `AND`, then `OR`. Parentheses override this order.
Matching is case-insensitive. A term without wildcards is a substring; terms
with `*`, `?`, or `[]` use whole-filename wildcard matching.

Use the exact-list box for filenames copied from a spreadsheet, log, or Python
script. Lines and commas are both accepted. Product-specific names are reduced
to the common frame stem before matching.

## Geometry-specific explorers

The experiment geometries are deliberately separate because their useful q
ranges, detector locations, line-cut widths, and analysis emphasis differ.

| Geometry | Initial q range (Å⁻¹) | q-axis default | Emphasis |
|---|---:|---|---|
| GISAXS | 0.001–0.5 | log for I(q) | low-q qx/qz morphology |
| GIWAXS | 0–3.0 | linear | wide-q texture and orientation |
| Transmission SAXS | 0.001–0.5 | log | low-q size/structure and anisotropy |
| Transmission WAXS | 0–3.5 | linear | high-q peaks and orientation |

Every value remains editable in the page. The four pages retain independent
widget state and raw-detector choices while sharing the same tested lazy file
loaders.

## Understanding the panels

- **Raw / stitched** shows detector or stitched pixel coordinates.
- **QC** shows the reduction quality-control image when present.
- **q-image** shows `qx–qz` or `qr–qz` data from the selected NPZ.
- **q–φ** shows intensity as a function of q and azimuth.
- **Circular average** shows I(q) from the selected CSV.

The range panel controls intensity limits, axis limits, aspect ratio, line
style, and log scaling. Large 2D arrays are stride-downsampled for browser
display while line cuts use the loaded array values.

## Line cuts

The GISAXS and GIWAXS pages support bands on q-images and q–φ maps. The
transmission pages focus their cuts on q–φ maps. Enter one or more centers
separated by spaces or commas and set a band width. The shaded bands appear on
the map, and the averaged profiles appear below the panels. Download exports
every displayed profile to one CSV table.

## Plotting Studio

The four Plotting Studio tabs expose the reusable plotting API without writing
Python code:

- **1D** reads a numeric table, overlays chosen columns, applies maximum or
  integral normalization, and exports the plotted table.
- **2D** accepts NPY/NPZ, numeric tables, common detector-image formats, or
  q-images saved by File Selection. Percentile clipping and log intensity are
  interactive.
- **3D** turns a matrix into a rotatable surface or wireframe, or a top-down
  contour.
- **Multi-axes** builds grids, main-plus-residual figures, and mosaics with the
  supported publication themes and PNG/SVG/PDF output.

NPY/NPZ object pickles are disabled. Uploaded content remains in the local
Streamlit session.

## Publication figures

The Publication Plot page shares the active result folder and saved File
Selection. It indexes `cir_avg` names first, then opens only the CSV files
explicitly selected in the multiselect box. I cap one figure at 50 curves to
keep legends and browser memory manageable.

Available controls include:

- science, notebook, presentation, and poster themes;
- maximum or integral normalization;
- q-range limits, logarithmic axes, and additive waterfall offsets;
- figure dimensions and legend visibility;
- 300-DPI PNG or vector SVG/PDF download.

For notebook and Python-script use, import the same plotting layer with
`import pyscattviz.plotting as pv`. The complete API is documented in
[PLOTTING_API.md](PLOTTING_API.md).

## Saving to your own folder

Every page that draws something has a **💾 Save to disk** panel. They share one
output root, set on the **Output Folder** page and remembered in
`~/.pyscattviz/settings.json`, and each writes into a subfolder named after the
page: `GIWAXS_Explorer/`, `Quick_Plot/`, `Publication_Plot/`, and so on. An
optional extra subfolder holds a sample or session name, and an optional date
subfolder separates repeated sessions.

Names are sanitized for Windows without losing the decimal points that beamline
stems are full of, so `Kim_th0.1000deg_qphi` stays intact. Nothing is
overwritten silently: a repeated name becomes `name_001`, `name_002`, … unless
**Overwrite** is turned on.

| Payload | Formats |
|---|---|
| Interactive Plotly figure | png · svg · pdf · html · json |
| matplotlib figure | png · svg · pdf · eps · tif |
| Plotted data | csv · tab-separated txt |
| Displayed array | npz · npy |
| Path or filename list | txt |

Static images of the interactive figures use the free `kaleido` package
installed with pyScattViz. On a computer with no Chrome or Chromium, run
`plotly_get_chrome` once in the same environment; HTML export never needs it.

The same helpers work from a notebook:

```python
from pyscattviz.exporting import resolve_output_dir, save_matplotlib_figure

folder = resolve_output_dir("~/pyScattViz_Output", "GIWAXS Explorer", create=True)
save_matplotlib_figure(fig, folder, "sample_A_cir_avg", fmt="png", dpi=300)
```

## Memory and performance

Filename indexing uses an iterator and retains only matching canonical stems.
The default selection cap is 5,000 frames. A broad query may still take time on
a network filesystem because directory entries must be inspected, but array
data are not loaded during that scan.

The viewer loads one active frame and caches it for interaction. Close the app
or use Streamlit's cache controls after switching between many very large data
sets when memory becomes constrained.

## Updating

The start paths are platform-specific: Windows virtual environments use
`.venv\Scripts`, while macOS and Linux use `.venv/bin`.

On Windows PowerShell:

```powershell
cd $HOME\pyScattViz
git pull
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pip install --upgrade .
.\start_windows.bat
```

On macOS or Linux:

```bash
cd "$HOME/pyScattViz"
git pull
rm -rf build
./.venv/bin/python -m pip install --upgrade .
./.venv/bin/python -m pyscattviz
```

Deleting `build` matters when upgrading past 0.7.0: an earlier in-place install
leaves the old page files there, and setuptools folds them back into the new
wheel so the sidebar lists several pages twice. pyScattViz prints a warning at
startup if that has happened.

For normal daily startup, I included `start_windows.bat`,
`start_macos.command`, and `start_linux.sh` in the repository root. On Windows,
the PowerShell error that says `./.venv/bin/pyscattviz` is not recognized means
that a macOS/Linux path was used. Run `.\start_windows.bat` instead.
