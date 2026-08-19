# pyScattViz development handoff

Read this file before continuing work after a chat, terminal, or development
session restart. It deliberately contains no passwords, Duo codes, tokens, or
private keys.

## Repository state

- Repository: `https://github.com/yugangzhang/pyScattViz`
- Branch: `main`
- Current package version: `0.7.0`
- The Windows launcher `start_windows.bat` was confirmed working by the user.
- At the end of this handoff update, `main` is expected to be committed, pushed,
  and clean. Confirm with `git status` and `git log -5 --oneline --decorate`.

## User goal and verified access

Most users will run pyScattViz on Windows. The goal is to explore scattering
data — a mounted NSLS-II proposal, a copied subset, or a folder already on the
local disk — without copying a complete proposal to the local computer.

The user verified this direct connection from Windows PowerShell:

```powershell
sftp yuzhang@sftp.nsls2.bnl.gov
```

BNL password plus Duo Push succeeded, and this remote result folder was listed:

```text
/nsls2/data/smi/proposals/2026-2/pass-319371/projects/microbeam_Kim/Results/giwaxs
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
    `mounts`, `filters`, `publication`, `plotting`) hold the logic so it stays
    testable and usable from notebooks.

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
- `src/pyscattviz/data_sources.py`: persistent remote-to-mounted path mapping.

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
- `src/pyscattviz/app/components/saving.py`: the shared save panel every page
  uses. Note the `_root_input` re-seeding trick — several output-root boxes are
  on screen at once and must not fight over the value.
- `src/pyscattviz/app/components/files.py`: cached loaders keyed on file mtime,
  and `collect_files` which expands a mixed basket into a file list.
- `src/pyscattviz/app/components/grazing_explorer_page.py` and
  `transmission_explorer_page.py`: shared renderers with independent profiles.

Tests:

- `tests/test_discovery.py`, `tests/test_datasets.py`, `tests/test_dataio.py`,
  `tests/test_exporting.py`, `tests/test_files_component.py`: the new core.
- `tests/test_mounts.py`: proposal paths and every generated command.
- `tests/test_data_selection_page.py`, `tests/test_quick_plot_page.py`,
  `tests/test_saving_page.py`, `tests/test_app_smoke.py`: GUI regression.

## Last verification

The `0.7.0` implementation passed:

```text
python -m pytest -q           280 passed
python -m ruff check src tests
git diff --check
python -m pip wheel . --no-deps
```

Figures were confirmed written to disk from Quick Plot, the four explorers, and
Publication Plot, each landing in its own page subfolder, with PNG produced
through kaleido and HTML produced without it.

## Next work

1. Have the user pull and install `0.7.0` and register the verified RaiDrive
   `Z:` mapping at the chosen remote scope.
2. Run a Data Selection search over the real proposal tree and check that the
   depth and result caps are sensible over SFTP, not just locally.
3. Try rclone against BNL Duo on Windows and record the result here; if it
   works, the GUI note in `01_Data_Sources_and_Mounts.py` and the README table
   should be upgraded from "not yet confirmed".
4. Exercise Quick Plot with the users' own non-beamline files — that is where
   the delimiter/header sniffer in `dataio.py` will meet cases I have not seen.
5. Verify the separate GISAXS, GIWAXS, TSAXS, and TWAXS q defaults against real
   beamline outputs and adjust only with scientific evidence.

## Suggested prompt for a new chat

```text
Please continue pyScattViz from the repository. First read README.md and
recorde.md completely, then inspect git status and recent git log. Keep the GUI
mount-only and credential-free, and keep the core modules Streamlit-free.
```
