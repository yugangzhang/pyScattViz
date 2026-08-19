# Getting NSLS-II data onto your computer

pyScattViz reads reduced scattering products through normal filesystem paths.
There are three honest ways to produce one, and all of them are free:

| Route | What happens | When I use it |
|---|---|---|
| **Mount** | Directory names are listed remotely; only the bytes of an opened file cross the network | Large or unfamiliar datasets — a 2 TB proposal costs nothing until a frame is read |
| **Copy a subset** | One result folder is written to the local disk | A small dataset, a slow link, or working offline |
| **Already local** | Nothing happens; the folder is registered | A disk, a USB drive, a laboratory share |

A mount does **not** make remote bytes local without network I/O. Browsing a
folder with tens of thousands of names is slower than on a local disk, which is
why the selection pages read names only.

## Security and authentication

The SFTP host is:

```text
sftp.nsls2.bnl.gov
```

Its verified ED25519 fingerprint is:

```text
SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE
```

BNL password and Duo prompts must be completed in a terminal or a desktop SFTP
mount client. pyScattViz never starts an interactive authentication process in
the browser and never stores passwords, Duo codes, or SSH keys.

What the application does write, all of it paths and preferences only:

```text
~/.pyscattviz/path_mappings.json    remote root → mounted/local folder
~/.pyscattviz/collections/*.json    saved dataset selections
~/.pyscattviz/settings.json         output folder and saving preferences
```

## Application workflow

1. Open **Data Sources & Mounts**.
2. Choose proposal, beamline-proposals, `/nsls2/data`, or a custom mount scope.
3. Enter the beamline/proposal information required by that scope and the BNL
   username.
4. Select the operating system, then the **access method**. The page generates
   the exact commands for that combination.
5. Complete BNL password and Duo authentication outside the web GUI.
6. Return to the page and select **Test this folder**.
7. Select **Register folder for the other pages**.
8. Open **Data Selection** to filter the tree with AND/OR/EXCLUDE term lists, or
   **File Selection** to browse it directly, then open an explorer.

## Method by platform

| Platform | Method | Status |
|---|---|---|
| Windows | RaiDrive | **Verified** with BNL password and Duo Push |
| Windows | rclone + WinFsp | Free and open source; Duo behaviour not yet confirmed |
| macOS | SSHFS + macFUSE | Standard route; macFUSE needs a security approval |
| macOS | rclone + macFUSE | Same commands as Windows and Linux |
| Linux | SSHFS | Standard route, fastest of the three |
| Linux | Files → Connect to Server | Nothing to install; slower for large folders |
| Any | `sftp -r`, `rclone copy`, FileZilla, Cyberduck | Copies a subset; no driver needed |
| Any | Already-local folder | Nothing to configure |

**RaiDrive is Windows-only.** Its equivalent on macOS and Linux is SSHFS;
rclone is the one client whose commands are identical on all three platforms.

## Windows

Windows OpenSSH successfully supports BNL password and Duo authentication, but
SSHFS-Win does not support the separate keyboard-interactive 2FA exchange. Use
the free RaiDrive SFTP client. This route has been verified with BNL password,
Duo Push, and an NSLS-II proposal mounted as a Windows drive.

Install it with `winget install --exact --id OpenBoxLab.RaiDrive`, then create an
SFTP connection to `sftp.nsls2.bnl.gov` on port 22. Use the remote root generated
by pyScattViz and an available drive letter such as `Z:`. Enable read-only access
when available: visualization does not require remote write access.

The account may still have server-side write permission. Do not rename, move,
or delete proposal content during review.

## Linux and macOS

The generated SSHFS command mounts directly through `sftp.nsls2.bnl.gov`; no
jump host is needed for proposal storage. Linux uses `fuse-sshfs`. macOS uses
macFUSE plus `gromgit/fuse/sshfs-mac`. Keep the mount point proposal-specific,
and unmount it before disconnecting from the network or shutting down.

On a GNOME desktop, **Files → Other Locations → Connect to Server** with
`sftp://<user>@sftp.nsls2.bnl.gov/` needs no installation. The mount appears at
`/run/user/<uid>/gvfs/sftp:host=sftp.nsls2.bnl.gov,user=<user>`, which is a
perfectly ordinary path as far as pyScattViz is concerned.

## rclone, on all three platforms

```bash
rclone config create nsls2 sftp host sftp.nsls2.bnl.gov user <user> port 22 ask_password true
rclone mount nsls2:<remote root> <local target> --read-only --vfs-cache-mode full
```

`ask_password true` keeps the BNL password out of the rclone configuration file.
Windows adds `--network-mode` and needs WinFsp; macOS and Linux add `--daemon`
and need macFUSE or `fuse3`.

I have not confirmed the BNL Duo prompt through rclone myself. If rclone stops
without asking for the Duo option, use RaiDrive on Windows or SSHFS on
macOS/Linux.

## Copying instead of mounting

```bash
sftp -r <user>@sftp.nsls2.bnl.gov:<remote result folder> <local folder>
rclone copy nsls2:<remote result folder> <local folder> --progress --include "*Kim*"
```

FileZilla (all platforms) and Cyberduck (Windows, macOS) do the same thing with
a mouse. Narrow the remote folder first: a whole proposal is rarely what anyone
wants on a laptop.

## Troubleshooting

- `Permission denied` — the BNL password or Duo failed, or the account is not
  authorized for that proposal.
- `Connection timed out` — the BNL VPN or a network route is needed.
- A mount that worked earlier but now looks empty — unmount and reconnect; a
  network interruption leaves a stale FUSE mount behind.
- Never unmount while a frame is loading.

Complete copy-and-paste commands for all three operating systems are in the
[README](../README.md#getting-the-data-onto-the-computer).
