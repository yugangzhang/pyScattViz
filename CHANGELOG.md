# Changelog

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
