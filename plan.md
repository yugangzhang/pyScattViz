# pyScattViz plan

What is still to do, most urgent first. [record.md](record.md) holds what has
been done, decided and verified — read it first. When an item here is done,
move its evidence into `record.md` and delete it from this file.

Last updated: 2026-10-21, at `0.22.0` (not yet committed).

## 1. Release 0.22.0

1. **Commit and push `0.22.0`.** Commit messages are written in my own voice
   with no assistant co-author trailer. `.gitignore` is staged separately and
   belongs in the same commit; `.ipynb_checkpoints/` does not.
2. **Restart the server** (`./run PORT PASSWORD`) so the running GUI picks up
   the new pages and the folder-picker fix.
3. **Build the OGang org on the live GUI.** *Org → Make an org*, Data folder
   `.../2026-3/pass-321639` (or its `experiments/OGang`), experiment *OGang*.
   Done when *Name* reads `OGang · 2026-3 · pass-321639`, the file is
   `<proposal>/Org/OGang.json`, and the summary shows 313 samples and 44 runs
   from about 3,089 frames. The development sandbox can read the proposal but
   not write `<proposal>/Org/`, so this step has to be done in the GUI. The
   empty `experiments/Org` folder made by hand can then be deleted.
4. **Rebuild the SMI QYu org with the `smi` layout.** The org made on
   2026-10-21, `.../pass-321337/projects/QYu/Org/Results.json`, was read
   with `products`: 56 samples, one per sample *and angle*
   (`QYu_JL5_0.1000deg`), and no beamline record. After the restart,
   *Make an org*, Data folder `.../projects/QYu/Results`. Done when the
   layout reads *SMI project (recognised)*, the file offered is
   `.../projects/QYu/Org/QYu.json`, the name `QYu · 2026-3 · pass-321337`,
   the summary 8 samples and 336 frames, and *Beamline, acquisition and
   reduction* shows 7 angles, WAXS arcs 0, 20, 40, SAXS at 40, 3 spots at
   −1000, 0, +1000 µm and the three `configs/*.yaml`. `Results.json` can then
   be deleted. The sandbox cannot write `projects/QYu/Org/`.
5. **Update the CMS QYu org while it is measured.** *Open an org → QYu*, then *Link new
   frames and save*. Done when the "not in the file yet" notice is gone and
   reopening the org shows the new frames.
6. **Check the wheel at `0.22.0`.** `python -m pip wheel . --no-deps` on a
   machine with network access (offline, the build here produced
   `UNKNOWN-0.0.0`). Done when the wheel is `pyscattviz-0.22.0` and holds
   `org/`, `products.py`, `components/org/` and pages 14–19.

## 2. Org pages

1. **Tell spots apart by x and y.** OGang's transmission spots are named
   `_x…_y…`, but `cms.parse_frame` reads only x (`_X_RE`), and spots are told
   apart on `["pos", "x"]` both in `cms.sample_table` and in the spot picker
   of `16_Org_Sample.py`. So two spots that share an x are one spot, and the
   second shows up only as a *Repeat* on *Org Sample*. Parse y the way x is
   parsed, key spots on `pos`, `x` and `y`, and show y in the spot label when
   a sample has it. Done when a test with OGang-style names (same x, two y)
   gives two spots, and the OGang org's spot and repeat counts are checked on
   the real folder. SMI frames carry y already (`smi.parse_frame`):
   HZheng's 3 × 3 grid of spots reads as 3 spots × 3 repeats until then.
2. **Save a figure from the Org pages.** Every other plotting page saves its
   panels to the output folder through `components/saving.py`; the Org pages
   download their data as CSV (the I(q), the curves, the waterfall, the peak
   tables) but cannot save a figure. Add the shared save panel to *Org
   Sample*, *Org Compare* and *Org In-situ*, writing to an `org` subfolder.
3. **Line-cuts on *Org Sample*.** The explorers' horizontal and vertical cuts
   of the q-image and the q–φ map. Reuse the explorer code rather than copying
   it.
4. **Hot-pixel cleaning and masks on the Org q-images**, through
   `despike.py` as the explorers do.
5. **To decide: save the org on its own while *Live* is on.** Today a frame
   measured since the last save is linked on screen but written to the file
   only on *Link new frames and save*. Saving by itself means the server
   writes into the proposal folder unattended, so it should stay off by
   default if it is added at all.
6. **Later, on request: the run metadata of an SMI org's scans, from Tiled.** The org keeps
   what the names, `user_data/` listings and `configs/*.yaml` say, and the
   scan id of every linked file (`meta.scans`). What only the Bluesky
   records hold is not in it yet: the start document's `user_hints` (every
   piezo and Huber position, the sample's extra fields), `experiment`,
   `user_group`, `geometry` and `YZ['md']` (beam, environment, holder,
   cell), and the baseline (slits, attenuators, XBPMs, energy). Read them
   from `tiled.nsls2.bnl.gov` (`smi` catalog, reachable from the
   workstation; it needs a login — an API key the user sets, never
   stored in the org) by scan id, summarise them per sample and for the
   experiment, and keep them beside `beamline`. Done when the QYu org shows
   *environment vacuum, RT*, *holder Al GI bar* and the slit and
   attenuator settings, and an org opens and works with no Tiled access.


## 3. Tests

1. **Isolate every test from the user's own settings.** 19 test files set
   `PYSCATTVIZ_CONFIG_DIR` and `PYSCATTVIZ_OUTPUT_DIR` themselves;
   `test_app_smoke.py` does not, so it reads `~/.pyscattviz/settings.json`
   and fails wherever that output root cannot be written (it does in the
   development sandbox). Move the fixture into `tests/conftest.py` as
   `autouse` and drop the copies. Done when `pytest -q` passes with no
   environment variables set and a read-only home output folder.

## 4. Needs Windows or macOS and BNL credentials

None of these can be done from the Linux workstation.

1. **Pull and install the current version on Windows** and register the
   verified RaiDrive `Z:` mapping at the chosen remote scope.
2. **Try rclone against BNL Duo on Windows** and record the result in
   `record.md`. If it works, upgrade the "not yet confirmed" wording in
   `01_Data_Sources_and_Mounts.py`, the README table and `docs/MOUNTS.md`.
   Do not soften that wording without the test.
3. **Try SSHFS on macOS** against the same proposal storage, and record the
   result the same way.
