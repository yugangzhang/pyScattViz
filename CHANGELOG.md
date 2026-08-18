# Changelog

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
