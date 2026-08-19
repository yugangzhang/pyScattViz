# pyScattViz

> Continuing this work in a new chat or development session? Read
> [recorde.md](recorde.md) first. It records the current release, design
> decisions, verified behavior, Windows test status, and next steps.

I wrote **pyScattViz** so collaborators can explore their scattering data on
their own computer without asking me to run anything for them. It covers
GISAXS, GIWAXS, transmission SAXS and WAXS reduction products from NSLS-II, and
it also plots plain data files — a two-column `.dat`, an `.npz`, a detector
`.tif` — that never came from a beamline reduction at all.

The data can reach the computer three ways, and all three are free:

1. **Mount the NSLS-II proposal over SFTP.** RaiDrive on Windows, SSHFS on macOS
   and Linux, rclone on all three. Only the bytes of an opened frame cross the
   network; the proposal is never copied whole.
2. **Copy a subset to the local disk.** `sftp -r`, `rclone copy`, FileZilla, or
   Cyberduck. Best for one result folder, a slow link, or working offline.
3. **Use data that is already local.** A disk, a USB drive, or a laboratory
   network share needs no setup at all.

The application runs locally on Windows, macOS, and Linux, listens on
`127.0.0.1`, and never asks for or stores a BNL password or Duo response.

## What is in it

| Page | What it is for |
|---|---|
| **Data Sources & Mounts** | Every free way to make the data visible, with the exact command generated for your platform |
| **Data Selection** | Find folders or files with *must contain* / *may contain* / *must not contain* term lists; keep them in a dataset basket and save it under a name |
| **File Selection** | Filter thousands of reduced filenames without opening a single array |
| **GISAXS · GIWAXS · Transmission SAXS · Transmission WAXS** | Four independent explorers with their own q defaults, panels, and line cuts |
| **Quick Plot** | Hand it any list of full paths and get 1D overlays, a stacked intensity map, or 2D images |
| **Publication Plot** | Export-ready I(q) overlays with publication themes |
| **Plotting Studio** | 1D, 2D, 3D, and multi-axes workspaces on the `pyscattviz.plotting` API |
| **Output Folder** | Where saved figures go, and what has been written there |

Each explorer can also export one panel for *every* frame that passes its
filters, which turns an angle series or an in-situ run into a folder of figures
in one click.

Everything that draws something can write it **straight to a folder you name**,
in a subfolder named after the page it came from — no hunting through the
browser's download directory. See
[Saving figures to your own folder](#saving-figures-to-your-own-folder).

## Installation from zero

These instructions assume no programming or terminal experience. A terminal is
a text window used to give the computer commands. Copy one command at a time,
paste it after the prompt, and press **Enter**. Do not copy the prompt itself
(for example, do not type `PS C:\Users\name>`).

Installing Python or Git may require an administrator password or help from the
computer's IT department. Python 3.9–3.12 is supported; I recommend 64-bit
Python 3.12 for a new installation.

> **The environment folder is different on each platform.** Windows commands
> use `.venv\Scripts`; macOS and Linux commands use `.venv/bin`. I included a
> separate start file for each platform so the path does not need to be
> remembered.

### Windows 10 or 11

#### 1. Open PowerShell or Windows Terminal

1. Click the **Start** button or press the **Windows** key.
2. Type `PowerShell`.
3. Open **Windows PowerShell** or open **Windows Terminal** and select its
   **PowerShell** tab. Either choice works.
4. A blue or black window opens with a prompt similar to
   `PS C:\Users\name>`. Paste commands with `Ctrl+V`.

#### 2. Install Python and Git

Paste these commands one at a time:

```powershell
winget install --exact --id Python.Python.3.12
winget install --exact --id Git.Git
```

Accept any license or installation prompts. When both commands finish, close
every PowerShell/Terminal window and open PowerShell again from the Start menu.
This restart makes the new programs visible.

If the computer reports that `winget` is not recognized:

1. Open a web browser and visit
   [Python for Windows](https://www.python.org/downloads/windows/).
2. Download the latest **Python 3.12 64-bit installer** and open it.
3. On the first installer screen, select **Add python.exe to PATH** and install
   the **Python launcher (`py`)**.
4. Download [Git for Windows](https://git-scm.com/download/win), open the
   installer, and keep its default choices.
5. Close and reopen PowerShell.

#### 3. Check the installation

```powershell
py -3.12 --version
git --version
```

The first command should print `Python 3.12...`; the second should print a Git
version. If Windows instead displays “Python was not found; run without
arguments to install from the Microsoft Store,” return to step 2 and install a
real Python interpreter. Use `py -3.12`, not the `python` Store alias.

#### 4. Download pyScattViz

```powershell
cd $HOME
git clone https://github.com/yugangzhang/pyScattViz.git
cd .\pyScattViz
```

`git clone` downloads the package into the personal home folder. If it was
already downloaded, skip the clone command and enter:

```powershell
cd $HOME\pyScattViz
```

#### 5. Create the private Python environment and install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
```

The last command downloads the scientific Python dependencies and may take
several minutes. Wait until the prompt returns without a red error message.
The commands call the environment directly, so PowerShell activation and its
script-execution policy are not involved.

#### 6. Start pyScattViz

The easiest method is to open the `pyScattViz` folder in File Explorer and
double-click **`start_windows.bat`**. If Windows displays a security prompt,
select **More info → Run anyway**.

The PowerShell method is:

```powershell
.\.venv\Scripts\python.exe -m pyscattviz
```

The browser should open at <http://127.0.0.1:8501>. Keep the PowerShell window
open while using the application.

#### Start it again on another day

Open PowerShell from the Start menu and run:

```powershell
cd $HOME\pyScattViz
.\start_windows.bat
```

The `Scripts` folder in these Windows commands is required. A command such as
`./.venv/bin/pyscattviz` is for macOS/Linux and PowerShell cannot find it.

### macOS

#### 1. Install Python and Git

1. Open a web browser and visit
   [Python for macOS](https://www.python.org/downloads/macos/).
2. Download and open the latest **Python 3.12 universal2 installer** (`.pkg`).
3. Follow the installer using its default choices.
4. Git is often already available. macOS can install it in step 3 below if it
   is missing.

#### 2. Open Terminal

1. Press **Command+Space** to open Spotlight Search.
2. Type `Terminal` and press **Return**. Terminal is also under
   **Applications → Utilities → Terminal** in Finder.
3. A window opens with a prompt ending in `%` or `$`. Paste with `Command+V`.

#### 3. Check Python and Git

```bash
python3.12 --version
git --version
```

The Python command should print `Python 3.12...`. If the Git command opens a
dialog asking to install Command Line Developer Tools, click **Install**, wait
for it to finish, and run `git --version` again.

#### 4. Download and install pyScattViz

```bash
cd "$HOME"
git clone https://github.com/yugangzhang/pyScattViz.git
cd pyScattViz
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install .
```

If the repository was already downloaded, skip `git clone` and begin with
`cd "$HOME/pyScattViz"`. Wait for installation to finish and the prompt to
return.

#### 5. Start pyScattViz

In Finder, open the `pyScattViz` folder and double-click
**`start_macos.command`**. If macOS blocks it the first time, Control-click the
file, select **Open**, and then select **Open** again.

The Terminal method is:

```bash
./.venv/bin/python -m pyscattviz
```

The browser should open at <http://127.0.0.1:8501>. Keep Terminal open. On
another day, open Terminal and run:

```bash
cd "$HOME/pyScattViz"
./start_macos.command
```

### Linux

#### 1. Open a terminal

On Ubuntu, Debian, Fedora, and many other Linux desktops, press
**Ctrl+Alt+T**. Another option is to open the applications menu, search for
`Terminal`, and select it. Paste commands with `Ctrl+Shift+V` on most Linux
terminals.

#### 2. Install Python and Git

For Ubuntu, Debian, Linux Mint, or related systems:

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip
```

For Fedora:

```bash
sudo dnf install git python3
```

The terminal may request the login password. No characters appear while a
Linux password is typed; this is normal. Press **Enter** after typing it.

Check the installation:

```bash
python3 --version
git --version
```

Python must be version 3.9 or newer.

#### 3. Download and install pyScattViz

```bash
cd "$HOME"
git clone https://github.com/yugangzhang/pyScattViz.git
cd pyScattViz
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install .
```

If the repository was already downloaded, skip `git clone` and begin with
`cd "$HOME/pyScattViz"`.

#### 4. Start pyScattViz

From the file manager, double-click **`start_linux.sh`** and select **Run** if
the desktop asks how to open it. The terminal method is:

```bash
./.venv/bin/python -m pyscattviz
```

The browser should open at <http://127.0.0.1:8501>. Keep the terminal open. On
another day, open a terminal and run:

```bash
cd "$HOME/pyScattViz"
./start_linux.sh
```

### Stop or update pyScattViz

To stop the application on any platform, return to the terminal and press
`Ctrl+C`.

To install a later update on Windows:

```powershell
cd $HOME\pyScattViz
git pull --ff-only
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pip install --upgrade .
.\start_windows.bat
```

> From 0.7.2 the `Remove-Item ... build` line is belt and braces — packaging
> clears that folder itself. It mattered when upgrading from 0.7.0 or 0.7.1,
> where a leftover `build` folder put the old page files back into the new
> install and Streamlit refused to start with *Multiple Pages specified with URL
> pathname*. If you hit that, just start pyScattViz again: it removes the stale
> files itself and reports what it removed.

> **Do not run `python3 -m venv .venv` on Windows after `git pull`.** The
> `python3` command is normally for macOS/Linux, and pulling an update does not
> remove the existing environment. Check it first:

```powershell
.\.venv\Scripts\python.exe --version
```

If that prints a Python version, keep the environment and run the update
commands above. Only when Windows reports that `.venv\Scripts\python.exe` does
not exist should the environment be created again:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
```

To install a later update on macOS or Linux:

```bash
cd "$HOME/pyScattViz"
git pull
rm -rf build
./.venv/bin/python -m pip install --upgrade .
./.venv/bin/python -m pyscattviz
```

### Troubleshooting startup

**PowerShell says `./.venv/bin/pyscattviz` is not recognized:** this is a
macOS/Linux path. From the `pyScattViz` folder on Windows, run:

```powershell
.\start_windows.bat
```

or:

```powershell
.\.venv\Scripts\python.exe -m pyscattviz
```

**PowerShell says `python3` was not found or opens the Microsoft Store:** do
not use `python3` on Windows. Use `py -3.12` when creating an environment, or
call `.\.venv\Scripts\python.exe` directly when the environment already exists.

**A start file says pyScattViz is not installed:** return to the installation
section for that operating system and create `.venv` before starting the app.

**The browser does not open automatically:** enter <http://127.0.0.1:8501> in
a web browser while the terminal window is still running.

If port 8501 is already in use, start on another port by adding `--port 8502`
to the final start command. The application listens only on the local computer
by default.

## Getting the data onto the computer

pyScattViz needs normal filesystem paths because NumPy, pandas, and image
readers open the selected CSV, NPZ, and image files directly. Choose one of the
three routes below, then register the folder on **Data Sources & Mounts**.

Open that page first: it asks for the beamline, cycle, proposal, and BNL
username, then generates the exact command for the platform and method you
select, tests the resulting folder, and saves the path mapping. Password and
Duo prompts run in a real terminal or desktop mount client; the web GUI
intentionally never receives or stores credentials.

Every example below uses placeholders rather than a real experiment. Substitute
your own:

| Placeholder | Replace with |
|---|---|
| `xxx` | your beamline's three-letter code |
| `xxxxxx` | your six-digit proposal number |
| `username` | your BNL username |
| `myproject` | the project folder inside your proposal |

So the remote root the page builds looks like this, with your own values in
place of the placeholders:

```text
/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx
```

### Choose the mount scope

| Scope | Remote root | Recommended use |
|---|---|---|
| Proposal | `/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx` | Safest default for collaborators |
| Beamline proposals | `/nsls2/data/xxx/proposals` | Several authorized proposals at one beamline |
| NSLS-II data | `/nsls2/data` | Staff working across beamlines |
| Custom | Any validated path below `/nsls2/data` | A specific project or results tree |

A broader mount exposes more directory names and may be slower to browse. It
does not grant new permissions: the SFTP server still enforces the BNL account's
authorization.

### Which method on which platform

| Platform | Method | Cost | Status |
|---|---|---|---|
| Windows | RaiDrive | free edition | **Verified** with BNL password and Duo Push |
| Windows | rclone + WinFsp | free, open source | Works cross-platform; Duo behaviour not yet confirmed by me |
| macOS | SSHFS + macFUSE | free | Standard route; macFUSE needs a security approval |
| macOS | rclone + macFUSE | free, open source | Same commands as Windows and Linux |
| Linux | SSHFS | free | Standard route, fastest of the three |
| Linux | Files → Connect to Server | free, nothing to install | Convenient; slower for large image folders |
| Any | `sftp -r`, FileZilla, Cyberduck | free | Copies a subset; no driver needed |
| Any | Already-local folder | — | Nothing to configure |

**RaiDrive is Windows-only.** macOS and Linux users should not look for it —
SSHFS is the equivalent there, and rclone is the one client that behaves
identically on all three platforms.

### Windows: RaiDrive (verified)

This is the route I tested against the NSLS-II server, with the BNL password,
Duo Push, and a mounted `Z:` drive. pyScattViz needs read access only.

1. Connect to the BNL VPN if the SFTP service is unavailable from the current
   network.
2. Test SFTP in PowerShell:

   ```powershell
   sftp username@sftp.nsls2.bnl.gov
   ```

3. Enter the BNL password, enter `1` for Duo Push, approve it, and run:

   ```text
   ls /nsls2/data/xxx/proposals/2026-2/pass-xxxxxx
   exit
   ```

4. Install [RaiDrive](https://www.raidrive.com/) from PowerShell:

   ```powershell
   winget install --exact --id OpenBoxLab.RaiDrive
   ```

5. Open RaiDrive, add a new **SFTP** storage connection, and enter:

   ```text
   Address:      sftp.nsls2.bnl.gov
   Port:         22
   Username:     your BNL username
   Path:         /nsls2/data/xxx/proposals/2026-2/pass-xxxxxx
   Drive letter: Z: (or another available letter)
   Access:       Read-only, when available
   ```

6. Verify the server's ED25519 fingerprint before accepting it:

   ```text
   SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE
   ```

7. Connect, complete the BNL password and Duo Push prompts, and confirm that the
   drive opens in File Explorer.
8. In **Data Sources & Mounts**, enter the mounted location shown by File
   Explorer, select **Test this folder**, then **Register folder for the other
   pages**.
9. In Data Selection or File Selection, browse from the mounted proposal root to
   a result folder, for example:

   ```text
   Z:\projects\myproject\Results\giwaxs
   ```

   Use the actual drive or mounted location shown on the computer; it may not
   be `Z:`.

The mounted account may have write permission. For scientific review, enable
read-only access when possible and do not rename, move, or delete proposal
content. The pyScattViz folder command bar itself implements only `pwd`, `ls`,
`cd`, and bounded `du`; it does not provide write commands.

SSHFS-Win is not used for password authentication because its Windows provider
cannot complete the separate Duo prompt. WSL plus Linux SSHFS remains another
free option for advanced users.

### Linux: SSHFS

Install SSHFS:

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install sshfs

# Fedora/RHEL alternative
sudo dnf install fuse-sshfs
```

Create a proposal-specific mount point and mount it:

```bash
mkdir -p "$HOME/NSLS_II_Link/xxx-pass-xxxxxx"
sshfs -o follow_symlinks,reconnect,ServerAliveInterval=15,ServerAliveCountMax=3 \
  username@sftp.nsls2.bnl.gov:/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx/ \
  "$HOME/NSLS_II_Link/xxx-pass-xxxxxx"
```

On the first connection, accept the host only if its ED25519 fingerprint is
`SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE`. Enter the BNL password,
select Duo option `1`, and approve the push. Test it:

```bash
ls "$HOME/NSLS_II_Link/xxx-pass-xxxxxx"
```

Register that folder under **Data Sources & Mounts**. Unmount later with:

```bash
fusermount3 -u "$HOME/NSLS_II_Link/xxx-pass-xxxxxx" || \
  fusermount -u "$HOME/NSLS_II_Link/xxx-pass-xxxxxx"
```

The proposal SFTP server is direct; it does not require the two-hop beamline
workstation jump used for some legacy data.

### Linux: Files → Connect to Server (nothing to install)

On a GNOME desktop such as Ubuntu or Fedora there is no installation step at
all:

1. Open **Files**.
2. Select **Other Locations** at the bottom of the sidebar.
3. In **Connect to Server**, enter `sftp://username@sftp.nsls2.bnl.gov/` and
   select **Connect**.
4. Enter the BNL password, choose the Duo option, and approve the push.

The mount then appears as an ordinary folder:

```bash
/run/user/$(id -u)/gvfs/sftp:host=sftp.nsls2.bnl.gov,user=username
```

Paste that path into **Data Sources & Mounts** and register it. GVFS is slower
than SSHFS for folders holding thousands of images, so prefer SSHFS when
browsing a large reduction.

### macOS: SSHFS + macFUSE

Install Homebrew if needed, then install macFUSE and SSHFS:

```bash
brew install --cask macfuse
brew install gromgit/fuse/sshfs-mac
```

macOS may require approval of the macFUSE system extension under **System
Settings → Privacy & Security** and may request a restart. Then mount:

```bash
mkdir -p "$HOME/NSLS_II_Link/xxx-pass-xxxxxx"
sshfs -o follow_symlinks,reconnect,ServerAliveInterval=15,ServerAliveCountMax=3 \
  username@sftp.nsls2.bnl.gov:/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx/ \
  "$HOME/NSLS_II_Link/xxx-pass-xxxxxx"
```

On the first connection, accept the host only if its ED25519 fingerprint is
`SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE`. Enter the BNL password,
select Duo option `1`, approve the push, and register the mounted folder under
**Data Sources & Mounts**. Unmount with:

```bash
umount "$HOME/NSLS_II_Link/xxx-pass-xxxxxx"
```

### Any platform: rclone

rclone is free and open source and uses the same commands on Windows, macOS, and
Linux, so it is what I recommend when a whole group needs one set of
instructions. It needs a FUSE driver: WinFsp on Windows, macFUSE on macOS.

Install:

```powershell
# Windows
winget install --exact --id WinFsp.WinFsp
winget install --exact --id Rclone.Rclone
```

```bash
# macOS
brew install --cask macfuse
brew install rclone

# Ubuntu/Debian
sudo apt update && sudo apt install rclone fuse3
```

Configure the connection once. `ask_password true` keeps the BNL password out
of the rclone configuration file — rclone prompts for it, and for the Duo
challenge, at mount time:

```bash
rclone config create nsls2 sftp host sftp.nsls2.bnl.gov user username port 22 ask_password true
```

Mount it. On Windows use a free drive letter; on macOS and Linux use an empty
folder:

```powershell
# Windows
rclone mount nsls2:/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx Z: --read-only --vfs-cache-mode full --dir-cache-time 60s --attr-timeout 60s --network-mode
```

```bash
# macOS and Linux
mkdir -p "$HOME/NSLS_II_Link/xxx-pass-xxxxxx"
rclone mount nsls2:/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx \
  "$HOME/NSLS_II_Link/xxx-pass-xxxxxx" \
  --read-only --vfs-cache-mode full --dir-cache-time 60s --attr-timeout 60s --daemon
```

Release the mount with `Ctrl+C` in the rclone window on Windows, `umount` on
macOS, or `fusermount3 -u` on Linux.

I have not yet confirmed the BNL Duo prompt through rclone myself. If rclone
stops without asking for the Duo option, fall back to RaiDrive on Windows or
SSHFS on macOS/Linux, both of which are known to work.

### Any platform: copy a subset to the local disk

No mount, no driver, nothing to install — OpenSSH ships with Windows 10/11,
macOS, and every Linux distribution. This is the right answer for a single
result folder, a slow link, or working on a plane:

```bash
# macOS and Linux
mkdir -p "$HOME/pyScattViz_Data/giwaxs"
sftp -r username@sftp.nsls2.bnl.gov:/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx/projects/myproject/Results/giwaxs \
  "$HOME/pyScattViz_Data/giwaxs"
```

```powershell
# Windows
New-Item -ItemType Directory -Force -Path "$HOME\pyScattViz_Data\giwaxs"
sftp -r username@sftp.nsls2.bnl.gov:/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx/projects/myproject/Results/giwaxs "$HOME\pyScattViz_Data\giwaxs"
```

With rclone configured, a filtered copy is often better than a whole folder:

```bash
rclone copy nsls2:/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx/projects/myproject/Results/giwaxs \
  "$HOME/pyScattViz_Data/giwaxs" --progress --include "*sampleA*"
```

Graphical alternatives that also work on every platform:
[FileZilla](https://filezilla-project.org/) and, on Windows and macOS,
[Cyberduck](https://cyberduck.io/). Both connect to `sftp.nsls2.bnl.gov` with
the BNL username, ask for the password and Duo, and let a folder be dragged to
the local disk.

Narrow the remote folder before copying. Copying a whole proposal is rarely what
anyone wants.

### Data already on this computer

Nothing to configure. Open **Data Sources & Mounts**, choose **Data already on
this computer**, enter the folder, and select **Register folder for the other
pages**. A local disk, an external drive, and a laboratory network share are all
treated identically to a mount, and every page — Data Selection, the four
explorers, Quick Plot, Publication Plot — works exactly the same way.

### Mount troubleshooting

- `Permission denied` usually means the BNL password/Duo authentication failed
  or the account is not authorized for that proposal.
- `Connection timed out` usually means the BNL VPN or network route is needed.
- A mount that worked earlier but is now empty may need to be unmounted and
  reconnected after a network interruption.
- pyScattViz never writes credentials into its configuration. It saves only
  remote-to-mounted path mappings in `~/.pyscattviz/path_mappings.json`, saved
  dataset collections in `~/.pyscattviz/collections/`, and output preferences in
  `~/.pyscattviz/settings.json`.
- Never unmount while a frame is actively loading.

## Selecting the data you care about

The **Data Selection** page is the GUI form of the `ls_dir` helper I have used in
pyScatt for years. Give it search roots and three term lists:

| List | Meaning |
|---|---|
| **Must contain (AND)** | every term must appear |
| **May contain (OR)** | at least one term must appear |
| **Must not contain (EXCLUDE)** | no term may appear |

A term is a plain substring unless it contains a shell wildcard (`*`, `?`, `[`),
in which case it is matched against the whole name. Matching ignores case.
Separate terms with commas, semicolons, or new lines.

Search **Folders** (the usual choice) or **Files**, match on the folder *name* or
on the whole *path* — `Results` AND `giwaxs` matched on the path is how you find
every result folder in a proposal — and limit the depth so a broad search over a
network mount cannot run forever.

Whatever you tick goes into a **dataset basket**: an ordered list of full paths
that Quick Plot and the explorers read directly. A basket can be saved under a
name and reopened next week; the file is plain JSON under
`~/.pyscattviz/collections/` and holds nothing but paths.

If you already have the paths — from an email, a notebook, a previous session —
use the **Paste full paths** tab instead. Folders and files may be mixed, and an
original `/nsls2/...` path is translated through the registered mount mappings.

The same logic is available from Python:

```python
from pyscattviz.discovery import find_folders, ls_dir

ls_dir("/mnt/proposal/Results/giwaxs/cir_avg", and_list=["sampleA"], no_list=["AgBH"])

rows, truncated = find_folders(
    ["/mnt/proposal"],
    and_list=["Results"],
    or_list=["giwaxs", "gisaxs"],
    no_list=["test"],
    match_on="path",
    max_depth=5,
)
```

## Plotting a list of files

**Quick Plot** takes the dataset basket, one folder, or a pasted list of full
paths and plots it. No reduction layout is required — it reads:

| Kind | Extensions |
|---|---|
| Curves | `.csv`, `.txt`, `.dat`, `.chi`, `.xy` |
| Arrays | `.npz`, `.npy` |
| Images | `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg` |

Comment blocks, missing headers, Fit2D `.chi` header blocks, and
comma/tab/semicolon/whitespace delimiters are all handled. `q_ca`/`iq_ca` and
`q`/`I` are recognized automatically; any other column can be chosen by name.

The three plotting tabs are:

- **1D curves** — overlay, normalize (maximum, integral, or at a chosen x),
  offset additively or multiplicatively, log axes, x range, automatic legend
  trimming of the boilerplate every beamline stem carries, and a matching
  matplotlib publication figure with the science/notebook/presentation/poster
  themes.
- **Stacked map** — interpolate every curve onto one x grid and show the set as
  an intensity map or a waterfall. This is how an in-situ or angle series is
  read at a glance.
- **2D images** — detector images and 2D arrays with robust percentile contrast,
  log/linear colour, equal aspect, and vertical flip.

## Saving figures to your own folder

pyScattViz runs on your computer, so it writes where you tell it to. Every page
that draws something has a **💾 Save to disk** panel:

- one **output root**, which you set on the **Output Folder** page and which is
  remembered between sessions in `~/.pyscattviz/settings.json`;
- one **subfolder per page**, so a figure from the GIWAXS Explorer lands in
  `<output root>/GIWAXS_Explorer/` and a Publication Plot lands in
  `<output root>/Publication_Plot/`;
- an optional extra subfolder for a sample or session name, and an optional date
  subfolder;
- no silent overwriting — a repeated name becomes `name_001`, `name_002`, …
  unless **Overwrite** is turned on.

Figures can be written as PNG, SVG, PDF, interactive HTML, or Plotly JSON;
matplotlib figures also as EPS and TIFF. The plotted table can be written beside
the figure as CSV, and the displayed array as NPZ or NPY, so a figure and the
numbers behind it stay together.

Static images of the interactive Plotly figures are produced by the free
`kaleido` package, which is installed with pyScattViz. On a computer with no
Chrome or Chromium, run `plotly_get_chrome` once in the same environment; HTML
export works without it.

The default output root is `~/pyScattViz_Output`. `PYSCATTVIZ_OUTPUT_DIR`
overrides it for a new installation.

The same helpers are available from Python:

```python
from pyscattviz.exporting import resolve_output_dir, save_matplotlib_figure

folder = resolve_output_dir("~/pyScattViz_Output", "GIWAXS Explorer", create=True)
save_matplotlib_figure(fig, folder, "sample_A_cir_avg", fmt="png", dpi=300)
```

## File selection and lazy loading

The **File Selection** page scans directory entries but does not open images,
NPZ arrays, or CSV tables. A configurable cap prevents a broad match from
building an unbounded in-memory table. The viewer opens only the current frame.

Boolean expressions support `AND`, `OR`, `NOT`, parentheses, quoted phrases,
and wildcards:

```text
sampleA AND (0.1000deg OR 0.1500deg) NOT AgBH
"sample one" OR sample_two
sampleA_*_WAXS
```

Adjacent terms imply `AND`. A pasted or uploaded filename list provides exact
selection. Product prefixes and extensions are normalized, so
`Cir_Avg_sample.tif.csv`, `qimg_sample.tif.npz`, and `sample` select the same
frame.

## Geometry-specific scattering explorers

The four experiment geometries have independent pages and independent widget
state. They share tested file loaders and plotting primitives, but not a single
set of scientific defaults.

| Explorer | Default q axis | Geometry preset (Å⁻¹) | Primary review tools |
|---|---|---:|---|
| GISAXS | logarithmic I(q) | 0.001–0.5 | low-q qx/qz maps and band cuts |
| GIWAXS | linear q | 0–3.0 | wide-q orientation maps and q–φ cuts |
| Transmission SAXS | logarithmic I(q) | 0.001–0.5 | SAXS detector path, anisotropy, low-q I(q) |
| Transmission WAXS | linear q | 0–3.5 | WAXS detector path, orientation, high-q I(q) |

**Axis limits start blank, which means each panel scales to the frame it is
showing.** I checked the old fixed defaults against real CMS and SMI output and
they clipped most of it: a CMS GIWAXS q–φ map reaches 3 Å⁻¹ and an SMI one
reaches 7, transmission WAXS reaches 9, every q-image carries negative qz that a
0-based minimum hid, and φ runs −179 … +179 rather than 0 … 180. The q a
reduction covers depends on the detector, its distance, and the photon energy,
so no fixed number stays right for long.

Three buttons sit above the limit boxes: **Fit to this frame** fills them from
the frame's own arrays, the **geometry preset** restores the values in the table
above, and **Clear back to auto** empties them again.

Every explorer also exposes editable intensity limits, detector/raw paths,
line-cut centers and widths, filename filtering, and product selection. Large 2D products are downsampled
for browser display; line cuts use the selected loaded array.

Any panel, and any set of line cuts, can be written to disk from the explorer
itself. **Export every filtered frame** renders the same panel for each frame
that passes the current filters and writes the set into its own subfolder — a
contact sheet of an angle series or an in-situ run, in one click. Frames that
lack that product are reported rather than silently dropped.

Each explorer sidebar also lists the folders in the dataset basket, so moving
between samples does not mean retyping a mounted path.

## Plotting Studio

The **Plotting Studio** exposes the principal plotting tools in the web GUI:

- **1D:** multiple curves, normalization, log axes, markers, unified hover, and
  plotted-table CSV download;
- **2D:** NPY/NPZ, numeric table, detector-image, or saved q-image input with
  robust percentile contrast and linear/log color display;
- **3D:** interactive surfaces, wireframes, and top-down contours from demo or
  uploaded matrices;
- **Multi-axes:** grids, main-plus-residual layouts, and named mosaics using the
  science, notebook, presentation, or poster themes, with PNG/SVG/PDF export.

The page uses the same supported `pyscattviz.plotting` functions available to
notebooks and scripts. NPY/NPZ uploads are loaded with Python object pickles
disabled.

## Publication plots

The **Publication Plot** page reads only the explicitly selected circular-average
CSVs. It supports science/notebook/presentation/poster themes, maximum or
integral normalization, q-range selection, log axes, vertical offsets, legend
control, and PNG/SVG/PDF output either as a download or straight to disk.

## Python plotting API

The earlier `pyViz` functionality lives under the supported pyScattViz
namespace:

```python
import numpy as np
import pyscattviz.plotting as pv

pv.set_theme("science")

q = np.logspace(-3, 0, 200)
intensity = 1e3 * q**-2
ax = pv.plot1d(intensity, x=q, logx=True, logy=True, xlabel=r"q ($\AA^{-1}$)", ylabel="I(q)")
ax.figure.savefig("scattering_curve.svg", bbox_inches="tight")
```

The API includes 1D overlays and fits, 2D images and transforms, 3D plots,
N-D correlations, custom scattering colormaps, multi-panel layouts, ROI
overlays, safe scientific labels, and figure serialization. See
[the plotting API guide](docs/PLOTTING_API.md).

## Supported reduction layout

The scattering viewers recognize these direct product folders:

```text
gisaxs/ or giwaxs/
├── cir_avg/     # Cir_Avg_*.csv
├── q_image/     # qimg_*.npz
├── qc/          # qc_*.png, .tif, ...
├── qphi/        # qphi_*.npz
└── stitched/    # optional CMS stitched/raw images
```

The same reduced-product names are supported for transmission SAXS/WAXS.
The transmission page also accepts editable raw-image locations used by CMS
and SMI. Data that does not follow this layout is not a problem — use Data
Selection and Quick Plot instead.

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
```

More detail is available in [the user guide](docs/USER_GUIDE.md),
[the mount guide](docs/MOUNTS.md), and
[the plotting API guide](docs/PLOTTING_API.md).

The development/session handoff is maintained in [recorde.md](recorde.md).

## Contact and license

I welcome issue reports at <https://github.com/yugangzhang/pyScattViz/issues>.
Scientific-use questions can be sent to Yugang Zhang at `yuzhang@bnl.gov`.

pyScattViz is released under the MIT License.
