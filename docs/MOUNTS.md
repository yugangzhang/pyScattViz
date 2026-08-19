# NSLS-II SFTP mounts

pyScattViz reads reduced scattering products through normal filesystem paths.
Mounting an NSLS-II proposal over SFTP provides on-demand access: directory
names are listed remotely and only files opened by the application cross the
network. A mount does not make remote bytes local without network I/O.

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

## Application workflow

1. Open **Data Sources & Mounts**.
2. Enter beamline, cycle, proposal, and BNL username.
3. Select the operating system and follow the generated instructions.
4. Complete BNL password and Duo authentication outside the web GUI.
5. Return to the page and select **Test mounted path**.
6. Select **Register mount for File Selection**.
7. Browse from the proposal mount to `projects/.../Results/giwaxs`, `gisaxs`,
   `tsaxs`, or `twaxs` in File Selection.

The saved mapping contains paths only and is stored in:

```text
~/.pyscattviz/path_mappings.json
```

## Windows

Windows OpenSSH successfully supports BNL password and Duo authentication, but
SSHFS-Win does not support the keyboard-interactive 2FA exchange. Use Mountain
Duck with an SFTP bookmark and **Online** connect mode. Set the server, username,
and proposal path shown by pyScattViz. Online mode uses an on-demand local cache
for files that applications open; it does not synchronize the complete proposal.

Mountain Duck is commercial after its trial. Free alternatives are Linux
SSHFS inside WSL or SSHFS-Win key authentication after NSLS-II support has
registered an SSH public key for the account.

## Linux and macOS

The generated command mounts directly through `sftp.nsls2.bnl.gov`; no jump
host is needed for proposal storage. Linux uses `fuse-sshfs`. macOS uses
macFUSE plus `gromgit/fuse/sshfs-mac`. Keep the mount point proposal-specific,
and unmount it before disconnecting from the network or shutting down.

Complete copy-and-paste commands for all three operating systems are in the
[README](../README.md#mount-nsls-ii-proposal-data).
