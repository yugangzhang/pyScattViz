# pyScattViz development handoff

Read this file before continuing work after a chat, terminal, or development
session restart. It deliberately contains no passwords, Duo codes, tokens, or
private keys.

## Repository state

- Repository: `https://github.com/yugangzhang/pyScattViz`
- Branch: `main`
- Current package version: `0.6.0`
- The Windows launcher `start_windows.bat` was confirmed working by the user.
- At the end of this handoff update, `main` is expected to be committed, pushed,
  and clean. Confirm with `git status` and `git log -5 --oneline --decorate`.

## User goal and verified access

Most users will run pyScattViz on Windows. The goal is to browse and visualize
large NSLS-II proposal data without copying the complete proposal to the local
computer.

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

## Current design decisions

1. pyScattViz reads only normal local or mounted filesystem paths.
2. The GUI must never request or store a BNL password, Duo response, token, or
   private key.
3. Interactive authentication must happen in a real terminal or desktop SFTP
   mount client. The GUI may generate commands, explain setup, validate a mount,
   and save path mappings.
4. Linux and macOS use direct SSHFS mounting through
   `sftp.nsls2.bnl.gov`. The **Data Sources & Mounts** page generates the exact
   proposal-specific command.
5. Native Windows SSHFS-Win password mounting is not recommended because it
   could not complete BNL keyboard-interactive Duo authentication (`net use`
   ended with system error 67). Do not repeat that path unless key-based access
   has first been arranged with NSLS-II support.
6. The verified native-Windows recommendation is the free RaiDrive SFTP client.
   Use read-only access when possible. A mount fetches bytes for opened files
   but does not synchronize the complete proposal.
7. Proposal scope is the safest default. Authorized staff may instead mount a
   beamline proposal root, `/nsls2/data`, or a validated custom subpath.
8. GISAXS, GIWAXS, transmission SAXS, and transmission WAXS have independent
   pages and scientific defaults.
9. The Plotting Studio exposes 1D, 2D, 3D, and multi-axes workflows using the
   supported `pyscattviz.plotting` API.

## Application workflow

1. Open **Data Sources & Mounts**.
2. Select the mount scope and enter beamline `SMI`, cycle `2026-2`, proposal
   `319371`, and the BNL username as needed.
3. On Windows, configure RaiDrive SFTP with the generated remote root and an
   available drive such as `Z:`. Linux/macOS use the generated SSHFS command.
4. Complete password/Duo authentication outside the browser.
5. Return to the GUI and enter the mounted path.
6. Select **Test mounted path**.
7. Select **Register mount for File Selection**.
8. Open **File Selection** and browse with its `pwd`, `ls`, `cd`, and bounded
   `du` commands, or paste the original `/nsls2/...` result path. A pasted remote
   path works only when a corresponding available mount mapping is registered.
9. Scan filenames, select frames, and open the geometry-specific scattering
   viewer. Array data are opened only for the active frame.
10. Use Plotting Studio for interactive 1D/2D/3D or multi-axes figures.

Mappings contain paths only and are saved at:

```text
~/.pyscattviz/path_mappings.json
```

An old `/nsls2/... -> Z:\` mapping should be removed in **Data Sources &
Mounts → Mounted / local folders** if `Z:\` does not actually exist.

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

- `README.md`: beginner installation, update, launch, and cross-platform mount
  instructions.
- `docs/MOUNTS.md`: concise SFTP mount and security guide.
- `src/pyscattviz/app/pages/1_Data_Sources_and_Mounts.py`: GUI instructions,
  command display, mount validation, and mapping registration.
- `src/pyscattviz/mounts.py`: proposal validation and SSHFS command generation.
- `src/pyscattviz/app/pages/2_File_Selection.py`: mounted/local filesystem
  browsing and lazy filename selection.
- `src/pyscattviz/app/components/grazing_explorer_page.py`: shared low-level
  renderer with independent GISAXS/GIWAXS profiles.
- `src/pyscattviz/app/components/transmission_explorer_page.py`: shared
  low-level renderer with independent TSAXS/TWAXS profiles.
- `src/pyscattviz/app/pages/8_Plotting_Studio.py`: 1D, 2D, 3D, and multi-axes
  GUI workspaces.
- `src/pyscattviz/studio.py`: safe upload adapters and deterministic demos.
- `src/pyscattviz/data_sources.py`: persistent remote-to-mounted path mapping.
- `tests/test_mounts.py` and `tests/test_app_smoke.py`: mount and GUI regression
  coverage.

## Last verification

The `0.6.0` implementation passed:

```text
python -m pytest -q           169 passed
python -m ruff check src tests
git diff --check
python -m pip wheel . --no-deps
```

## Next work

1. Have the user pull and install `0.6.0` on Windows.
2. Register the verified RaiDrive `Z:` mapping at the chosen remote scope.
3. Browse to the GIWAXS result folder, scan a small filename filter, and open
   one `cir_avg` or `q_image` frame.
4. Verify the separate GISAXS, GIWAXS, TSAXS, and TWAXS q defaults against real
   beamline outputs and adjust only with scientific evidence.
5. Exercise Plotting Studio with representative user CSV and NPZ files.

## Suggested prompt for a new chat

```text
Please continue pyScattViz from the repository. First read README.md and
recorde.md completely, then inspect git status and recent git log. Keep the GUI
mount-only and continue from the Windows mount test described in recorde.md.
```
