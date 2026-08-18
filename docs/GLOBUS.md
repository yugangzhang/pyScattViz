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

Then open **Globus & Data Sources → Globus CLI browser**. The page detects the
CLI login and lists remote folders through the active NSLS2 collection:

```text
819379a8-47db-439d-a5ba-a2387b79add9
```

The retired `88c7648d-...` collection is not used. Online directory listing
does not transfer the proposal. Array loading still requires selected files to
be transferred into a local cache; Globus cannot expose the collection as a
Windows drive.

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
