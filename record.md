# pyScattViz development handoff

Read this file before continuing work after a chat, terminal, or development
session restart. It records what has been done, decided and verified;
[plan.md](plan.md) holds what is still to do. It deliberately contains no
passwords, Duo codes, tokens, or private keys.

## Repository state

- Repository: `https://github.com/yugangzhang/pyScattViz`
- Branch: `main`
- Current package version: `0.22.0`
- The Windows launcher `start_windows.bat` was confirmed working by the user.
- `0.22.0` was written on 2026-10-18 on top of `ef69663` (`0.21.0`) and was not
  yet committed when this file was last updated; committing it is the first
  step of `plan.md`. Confirm with `git status` and
  `git log -5 --oneline --decorate`.
- The handoff file was `recorde.md` until `0.22.0`; it is `record.md` now.

## User goal and verified access

Most users will run pyScattViz on Windows. The goal is to explore scattering
data — a mounted NSLS-II proposal, a copied subset, or a folder already on the
local disk — without copying a complete proposal to the local computer.

The user verified this direct connection from Windows PowerShell:

```powershell
sftp username@sftp.nsls2.bnl.gov
```

BNL password plus Duo Push succeeded, and this remote result folder was listed:

```text
/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx/projects/myproject/Results/giwaxs
```

It contains `cir_avg`, `q_image`, `qc`, and `qphi`. No jump host was needed for
this proposal-storage SFTP connection.

The server's observed ED25519 fingerprint is:

```text
SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE
```

The user then verified the free RaiDrive client on Windows. BNL password and
Duo succeeded, the SFTP storage appeared as `Z:`, proposal folders were
browsable, and the account's write permission was confirmed by creating a test
folder. pyScattViz should nevertheless recommend read-only mounting for review.

**Not yet verified by anyone:** rclone against the BNL Duo prompt, and SSHFS on
macOS. Both are documented as free alternatives with that status stated openly
in the GUI and the README. Do not upgrade the wording without a real test.
Both need a Windows or macOS machine and the BNL credentials, so they cannot be
closed from here.

**Real reduction output is on this machine** at
`~/Repos/pySAXSAI/results/{cms,smi}/<geometry>/<dataset>/` with `cir_avg`,
`q_image`, `qphi`, and `qc`, covering CMS gisaxs/giwaxs/maxs/gimaxs/saxs/waxs
and SMI gisaxs/giwaxs/tsaxs/twaxs. Real beamtime trees are under
`/mnt/data32/NSLSII_Data/{CMS,SMI}/<cycle>/`. Test against these before assuming
a layout — every 0.7.1 fix came from doing so. Note that several of those result
folders hold only AgBH calibration frames, which the default filter hides.

## Current design decisions

1. pyScattViz reads only normal local or mounted filesystem paths.
2. The GUI must never request or store a BNL password, Duo response, token, or
   private key.
3. Interactive authentication must happen in a real terminal or desktop SFTP
   mount client. The GUI may generate commands, explain setup, validate a mount,
   and save path mappings.
4. Three access routes are first-class and all free: mount (RaiDrive on Windows,
   SSHFS on macOS/Linux, rclone anywhere, GVFS on a GNOME desktop), copy a
   subset (`sftp -r`, `rclone copy`, FileZilla, Cyberduck), and a folder already
   on the local disk.
5. RaiDrive is Windows-only and the README says so explicitly, because users on
   macOS and Linux were otherwise left looking for it.
6. Native Windows SSHFS-Win password mounting is not recommended because it
   could not complete BNL keyboard-interactive Duo authentication (`net use`
   ended with system error 67). Do not repeat that path unless key-based access
   has first been arranged with NSLS-II support.
7. Proposal scope is the safest default. Authorized staff may instead mount a
   beamline proposal root, `/nsls2/data`, or a validated custom subpath.
8. GISAXS, GIWAXS, transmission SAXS, and transmission WAXS have independent
   pages and scientific defaults.
9. Data selection uses AND / OR / EXCLUDE term lists, matching the `ls_dir`
   semantics from pyScatt, over folders as well as files.
10. Saving is to the user's own folder, one subfolder per page, never silently
    overwriting. Browser downloads are kept as a secondary route.
11. Streamlit-free modules (`discovery`, `datasets`, `dataio`, `exporting`,
    `mounts`, `filters`, `publication`, `plotting`, `products`, `org`) hold the
    logic so it stays testable and usable from notebooks.
12. Every loader raises one catchable `DataReadError`. A corrupt file must
    report itself and leave the rest of the page working; it must never raise
    a bare `EOFError`, `BadZipFile`, or `EmptyDataError` into Streamlit.
13. Axis limits open on the per-geometry review window Yugang asked for (GIWAXS:
    q 0–5, φ 0–180). `frame_axis_ranges` backs "Fit to this frame" for when a
    map looks cut off — real SMI GIWAXS reaches 7 A^-1 where CMS reaches 3 — and
    "Clear back to auto" blanks the boxes. Do not silently widen the defaults
    again; offer the button instead.
14. `st.plotly_chart` has no `width` parameter in Streamlit 1.50 — use
    `use_container_width=True`. `st.dataframe` and `st.pyplot` do take `width`.
15. Documentation and GUI placeholders never name a real experiment. Use `xxx`
    for the beamline, `xxxxxx` for the proposal, `myproject` for the project
    folder, and `username` for the BNL account. Only `yuzhang@bnl.gov` as the
    public contact address stays.
16. Filtering is always must-contain / may-contain / must-not-contain, in that
    order, on every page. An AND-only box cannot express "UV_20 or UV_30", which
    is the commonest request.
17. The Python Console runs the user's code in-process on purpose; that is the
    feature. The one guard that matters is `is_local_only` — do not remove it,
    and do not let the page render its editor on a non-loopback bind.
18. Every input widget must have a `key`, or its value cannot survive a page
    change — Streamlit stores an unkeyed widget under an internal id that never
    appears in `session_state`. `tests/test_state_persistence.py` fails if any
    unkeyed widget is added. Buttons, downloads and uploaders are the exception:
    they must go through `action_key` so `keep_widget_state` leaves them alone,
    since they reject assignment at widget-creation time.
19. Because values now persist, a remembered choice can outlive its options. Use
    `coerce_choice`/`coerce_choices` wherever the options depend on the data.
20. Plotly takes a **log** axis range in log10 units. `axrange` does this;
    `heatmap_fig` did not, which drew every log-q q–φ panel at 1–3 A^-1 and left
    it blank. Any new axis-range code must go through `axrange`.
21. Panels are packed, not slotted. Draw only what is selected *and* present, or
    a missing product leaves a hole — transmission data has no stitched raw
    image, so the old fixed grid always opened with an empty first cell.
22. Renaming a shipped file needs the `setup.py` shim to keep working: pip
    builds a local directory in place and setuptools never removes files from
    `build/lib`, so a rename otherwise ships both names. For pages that is fatal
    — Streamlit rejects two pages with the same inferred URL. `cli.py` also
    repairs an installation that already has both.

23. Naming a folder opens nothing. Registering or typing a path may scan
    directory entries and nothing else; the first byte of data is read only
    after a frame or file is chosen. Every viewing page therefore opens on an
    empty picker — `index=None` with a placeholder for a selectbox, `default=[]`
    for a multiselect — and stops there with the catalogue on screen. A
    single-frame folder is no exception: an auto-pick "because there is only
    one" is what makes the rule impossible to rely on. `coerce_choice(...,
    default_index=None)` is the version to use for a file picker;
    `render_frame_picker`/`render_frame_catalog` in `components/frames.py` are
    the shared gate for the four explorers. `tests/conftest.py` holds
    `open_frame`/`choose_file`/`choose_files`, which a page test must call
    before it can assert on any panel.
24. A product folder is matched by name **ignoring case and word separators**,
    and each product carries the aliases the beamlines actually use. CMS writes
    `cir_avg`, `q_image`, `qphi`, `qc`, `stitched` from one pipeline and
    `Qimage`, `Raw_Plot` from the grazing-incidence one; SMI's stitching
    pipeline writes `Cir_Avg`, `Stitch_Data`, `Check_Stitch`, `Stitch_Image` and
    `Raw_Plot` for the same things. Hard-coding `root / "cir_avg"` meant that on
    a case-sensitive mount an SMI GIWAXS folder showed exactly one product, and
    `Qimage` — one underscore away from `q_image` — showed none. Case and
    separators are the only thing that ever varies, so `fold_folder_name` in
    `discovery.py` normalises both away and one rule replaces a growing list of
    spellings. The aliases live in `SCATTERING_PRODUCTS[...]["folders"]` in
    `components/scattering.py` and in `PRODUCT_FOLDERS` in `discovery.py`
    (`is_product_folder` is the test); `product_folders(root)` resolves them in
    one `scandir`. A product is always shown under the name it has on disk —
    "q-image" tells nobody they are looking at `Stitch_Data`. A new filename
    prefix must also be added to `_PRODUCT_PREFIXES`, which `stem_of` strips
    longest-first so `Stitch_Data_qx_` cannot be mistaken for `Stitch_Data_`.
25. A rendered figure is displayed, not re-plotted. `Stitch_Image`, `Raw_Plot`,
    `Check_Stitch` and CMS `qc` hold PNGs the reduction already drew, so they go
    to `st.image` with the read error caught and reported; only detector and
    q-space arrays go through the heatmap renderer. `Stitch_Data` and `Qimage`
    are the exception that proves it: a float32 TIFF carrying real data, whose
    qx/qz axes live in sibling `*_qx_*` / `*_qz_*` CSVs, loaded by
    `_load_stitched_qimage` — which finds the axes by stem, so it does not care
    which of the two folders it is in. Row 0 is the lowest qz in both, verified
    against each reduction's own rendering, so the map goes to Plotly unflipped.
    A rendered PNG sitting *inside* `Qimage` is neither the map nor a frame of
    its own; the `q_image` patterns only take `.npz`/`.tif`/`.tiff`.
26. An experiment is followed as an **org**: a pyDataOrg organiser kept as one
    JSON file, with the data folder it was made of recorded under
    `project.extensions.pyscattviz.source` (layout, root, options). Kept
    beside the data (`<proposal>/Org/`), that root is relative to the file, so
    the org opens wherever the proposal is mounted; reopened, it links the
    frames written since and keeps what the user added. pyDataOrg is the
    optional extra `[org]` — every Org page also works on a folder alone (a
    `Source` in `svorg_source`), and `store.create_org` says how to install
    it. A folder is read by a *layout* (`org/layouts.py`): `cms`, the CMS
    `<folder>/<detector>/{raw,analysis}` tree with names parsed in
    `org/cms.py`, or `products`, any product folders with names read by a
    regular expression. The product-folder rules moved out of
    `components/scattering.py` into `products.py` so that reading a folder
    imports no Streamlit — `tests/test_org_store.py` checks that in a
    subprocess; `scattering.py` re-exports the names it always had.
    **Ask AI** (`org/ask.py`) runs the user's own command-line tool (codex,
    claude, gemini, ollama, or what `~/.config/pyScattViz/ask.json` lists) on
    the org's names and counts only — never data, never a path — and nothing
    it says is written anywhere. A model may *propose* how to read a folder;
    `parse_proposal` checks it and the user builds the org. Ask is off behind
    a password unless `--ask` turns it on: a model bills whoever runs the
    server. The config names environment variables, never keys. Org page keys
    start `svorg_`; a frame slider must go through `controls.pick_frame`,
    because a value from a longer run otherwise raises
    `StreamlitValueAboveMaxError` when a shorter one is chosen.
27. The Org plot pages carry the explorers' controls, built in
    `components/org/controls.py` (`display_options`, `ranges`,
    `curve_controls`) and honoured in `figures.py`. Limits are `(lo, hi)` with
    either side None for auto, and auto is not Plotly's: `image_limits` frames
    a map on the box holding data and scales its colour on the window shown,
    `curve_limits` frames curves on the points that can be drawn and fits I to
    the q window. So a blank box is the useful default and **Fit** only fills
    the boxes in to be edited. An org being measured is reopened, not remade:
    `state.SAVED` counts the frames the file links when it is opened or saved,
    `state.unsaved()` the difference, `state.update_org()` rescans, links and
    saves. The *Known folders* menu moves the folder box only through its
    `on_change`; comparing the two on every rerun reverted any pasted path.

Commit messages are written in my own voice and carry no assistant
co-author trailer.

## Application workflow

1. Open **Data Sources & Mounts**. Choose the mount scope and enter beamline,
   cycle, proposal, and BNL username as needed.
2. Choose the platform and the access method. The page generates the exact
   command; complete password/Duo authentication outside the browser.
3. Return to the GUI, enter the mounted or local path, select **Test this
   folder**, then **Register folder for the other pages**.
4. Open **Data Selection**. Enter search roots and the AND/OR/EXCLUDE term
   lists, or paste full paths. Tick results into the dataset basket and,
   optionally, save the basket under a name.
5. Open **File Selection** for reduced products, or **Quick Plot** for anything
   else. Both read only names until a file is chosen.
6. Open the geometry-specific explorer. Array data are opened only for the
   active frame.
7. Save any panel, cut, or figure to the output folder from the page itself.

Configuration written by the application, paths and preferences only:

```text
~/.pyscattviz/path_mappings.json
~/.pyscattviz/collections/*.json
~/.pyscattviz/settings.json
```

Default output root: `~/pyScattViz_Output`, overridable with
`PYSCATTVIZ_OUTPUT_DIR`. Configuration root overridable with
`PYSCATTVIZ_CONFIG_DIR` (the test suite relies on this).

## Windows update and launch commands

Run these commands from PowerShell in the existing repository:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install --upgrade .
.\start_windows.bat
```

Do not use `python3`, `.venv/bin/python`, or `.venv/bin/pyscattviz` on Windows.
Do not recreate `.venv` after every pull when
`.\.venv\Scripts\python.exe --version` already works.

## Important files

Core logic, all Streamlit-free:

- `src/pyscattviz/discovery.py`: `ls_dir`, `find_folders`, `find_files`,
  `classify_folder` — the AND/OR/EXCLUDE selection engine.
- `src/pyscattviz/datasets.py`: dataset basket persistence and named collections.
- `src/pyscattviz/dataio.py`: universal readers for curves, arrays, and images,
  including the delimiter/header sniffer and `stack_curves`.
- `src/pyscattviz/exporting.py`: output root, per-tab folders, safe names,
  non-overwriting saves for figures, tables, arrays, and text.
- `src/pyscattviz/mounts.py`: proposal validation plus SSHFS, rclone, GVFS, and
  `sftp -r` command generation and the per-platform method registry.
- `src/pyscattviz/filters.py`: the boolean filename expression language.
- `src/pyscattviz/codegen.py`: turns GUI state into a runnable script. Pure text
  generation, and every generator is executed in `tests/test_codegen.py` — a
  snippet that raises on the first line is worse than none.
- `src/pyscattviz/console.py`: notebook-style execution of a snippet, plus
  `is_local_only`, which gates the console on a loopback bind address.
- `src/pyscattviz/despike.py`: hot-pixel detection and removal on the *reduced*
  2D products. Deliberately not raw-frame reduction — that is pySAXSAI's
  `codes/hot_pixels.py`, one step earlier. Two conditions, both required:
  significance against counting statistics, and a multiple of the local median.
  The second is what stops a steep gradient being read as a spike; a
  global-MAD-only version flagged a pixel sitting at 1.0x its neighbours on real
  CMS data. Build masks from frames spanning *different samples* — a majority
  vote over one sample's angle series flags that sample's Bragg spots.
- `src/pyscattviz/shell.py`: the read-only terminal. Every verb is parsed and
  carried out with `pathlib`; nothing reaches a system shell. `select`/`save`
  build the same named collections Data Selection reads.
- `src/pyscattviz/data_sources.py`: persistent remote-to-mounted path mapping.
- `src/pyscattviz/products.py`: `SCATTERING_PRODUCTS`, `product_folders`,
  `stem_of` — which folder holds which product, and the frame a file is of.
- `src/pyscattviz/org/cms.py`: a CMS experiment read from its names — frames,
  raw-against-reduced progress, samples, in-situ runs, the pyDataOrg links.
- `src/pyscattviz/org/layouts.py`: the `cms` and `products` layouts,
  `detect_layout`, `describe_tree` (what a model is shown of a folder).
- `src/pyscattviz/org/store.py`: `Source`, `create_org`/`open_org`, the org's
  name and suggested place, recent orgs.
- `src/pyscattviz/org/ask.py`: the models, the context a question is asked
  with, `ask`, and `propose_source`/`parse_proposal`.
- `src/pyscattviz/org/analysis.py`: a peak's area, position and width along a
  run.

Streamlit layer:

- `src/pyscattviz/app/pages/01_Data_Sources_and_Mounts.py`: platform + method
  chooser, generated commands, validation, registration.
- `src/pyscattviz/app/pages/02_Data_Selection.py`: term-list search, paste,
  basket, saved collections.
- `src/pyscattviz/app/pages/03_File_Selection.py`: mounted/local browsing and
  lazy filename selection.
- `src/pyscattviz/app/pages/08_Quick_Plot.py`: 1D, stacked map, 2D for any path
  list.
- `src/pyscattviz/app/pages/11_Output_Folder.py`: output root and saved files.
- `src/pyscattviz/app/components/datasource.py`: the folder picker and the
  AND/OR/EXCLUDE boxes shared by the four explorers and Publication Plot. The
  picker keeps what was typed even when the path is unavailable — the old box
  cleared it, so a typo could not be corrected.
- `src/pyscattviz/app/pages/12_Terminal.py`: the terminal, wired to the basket.
- `src/pyscattviz/app/components/saving.py`: the shared save panel every page
  uses. Note the `_root_input` re-seeding trick — several output-root boxes are
  on screen at once and must not fight over the value.
- `src/pyscattviz/app/components/files.py`: cached loaders keyed on file mtime,
  and `collect_files` which expands a mixed basket into a file list.
- `src/pyscattviz/app/components/batch.py`: export one panel for every filtered
  frame. It calls `frame_panel_figure` in `scattering.py`, which rebuilds a
  panel for a frame that is not on screen; the interactive pages keep their own
  panel code because they also draw line-cut bands and per-curve styling.
- `src/pyscattviz/app/components/grazing_explorer_page.py` and
  `transmission_explorer_page.py`: shared renderers with independent profiles.
- `src/pyscattviz/app/pages/14_Org.py` to `19_Ask_AI.py`: make or open an
  org, then Overview, Sample, Compare, In-situ, and Ask AI. They share
  `components/org/state.py` (the open org or folder, `PYSCATTVIZ_ORG`, the
  15 s re-read, saving), `controls.py` (folder, sample, angle and frame
  pickers; the explorers' display row and ranges) and `figures.py` (the maps
  and curves, framed and scaled on what they show).

Tests:

- `tests/test_discovery.py`, `tests/test_datasets.py`, `tests/test_dataio.py`,
  `tests/test_exporting.py`, `tests/test_files_component.py`: the new core.
- `tests/test_mounts.py`: proposal paths and every generated command.
- `tests/test_data_selection_page.py`, `tests/test_quick_plot_page.py`,
  `tests/test_saving_page.py`, `tests/test_batch_export.py`,
  `tests/test_app_smoke.py`: GUI regression.
- `tests/test_corrupt_files.py`: a result folder holding a zero-byte CSV, a
  truncated npz, and a PNG that is not an image. Every page must survive it.
  This is not hypothetical — an interrupted reduction or a dropped mount
  produces exactly these files.
- `tests/test_end_to_end.py`: register a folder, search it with term lists,
  fill and save the basket, plot it, and write a figure. This is the journey a
  collaborator actually takes; the per-page tests do not check that the state
  they hand each other lines up.
- `tests/test_axis_ranges.py`: the measured limits, plus a check against the
  real CMS/SMI products when they are present (skipped when they are not).
- `tests/test_real_layouts.py`: the CMS QC layout tags, the deterministic QC
  choice, the calibration-only message, the absence of the Streamlit
  deprecation warning, and the SMI stitched layout — its five product folders,
  its filename prefixes, the axes read from the sibling qx/qz CSVs, and the
  GIWAXS explorer drawing the panels for such a frame. The CMS `Qimage` layout
  is covered the same way, down to the rendered PNG in the map's own folder.
- `tests/org_experiment.py`: a small CMS experiment written to disk (static,
  humidity and spin-coating folders, a repeat, an unreduced frame, a dead T
  sensor). `tests/test_org_cms.py`, `test_org_store.py`, `test_org_ask.py`
  and `test_org_pages.py` run on it; a model is a stand-in Python script.
  `tests/test_org_figures.py` checks the auto limits on arrays.
  The org tests that need pyDataOrg skip without it.

## Last verification

The `0.22.0` implementation passed, with pyDataOrg importable and
`PYSCATTVIZ_CONFIG_DIR`/`PYSCATTVIZ_OUTPUT_DIR` pointed at empty folders
(three `test_app_smoke.py` tests otherwise read `~/.pyscattviz/settings.json`;
see `plan.md`):

```text
python -m pytest -q           661 passed, 4 skipped
python -m ruff check src tests
python -m ruff format --check src tests
git diff --check
```

The wheel was last checked at `0.21.0` (`python -m pip wheel . --no-deps`: the
org package, products.py and pages 14–19 are in it); no file was added to or
moved out of the package since. The Org pages were also run on two real CMS
experiments, a static and humidity GIWAXS one and a static and thermal
transmission SAXS one (3,089 frames, 44 heated runs): every page draws with no
error and every axis opens framed on its data.

Figures were confirmed written to disk from Quick Plot, the four explorers, and
Publication Plot, each landing in its own page subfolder, with PNG produced
through kaleido and HTML produced without it.

The SMI layout was checked against a real stitched GIWAXS beamtime
(`.../pass-xxxxxx/Results/WAXS`, 1,296 frames): all five product folders are
discovered, every frame carries a stitched image, a raw plot, a `Stitch_Data`
q-map and a circular average, the two `Check_Stitch` figures attach to the two
frames they belong to, and the 3009x2180 float32 map loads with its 2,180-point
qx and 3,009-point qz axes.

The CMS `Qimage` layout was checked against a real grazing-incidence beamtime
(`.../experiments/1_gi_static/saxs/analysis/GISAXS`, 935 frames): `Qimage` and
`Raw_Plot` are both found, every frame has a q-map and a raw plot, and the
1679x1475 float32 map loads with its qx and qz axes. Its orientation was
confirmed by re-rendering the TIFF with row 0 at the lowest qz and matching the
asymmetric detector-gap streak against the reduction's own PNG.

The `smi` layout (2026-10-21) was checked against the four SMI projects of
`pass-321337` (read-only from the sandbox): it recognises each `Results`
(and a group's folder below it, `TSAXS384/Results/UPenn`), and reads QYu as
8 samples of group `QYu` in 336 frames (0.3 s), HZheng 17 in 290, PGuo 43 in
5,201 (1.9 s), UPenn 111 in 2,886. The strategy it reads back matches the run
sheets: QYu GI at 7 angles, WAXS arcs 0, 20, 40, SAXS at 40, 3 spots at
−1000, 0, +1000 µm, 16.15 keV, 1 s (`2026C3_HZheng.py`'s `GI`); HZheng 9
spots on a 3 × 3 grid; UPenn a 13-point cross of ±900 µm; PGuo 12 angles,
5 spots. A QYu org built from it into the scratchpad was 512 KB and opened
again with its record. The live GUI was not run on it.

## Open work

What is still to do, in order, is in [plan.md](plan.md). When an item there is
done, move its evidence here and take it out of the plan.

## Closed, with evidence

Closed in `0.7.1`:

- Data Selection was run over the real SMI beamtime tree at
  `/mnt/data32/NSLSII_Data/SMI/2026_Cycle1`: 235 folders at depth 6 in about one
  second, caps reported rather than silently applied. The depth and result caps
  behave.
- Quick Plot was run over real CMS and SMI products, including an overlay mixing
  the two beamlines, and wrote a PNG from CMS GISAXS circular averages.
- The q defaults were measured against real output and replaced with
  scale-to-frame limits plus a preset button; see decision 13.

## Suggested prompt for a new chat

```text
Please continue pyScattViz from the repository. First read README.md,
record.md and plan.md completely, then inspect git status and recent git log.
Keep the GUI mount-only and credential-free, and keep the core modules
Streamlit-free.
```
