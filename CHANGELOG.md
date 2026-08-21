# Changelog

## 0.16.2

- **Confirmed and pinned the masking contract**: a masked pixel is *not used*,
  it never contributes a zero. Verified on a uniform map through every path —
  user mask, hot-pixel removal, both together, and the reduction's own no-data
  zeros — each comes back at exactly the original level rather than a fraction
  of it, and the gaps reach the CSV as empty cells and the NPZ as NaN.
- The cleaning path now shares `apply_mask` with the panels rather than keeping
  its own copy. That matters beyond tidiness: `apply_mask` *infers* which way
  round a boolean mask is written from its overlap with the positive pixels, and
  some products use True for *valid*. The private copy assumed True meant
  masked, which on such a file would have blanked the data and kept the gaps.

## 0.16.1

- **Fixed the re-integrated I(q) reading low.** A reduced q–φ map marks the
  (q, φ) bins the detector never reached with **0**, not NaN — 64% of a real CMS
  GIWAXS map — and those zeros were being averaged in as real intensity. The
  curve came out at **0.43×** the reduction's own circular average. Zeros are now
  treated as no data, which is the reduction's own convention (pySAXSAI defines
  `qimg_mask = (qimg == 0)`, and on a q-image the two agree pixel for pixel).
  The two traces in panel D now sit on each other to **0.3%**.
- **The qr–qz remesh is easier to find.** A reduction run with
  `qimg_x_axis = ['Qx', 'Qr']` puts both remeshes in one npz, but nothing said
  so. Panel B's title now names the remesh on screen — *B · q-image (qx–qz)* —
  and a note beside the **B x-axis** control says when the file carries both.

## 0.16.0

- **Batch process in all four explorers.** Set the cleaning up on one frame —
  hot pixels, an exclusion mask — then apply exactly that to every frame that
  passed the filter and write what you tick: **I(q)** (q–φ averaged over φ),
  **I(φ)** (averaged over q), **panels**, **cleaned arrays**, and a **manifest**
  recording what was done to what. Band centres turn either reduction into a
  series of sector cuts.
- **One cleaning, used everywhere.** The hot-pixel settings, the across-frames
  defect vote and the exclusion mask now live in a single `Cleaning` object that
  the 2D panels, the line cuts, the 1D curve and the batch all share — so a
  batch cannot quietly stop matching what was on screen when it was set up.
- **Transmission SAXS and WAXS gained the exclusion mask**, the defect vote and
  the re-integrated curve, which until now only the grazing pages had.
- Verified on 756 real CMS frames: a ring masked at q 1.9–2.05 comes out as 19
  of 19 NaN bins in every written I(q), with the manifest naming the mask.

## 0.15.0

- **The mask now reaches the 1D curve.** Panel D's re-integrated trace was gated
  on the hot-pixel toggle, so with hot-pixel removal off a mask changed the 2D
  panels and left I(q) exactly as it was. It is now built whenever the frame has
  a q–φ map, and it answers to everything: the reduction's own mask, the
  detector defects, and every region excluded by hand. Verified on CMS data —
  a ring masked at q 1.9–2.05 turns all 19 bins inside it to NaN and leaves
  every bin outside bit-identical, and a polygon drawn in (qx, qz) changes
  exactly the 91 q bins it geometrically covers, q 1.134…1.836.
- **A masked region is a gap, not a zero.** Every stage writes NaN, and the
  average is a `nanmean` down each q column, so an excluded pixel drops out of
  its bin rather than dragging the bin towards zero. A q column with nothing
  left comes back NaN.
- **Sector averages.** *Re-integrate φ min/max* under panel D narrows the
  azimuth the curve is averaged over; blank means the whole map, which is what
  keeps it comparable with the circular average on disk. The trace names what it
  carries and a caption reports how many q–φ pixels were excluded and how many
  q bins were left empty.
- A line cut over a map whose shape matches neither axis now skips quietly
  instead of taking the page down with an `IndexError` out of numpy.

## 0.14.2

- **Fixed `StreamlitValueAssignmentNotAllowedError` on the GIWAXS explorer.** A
  chart created with `on_select` is a widget like a button: it refuses
  assignment through `st.session_state`, and it refuses it at *widget creation*,
  so `keep_widget_state` re-asserting the key killed the page on its second
  render. `action_key` could not help — the chart registers itself far too late
  in the script — so keys ending `_chart` are now skipped by rule, which is
  order-independent and covers the next selection chart somebody adds.
- Drawing a mask region is now an explicit **✏️ Draw on the panels** toggle
  rather than a hidden modebar tool; it swaps the two 2D panels from
  drag-to-zoom to drag-to-select and lays an invisible point grid over the
  heatmap for the selection to latch onto. Note the numeric ring/wedge/box form
  is the reliable route — see the note in the panel.

## 0.14.1

- **The qr–qz view uses its own qz.** A q_image NPZ can now carry two remeshes
  of the same frame — pySAXSAI's `qimg_x_axis` takes a list, so `['Qx', 'Qr']`
  writes `qimg`/`qx` alongside `qrimg`/`qr`. The two do not land on the same
  grid (on a CMS GIWAXS frame the qz axes start at −2.77582 and −2.77829 Å⁻¹),
  so the **B x-axis** control now reads `qrimg_qz` when the reduction wrote one
  and only falls back to the shared `qz` when it did not.

## 0.14.0

- **Exclusion masks.** A substrate Bragg peak or a specular rod is real signal,
  not a defect, and often still needs to be out of an average — so masks are now
  authored rather than detected. Add a **ring** (|q| band), a **wedge** (φ band)
  or a **box** by number, or **box/lasso-select straight on the q-image or the
  q–φ map** and press *Add to mask*: Streamlit hands the selection back in data
  coordinates, so the shape is stored in q and survives a change of frame or
  zoom.
- **One definition, every product.** A polygon drawn in (qx, qz) is converted
  for the (q, φ) map, so the same region excludes the spot on the picture, in
  the line cuts, in the re-integrated 1D curve and in the batch export.
- Masks are JSON in `~/.pyscattviz/masks/`, so they reload next session and
  apply across a batch. Regions can be suspended without being deleted, and
  *Keep only these regions* inverts the set.

## 0.13.0

- **Finding hot pixels now does something to the 1-D curve.** The toggle blanked
  them in the 2D panels and the line cuts, but panel D showed the reduction's
  own `Cir_Avg` CSV read from disk — computed before anyone looked at the data,
  with every hot pixel baked in — so removal appeared to do nothing. The panel
  now overlays **I(q) with the hot pixels removed**, re-integrated from the q–φ
  map over the full azimuth so it is comparable with the curve on disk, and the
  despiked table is offered in the save panel. On one CMS MAXS frame the real
  defects move I(q) by up to **19%** at q = 3.87.
- **Vote across frames, from the explorer.** The persistence test was only in
  batch export. "Blank only pixels that recur across the selection" builds a
  defect mask from an evenly spread sample of the filtered frames and uses it
  for the 2D panels, the line cuts and the re-integrated curve. It matters: on
  `ACDM_SiWafer_100nm_s3 th0.080` the single-frame test flags 36 pixels and only
  4 recur. The brightest six are a contiguous 8×6 Bragg peak rising smoothly
  from 300 to 38,035 counts — blanking those deletes the measurement.
- A fully masked q column no longer prints a *Mean of empty slice* warning into
  the page; it was always NaN by construction.

## 0.12.1

- **The q-image opens on what the frame actually covers.** The CMS GIWAXS
  preset pinned qx to 0–3 Å⁻¹ and switched auto-fit off with it. On a
  Pilatus800 whose active area starts about 300 px left of the beam centre the
  remesh covers qx −2.18 … +1.23, so that window drew a band of blank above
  1.23 and hid the whole negative side, where most of the data is. Auto q
  limits now win on arrival even where a beamline preset exists — coverage is
  the detector's business, not a preference — and the preset still fills the
  boxes, so unticking gives it back in one click.
- **Every frame says what it covers**, measured from the frame and shown under
  the limit boxes: *This frame covers qx −2.18 … +1.23 · qz +0.16 … +2.78 · …*.
  A hand-typed window that misses the data now says so rather than drawing an
  empty panel.

## 0.12.0

- **The folders you use are remembered between sessions**, in
  `~/.pyscattviz/data_folders.md`. Open a folder once and it is already in the
  box the next time you start the application; every folder you have opened is
  in the menu. It is markdown rather than JSON on purpose — a list of data
  folders is something you want to read, annotate and paste into an email, so
  each line carries an optional note of your own and the date it was last used.
  Edit the file by hand and pyScattViz reads the change; the parser accepts what
  a person would actually type, with or without backticks, notes and dates.
- Folders can be **pinned** (offered first, never aged out), **annotated**, or
  **forgotten**, from the "Remembered folders" panel under the folder box. A
  remembered folder whose mount has gone is kept in the file but is not opened.
- The file lives in the per-user configuration folder, never inside a
  repository, so a path to an embargoed proposal cannot be committed by
  accident.

## 0.11.1

- **Auto-fit is two switches, not one.** "Auto q limits" and "Auto intensity
  limits" are now independent, because the useful combination is the mixed one:
  pick a q range by hand and let the intensity follow it. The intensity limits
  are measured from the points *inside the q window actually on screen*, so
  zooming into 0.05–0.15 Å⁻¹ on a CMS SAXS frame rescales I from 0.0013–3246 to
  1.3–95 instead of leaving the part you asked for as a flat line along the top
  of a panel scaled to the full four decades.
- **The hot-pixel thresholds are on screen.** A hot pixel is not a well-defined
  object — whether a pixel is a detector defect or the brightest point of a
  sharp reflection depends on a threshold, and that is the user's call. The
  neighbourhood size, the significance in σ, the multiple of the local median
  and an optional counts floor are all adjustable, with Default / Strict /
  Loose presets, and the panel reports how many pixels the present settings
  would blank on the frame on display and how bright the worst of them was. On
  Jiaen's GIWAXS frame the same frame gives 57, 25 or 7 removed pixels as the
  thresholds tighten; the count is the only honest way to judge a setting.
- **Batch export can build one defect mask from the whole selection.** A first
  pass over an evenly spread sample of the frames keeps only the pixels that
  recur, and that single mask is then applied to every frame. This is the test
  that separates a detector defect from a Bragg spot, so it is the honest way
  to despike a batch. On 756 q–φ maps from one CMS beamtime it converges on the
  same 16 pixels whether the sample is 6 frames or 24.
- The stack finder streams its frames instead of materializing them, so a
  thousand-frame mask costs one vote array rather than gigabytes.

## 0.11.0

- **Fixed the blank q–φ panel.** Plotly wants a log axis's range in log10 units,
  and the heatmap builder was passing raw q. A window of 0.001–0.5 Å⁻¹ was drawn
  at 10^0.001–10^0.5, i.e. 1–3 Å⁻¹, past the end of any SAXS dataset — so the
  panel came out empty on every log-q geometry (transmission SAXS and GISAXS)
  while GIWAXS, which is linear in q, looked fine.
- **The transmission layout packs itself.** Only the panels that are selected
  *and* present for the frame are drawn, two to a row. The old fixed A/B/C/D
  grid always reserved four slots, so transmission data — which has no stitched
  raw image — opened with an empty first cell. Products that are selected but
  absent are named in a caption instead of leaving a hole.
- **Smart 1D limits.** The q and intensity limits for I(q) are measured from
  where there is signal. A CMS SAXS file runs to q = 0.31 Å⁻¹ but the intensity
  has fallen from 1600 to 0.01 by q = 0.25, and it starts at 0.0056, not the
  0.001 the fixed window assumed — so most of the panel was empty decades.
- **Hot-pixel removal on the 2D products.** Every CMS/SMI detector has a few
  pixels that read absurdly high whatever the sample, and since the azimuthal
  average is a mean, one 500,000-count pixel moves a whole q bin. `despike.py`
  blanks them, on the q-image and q–φ maps, in the line cuts, and in the batch
  export. On by default.
- **Batch export of despiked 1D curves.** The explorers can now re-integrate
  every filtered frame's q–φ map over an azimuthal window with the hot pixels
  removed, writing one CSV per frame — the reduced curve without the spikes.
  The reduction's own circular average is computed before anyone has looked at
  the data, so a hot pixel is baked into it.

## 0.10.0

- **Settings survive switching tabs.** Streamlit discards a widget as soon as
  its page stops being rendered, so leaving the explorer and coming back threw
  away the colour map, the q limits, the filters — everything just set. Every
  page now keeps its state, sixty previously unkeyed widgets have stable keys,
  and a remembered choice whose options have changed is snapped back to a real
  one. Verified in a browser: set a filter, a colour map and a q limit, navigate
  away, come back, all three still there.
- CMS GIWAXS opens on qx and qz over 0–3 Å⁻¹, q–φ over q 0.5–3.5 and φ 0–180°.
  The preset follows the data: point the explorer at a CMS folder and it
  applies, point it at SMI and that one does.
- **Auto-fit for the blank q-image.** A remeshed q-image covers only part of the
  qx–qz plane and the rest is NaN, so a fixed window left SMI GISAXS stranded in
  a field of blank. The limits are now measured from the pixels that actually
  hold data — SMI GISAXS frames on ±0.21 in qx and −0.31…0.16 in qz instead of
  ±0.5 and 0…0.5, which also recovers the negative qz a 0-based minimum hid.
  On by default wherever there is no explicit beamline preset; φ is left alone.
- A φ line-cut profile opens on 0–180° again, matching the q–φ panel above it.
- **Publication Plot has the whole of matplotlib.** Per curve: colour, line
  style, width, marker, marker size, marker spacing, opacity and label, edited
  in a table. For the axes: x and y limits, labels, a stacking multiplier, base
  font size, major and minor grids with opacity, minor ticks, tick direction,
  length and width, ticks on the top and right, frame width, and legend
  position, columns, font size and box.

## 0.9.0

- Every plotting page can now hand over **the Python behind the figure on
  screen** — Quick Plot's 1D overlay, stacked map and 2D image, the Publication
  Plot, and the explorer panels. The script uses only the public API, writes out
  the file paths, and runs unchanged in a notebook or a terminal. Each generator
  is executed in the test suite, because a snippet that raises on the first line
  is worse than no snippet.
- Added a **Python Console** page. Write and run your own code against the data
  the session already has: `basket` is the current file list, `folder` the
  active data folder, and the readers, plotting API, and save helpers are
  already imported. A trailing expression is echoed as in a notebook, printed
  output is captured, matplotlib and Plotly figures and DataFrames are rendered,
  and names persist between runs. Four worked examples are built in.
- Generated code can be downloaded, saved beside the figures, or opened straight
  in the console with one button.
- The console refuses to run anything when the server has been bound to an
  address other people can reach. pyScattViz listens on 127.0.0.1 by default;
  running code typed into a browser is only reasonable when the browser is
  yours.

## 0.8.0

- Added a **Terminal** page. `ls`, `cd`, `cat`, `head`, `tail`, `find`, `wc` and
  `du` over any mounted or local folder, all parsed here and implemented with
  `pathlib` — nothing is handed to a system shell, so there is no way to spell
  `rm`. `select *UV_20* *UV_30*` builds a list, `unselect *AgBH*` trims it, and
  `save <name>` keeps it. That list *is* the dataset basket, so it appears
  straight away in Quick Plot, Publication Plot, and the explorers.
- Fixed choosing a data folder in the explorers. One mounted drive normally
  holds many proposals, beamlines, and projects; the old single box cleared
  whatever was typed as soon as the path was not yet available, so a typo could
  not be corrected, and it never translated an original `/nsls2/...` path
  through the registered mounts. Every explorer and Publication Plot now share
  one picker: a menu of the folders the session knows, a box that keeps what you
  type, and mount translation.
- Replaced the AND-only keyword box with **must contain / may contain / must not
  contain**, on all four explorers and on Publication Plot. Asking for two
  samples at once — `UV_20, UV_30` in the *may contain* box — had no answer
  before.
- The **QC image** panel now starts unchecked. It is the reduction's own
  diagnostic picture rather than the data under review, and drawing it slowed
  every frame change on a mounted folder.
- GIWAXS opens on the window actually reviewed: q-image qx and qz over 0–5 Å⁻¹,
  I(q) over 0–5 Å⁻¹, and φ over 0–180°. **Fit to this frame** still opens the
  limits to whatever the frame really covers, and **Clear back to auto** now
  genuinely blanks them.

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
