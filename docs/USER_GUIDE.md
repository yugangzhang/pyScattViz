# pyScattViz user guide

## Application flow

I organized the application around five pages.

1. **Globus & Data Sources** builds the NSLS-II collection path for online
   browsing and records one or more mounted/local folders.
2. **File Selection** includes a folder navigator, scans filenames, applies
   boolean or exact-list filters, and saves canonical frame names.
3. **GISAXS / GIWAXS Explorer** reviews grazing-incidence results.
4. **Transmission SAXS / WAXS** reviews transmission results and supports
   editable raw-detector folder locations.
5. **Publication Plot** turns selected circular averages into static figures
   for papers, reports, and presentations.

## Selecting folders

A result root normally contains `cir_avg`, `q_image`, `qc`, and `qphi`.
Entering one product folder, such as `.../giwaxs/q_image`, focuses the viewer on
that product. Entering the parent `.../giwaxs` allows any available combination.

Folder lists can contain local disks, external drives, institutional mounted
storage, and completed Globus destinations. A Globus `/nsls2/data/...` path can
be opened in Globus File Manager without transferring it, but it is not a
Windows/local filesystem path. To load frames lazily, use a transferred result
folder or expose the remote data as a mapped/mounted network folder.

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

The grazing-incidence viewer supports bands on q-images and q–φ maps. Enter one
or more centers separated by spaces or commas and set a band width. The shaded
bands appear on the map, and the averaged profiles appear below the panels.
Download exports every displayed profile to one CSV table.

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
.\.venv\Scripts\python.exe -m pip install --upgrade .
.\start_windows.bat
```

On macOS or Linux:

```bash
cd "$HOME/pyScattViz"
git pull
./.venv/bin/python -m pip install --upgrade .
./.venv/bin/python -m pyscattviz
```

For normal daily startup, I included `start_windows.bat`,
`start_macos.command`, and `start_linux.sh` in the repository root. On Windows,
the PowerShell error that says `./.venv/bin/pyscattviz` is not recognized means
that a macOS/Linux path was used. Run `.\start_windows.bat` instead.
