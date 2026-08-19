# Changelog

## 0.7.2

- Fixed the startup crash after upgrading in place. Renaming the pages in 0.7.0
  left the old names in the repository's `build/lib` folder, setuptools folded
  them back into the new wheel, and Streamlit then refused to start at all:
  *Multiple Pages specified with URL pathname Data_Sources_and_Mounts*. That
  happens inside Streamlit before any of our code runs, so the 0.7.1 warning was
  no help. The launcher now removes the stale files itself, by exact name, and
  a `setup.py` shim clears `build/lib` before packaging so it cannot recur.
- Replaced the real beamline, proposal number, project name, and BNL username in
  every example with placeholders — `xxx`, `xxxxxx`, `myproject`, `username` —
  and added a table explaining them. The documentation named one real
  experiment throughout, which it had no need to do.

## 0.7.1

Everything here came from pointing the application at the real CMS and SMI
reduction output on my own machine rather than at the layout I had assumed.

- Axis limits now start blank so each panel scales to the frame it is showing.
  The fixed defaults were clipping real data badly: a CMS GIWAXS q–φ map reaches
  3 Å⁻¹ and an SMI one reaches 7, against a 3.0 default; SMI transmission WAXS
  reaches 9 Å⁻¹ against a 3.5 default; every q-image carries negative qz that a
  0-based minimum hid; and φ runs −179 … +179, so the 0 … 180 default was hiding
  half of every q–φ map.
- Added **Fit to this frame**, which fills the limit boxes from the frame's own
  arrays, alongside the geometry preset (the previous fixed values) and a
  **Clear back to auto** button.
- Fixed CMS QC images never joining their frame. CMS writes several QC layouts
  per frame — `qc_`, `qc_1panel_` … `qc_4panel_autoelevate_` — and each layout
  tag was becoming a frame of its own with no other product attached. On one
  real CMS SAXS folder this turned 5 frames into 10, half of them showing
  "No circular average for this frame". The plain `qc_<name>` image is now the
  one kept, deterministically.
- Fixed `st.plotly_chart(..., width="stretch")`. That parameter does not exist
  in Streamlit 1.50: it fell through to a deprecated Plotly-config path, warned
  on every chart, and never expressed the intended width. Replaced with the
  supported `use_container_width=True`.
- An unreadable QC image no longer raises out of `st.image` on the transmission
  pages; it reports the file like every other product.
- A folder holding only calibration scans now says so, instead of the bare
  "Nothing matches the filter" that sends people looking for a fault that is not
  there.

## 0.7.0

- Added a **Data Selection** page: the GUI form of my `ls_dir` helper. Search one
  or more roots for folders or files with *must contain* / *may contain* /
  *must not contain* term lists, match on the folder name or the whole path,
  bound the depth and the result count, and paste a list of full paths directly.
- Added the **dataset basket** and named collections. A selection is an ordered
  list of full paths that Quick Plot and the explorers read directly, saved as
  plain JSON under `~/.pyscattviz/collections/` and holding nothing but paths.
- Added a **Quick Plot** page that plots any list of paths without a reduction
  layout: 1D overlays with normalization and offsets, a stacked intensity map or
  waterfall built by interpolating every curve onto one grid, and 2D images.
- Added `pyscattviz.dataio`, which reads the one-dimensional conventions that
  actually arrive — comment blocks, missing headers, Fit2D `.chi` header blocks,
  and comma/tab/semicolon/whitespace delimiters — and recognizes `q_ca`/`iq_ca`
  and `q`/`I` automatically.
- Added **save to disk** everywhere something is drawn. One output root, one
  subfolder per page (`GIWAXS_Explorer/`, `Quick_Plot/`, `Publication_Plot/`, …),
  an optional sample subfolder and date subfolder, and no silent overwriting.
  Figures save as PNG/SVG/PDF/HTML/JSON, tables as CSV/TXT, arrays as NPZ/NPY.
- Added an **Output Folder** page to set that root, create folders, and list what
  has been written. Preferences persist in `~/.pyscattviz/settings.json`.
- Added **batch export** to the four explorers: render one panel for every frame
  that passes the current filters and write the set into its own subfolder, with
  a progress bar, a frame cap, and skipped frames reported rather than silently
  dropped.
- Added a dataset-basket folder picker to each explorer sidebar, so moving
  between samples no longer means retyping a long mounted path.
- Added a *Report products* toggle to the folder search. The report costs one
  extra directory listing per match, which is free locally and noticeable over
  SFTP.
- A folder search matched on the path now lists the result folder rather than
  the result folder plus each of its own product subfolders. Searching for
  `cir_avg` on its own still returns the product folders.
- Added free access routes beyond RaiDrive, which is Windows-only: rclone with
  the same commands on all three platforms, GNOME *Files → Connect to Server* on
  Linux with nothing to install, and `sftp -r` / `rclone copy` / FileZilla /
  Cyberduck for copying a subset to the local disk. Data already on a local disk
  is now a first-class registered source.
- Rewrote **Data Sources & Mounts** around a platform-plus-method chooser that
  generates the exact command for the selected combination, and added guidance on
  when to mount, when to copy, and what the application stores.
- Added `pyscattviz.discovery`, `pyscattviz.datasets`, and `pyscattviz.exporting`
  as Streamlit-free modules usable from notebooks and scripts.
- Renumbered the pages with zero-padded prefixes so the sidebar order stays
  correct past nine pages.
- Kaleido is now installed with pyScattViz so static Plotly export works out of
  the box; HTML export continues to need nothing.
- Made the loaders survive the files a real proposal folder actually contains.
  A zero-byte CSV, a single-column CSV, a truncated npz, an npz that is not an
  archive, and a PNG that is not an image each used to take the whole page down;
  they now raise one catchable error, and the panel or curve reports itself
  while the rest of the review continues.

## 0.6.0

- Replaced the Windows mount recommendation with the free RaiDrive SFTP client,
  verified against the NSLS-II server with BNL password, Duo Push, and a mounted
  Windows drive.
- Added proposal, beamline-proposals, `/nsls2/data`, and validated custom mount
  scopes while retaining proposal scope as the safest default.
- Split GISAXS, GIWAXS, transmission SAXS, and transmission WAXS into independent
  pages with geometry-specific q ranges, detector paths, cut widths, and log-axis
  defaults.
- Added a Plotting Studio exposing the consolidated 1D, 2D, 3D, and multi-axes
  plotting tools with safe uploads, selected q-images, interactive controls, and
  data/figure export.
- Improved interactive 2D percentile clipping, log-color labeling, and physical
  coordinate handling.

## 0.5.0

- Removed the Globus browser, transfer workflow, CLI dependency, and remote
  selection state from the web GUI.
- Added a cross-platform **Data Sources & Mounts** page for building proposal
  paths, generating SFTP mount commands, validating mounts, and registering
  remote-to-mounted path mappings.
- Documented native Windows on-demand mounting with Mountain Duck and direct
  SSHFS mounting on Linux and macOS, including BNL password and Duo behavior.
- Kept filename scans and array loading on normal local/mounted filesystem
  paths; the viewer continues to open only the selected frame.

## 0.4.3

- Preserved the Globus path, collection ID, product choices, filename filters,
  remote scan table, and cache settings across Streamlit page navigation.
- Added the saved remote frame count to scattering-viewer guidance while a
  selective transfer is still pending.

## 0.4.2

- Ignored saved remote-to-drive mappings when their translated folder is not
  currently available, allowing the Globus remote workflow to continue.
- Cleared stale local selections during a remote-folder handoff and added a
  viewer message when a selective transfer is still required.

## 0.4.1

- Fixed the Globus-to-File-Selection handoff so it no longer rewrites an
  already-instantiated Streamlit collection-ID widget.

## 0.4.0

- Added direct handoff of the current or selected Globus folder to File
  Selection.
- Added remote filename indexing and the existing boolean/exact-name filters
  without downloading scattering arrays.
- Added Globus Connect Personal collection discovery and selective batch
  transfer of only the matching frame products into a local cache.
- Added transfer-task status checks and one-click activation of a completed
  local cache for the scattering viewers.

## 0.3.1

- Added in-place Globus consent retry without restarting the GUI.
- Preserved every required Globus scope and generated platform-specific consent
  commands for Windows, macOS, and Linux.
- Added refresh/edit controls so a future NSLS2 collection UUID replacement does
  not break remote browsing.
- Clarified Windows update/start commands in the README.

## 0.3.0

- Added browse-only Globus proposal links without starting a transfer.
- Added a cross-platform mounted/local folder navigator with safe `pwd`, `ls`,
  `cd`, and bounded `du` commands on the File Selection page.
- Added an authenticated Globus CLI browser using the active NSLS2 collection,
  with login detection and remote parent/subfolder navigation without transfer.
- Retained path mappings only as an advanced option for genuine existing mounts;
  BNL Duo-authenticated proposal access now uses Globus rather than SSHFS-Win.
- Added project issue-reporting and scientific-contact links to Home.

## 0.2.1

- Added named startup files for Windows, macOS, and Linux.
- Added the cross-platform `python -m pyscattviz` entry point.
- Clarified the Windows `Scripts` and macOS/Linux `bin` environment paths.

## 0.2.0

- Consolidated Yugang Zhang's earlier pyViz plotting library under
  `pyscattviz.plotting`.
- Added 1D, 2D, 3D, and N-D plotting, themes, custom colormaps, layouts,
  overlays, transforms, label cleanup, and figure export.
- Added the Publication Plot GUI page for selected circular-average curves.
- Preserved the lazy filename and selected-frame data-loading model.

## 0.1.0

- Added the initial Globus/local data-source workflow.
- Added lazy boolean and exact-list filename selection.
- Added GISAXS/GIWAXS and transmission SAXS/WAXS viewers.
