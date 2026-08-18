# NSLS-II data transfer with Globus

I use Globus as the primary transfer route because transfers are resumable and
verified. pyScattViz can open Globus File Manager at the proposal path for
online browsing. It reads data only from a transferred or mounted filesystem
folder; it does not store BNL credentials or proxy the remote collection.

## One-time setup

1. Install Globus Connect Personal for the operating system in use:
   [Windows](https://docs.globus.org/how-to/globus-connect-personal-windows/),
   [macOS](https://docs.globus.org/how-to/globus-connect-personal-mac/), or
   [Linux](https://docs.globus.org/how-to/globus-connect-personal-linux/).
2. Create a personal collection and permit access to a destination such as
   `pyScattViz-data` in the home folder.
3. Keep Globus Connect Personal running during transfers.

## Each proposal transfer

1. Connect to the BNL campus network or VPN when required.
2. Open <https://app.globus.org/file-manager>.
3. Choose **Brookhaven National Laboratory** and sign in with BNL Domain
   credentials.
4. Search for the **NSLS2** collection. Clear every collection-search filter.
5. Open the proposal path:

   ```text
   /nsls2/data/cms/proposals/<cycle>/pass-<six digits>
   /nsls2/data/smi/proposals/<cycle>/pass-<six digits>
   ```

6. Choose **Transfer or Sync to…**, select the personal collection and local
   destination, and start the transfer.
7. Wait for Globus to report a successful task before reviewing the destination.

The **Globus & Data Sources** page builds the proposal path and records the local
destination. Its browse-only button does not start a transfer. It also links to
both BNL guides.

## Small review transfer

Reduced result products are normally sufficient for a review meeting. Select
only the relevant project folders under `Results/gisaxs`, `Results/giwaxs`,
`Results/tsaxs`, or `Results/twaxs`. Include raw detector folders only when raw
images must appear in the viewer.

For repeat reviews, enable Globus sync by modification time or checksum. This
copies only new or changed files.

## Remote mount without a bulk download

Globus Connect Personal is a transfer client, not a filesystem mount. To make
an NSLS-II proposal appear as a Windows drive without copying the whole tree,
open **Globus & Data Sources → Remote mount (lazy access)**. The tab guides a
Windows user through installing WinFsp and SSHFS-Win and generates the network
address for `sftp.nsls2.bnl.gov`. BNL SFTP access and the campus network or VPN
are required.

For example, mount this remote proposal as drive `Z:`:

```text
/nsls2/data/smi/proposals/2026-2/pass-319371
```

Then save this path mapping in the same tab:

```text
/nsls2/data/smi/proposals/2026-2/pass-319371  →  Z:\
```

Afterward, File Selection accepts the original Globus/NSLS-II path, including
deeper `projects/.../Results/giwaxs` components. pyScattViz translates it to
the mounted drive and opens only directory listings and selected frame files.
The mapping is saved under `.pyscattviz` in the user's home folder and contains
no username or password.

## Access and transfer troubleshooting

- An empty collection search often means a collection filter remains enabled.
- A missing proposal path usually indicates that the BNL account is not listed
  on that proposal or that the beamline/cycle is incorrect.
- An unavailable personal collection usually means Globus Connect Personal is
  not running.
- A completed transfer with no visible files can result from choosing a local
  path outside the directories permitted by the personal collection.
- pyScattViz cannot open `/nsls2/...` on a collaborator's laptop. Select the
  local Globus destination instead.
