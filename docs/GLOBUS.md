# NSLS-II data transfer with Globus

I use Globus as the primary transfer route because transfers are resumable and
verified. pyScattViz can open Globus File Manager or use an authenticated
Globus CLI session for online browsing. It does not store BNL credentials or
proxy the remote collection.

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

## Browse through Globus CLI without downloading

Globus is not a filesystem mount. On Windows, authenticate its command-line
client once using the same BNL browser login and Duo flow as File Manager:

```powershell
.\.venv\Scripts\globus.exe login
```

On macOS or Linux:

```bash
./.venv/bin/globus login
```

The NSLS2 collection may request one additional data-access consent on the
first directory listing. The GUI detects this response and shows the command:

```powershell
.\.venv\Scripts\globus.exe session consent "urn:globus:auth:scope:transfer.api.globus.org:all" "https://auth.globus.org/scopes/819379a8-47db-439d-a5ba-a2387b79add9/data_access"
```

Complete the browser approval/Duo flow once, then select **Retry remote listing
after consent**. A GUI restart is not necessary. The GUI generates the command
with Windows or macOS/Linux paths as appropriate and preserves all scopes
returned by Globus.

Then open **Globus & Data Sources → Globus CLI browser**. The page detects the
CLI login and lists remote folders through the active NSLS2 collection:

```text
819379a8-47db-439d-a5ba-a2387b79add9
```

The retired `88c7648d-...` collection is not used. Online directory listing
does not transfer the proposal. Navigate to the required result root and use
**Use current remote folder in File Selection**, or select a visible subfolder
and use **Use selected folder in File Selection**. The same `/nsls2/...` path
can also be pasted into **File Selection → Result folder**.

## Selective cache transfer for visualization

When File Selection receives an `/nsls2/...` path, it can index product
filenames directly through Globus. Choose **Find remote product folders**, set
the filename filter, and choose **Scan remote filenames**. No NPZ, CSV, or
image content is read during this step.

To visualize the selection:

1. Start Globus Connect Personal on the same computer as pyScattViz.
2. Choose **Find my Globus Connect Personal collections** and select the
   destination collection. Its UUID can also be pasted manually.
3. Enter the destination folder as it appears inside that Globus collection.
4. Enter the exact same destination as a local Windows/macOS/Linux path.
5. Start the selective transfer. pyScattViz submits all matching product files
   in one Globus batch task and preserves `q_image`, `qphi`, `cir_avg`, `qc`,
   and `stitched` subfolders.
6. Check the task status. After success, open the transferred files in File
   Selection and continue to a scattering viewer.

Moving to another pyScattViz page does not discard the remote path, product
choices, filters, scan table, or cache settings. Before transfer, the viewers
show the number of saved remote frame names and direct the user back to File
Selection; names alone cannot render the arrays.

The Globus collection root and local filesystem root are not always named the
same way. Confirm their correspondence in Globus File Manager. A common
Windows example is Globus path
`/C/Users/yuzhang/pyScattViz-data/Kim-giwaxs` corresponding to local path
`C:\Users\yuzhang\pyScattViz-data\Kim-giwaxs`.

Globus cannot expose the NSLS2 collection as a Windows drive. Only the selected
frame files are transferred into the local cache; the proposal remains remote.
An old saved SSHFS or mapped-drive rule is ignored when its translated folder
does not exist. Remove obsolete rules under **Globus & Data Sources → Local
folders**.

If NSLS-II replaces the collection UUID, use **Refresh current NSLS2 collection
ID**. The ID is also editable for recovery and is not assumed to remain fixed
forever.

## Access and transfer troubleshooting

- An empty collection search often means a collection filter remains enabled.
- A missing proposal path usually indicates that the BNL account is not listed
  on that proposal or that the beamline/cycle is incorrect.
- An unavailable personal collection usually means Globus Connect Personal is
  not running.
- A completed transfer with no visible files can result from choosing a local
  path outside the directories permitted by the personal collection.
- The CLI browser can list `/nsls2/...`, but viewers cannot open remote arrays
  until selected files have reached a local Globus destination/cache.
