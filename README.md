# pyScattViz

We developed **pyScattViz** to help NSLS-II collaborators access and review
GISAXS, GIWAXS, SAXS, and WAXS reduction products on their own computers. The
application runs locally on Windows, macOS, and Linux. NSLS-II proposal storage
is mounted over SFTP so directory entries and opened frames cross the network on
demand; the complete proposal is not copied to the local computer.

The package focuses on data review. It includes lazy filename selection, QC
images, q-space images, q–φ maps, circular averages, interactive line cuts,
publication-figure export, and a reusable Python plotting API. I consolidated
my earlier `pyViz` plotting work into this repository so one installation now
covers both GUI review and notebook/script plotting.

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
.\.venv\Scripts\python.exe -m pip install --upgrade .
.\start_windows.bat
```

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

## Mount NSLS-II proposal data

pyScattViz needs normal filesystem paths because NumPy, pandas, and image
readers open the selected CSV, NPZ, and image files directly. An SFTP mount
makes the remote proposal appear as a local folder. The bytes for an opened
frame still cross the network, but the complete proposal is never copied.

Open **Data Sources & Mounts** in pyScattViz first. Enter the beamline, cycle,
proposal, and BNL username. The page generates the exact commands, tests the
mounted path, and saves its path mapping. Password and Duo prompts must run in
a real terminal or desktop mount client; the web GUI intentionally never
receives or stores credentials.

The example used below is:

```text
/nsls2/data/smi/proposals/2026-2/pass-319371
```

### Windows 10 or 11

Windows OpenSSH can authenticate to the NSLS-II SFTP server with BNL password
and Duo, but SSHFS-Win cannot complete this keyboard-interactive 2FA sequence.
The practical native-Windows mount is Mountain Duck:

1. Connect to the BNL VPN if the SFTP service is unavailable from the current
   network.
2. Test SFTP in PowerShell:

   ```powershell
   sftp yuzhang@sftp.nsls2.bnl.gov
   ```

3. Enter the BNL password, enter `1` for Duo Push, approve it, and run:

   ```text
   ls /nsls2/data/smi/proposals/2026-2/pass-319371
   exit
   ```

4. Install the [Mountain Duck Windows trial](https://mountainduck.io/). It is
   commercial software after the trial.
5. Create an **SFTP** bookmark:

   ```text
   Server:       sftp.nsls2.bnl.gov
   Port:         22
   Username:     your BNL username
   Path:         /nsls2/data/smi/proposals/2026-2/pass-319371
   Connect mode: Online
   ```

6. Verify the server's ED25519 fingerprint before accepting it:

   ```text
   SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE
   ```

7. Connect using the BNL password and Duo. **Online** mode downloads an opened
   file through an on-demand local cache. It does not synchronize the complete
   proposal. Disconnect the bookmark when the review is finished.
8. In **Data Sources & Mounts**, enter the mounted location shown by File
   Explorer, select **Test mounted path**, then **Register mount for File
   Selection**.
9. In File Selection, browse from the mounted proposal root to a result folder,
   for example:

   ```text
   Z:\projects\microbeam_Kim\Results\giwaxs
   ```

   Use the actual drive or mounted location shown on the computer; it may not
   be `Z:`.

Free Windows alternatives are running pyScattViz and Linux SSHFS inside WSL, or
asking NSLS-II support to register an SSH public key and then using SSHFS-Win
key authentication. Do not retry `\\sshfs.r\...` with a password: that provider
does not support the required Duo prompt.

### Linux

Install SSHFS:

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install sshfs

# Fedora/RHEL alternative
sudo dnf install fuse-sshfs
```

Create a proposal-specific mount point and mount it:

```bash
mkdir -p "$HOME/NSLS_II_Link/smi-pass-319371"
sshfs -o follow_symlinks,reconnect,ServerAliveInterval=15,ServerAliveCountMax=3 \
  yuzhang@sftp.nsls2.bnl.gov:/nsls2/data/smi/proposals/2026-2/pass-319371/ \
  "$HOME/NSLS_II_Link/smi-pass-319371"
```

On the first connection, accept the host only if its ED25519 fingerprint is
`SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE`. Enter the BNL password,
select Duo option `1`, and approve the push. Test it:

```bash
ls "$HOME/NSLS_II_Link/smi-pass-319371"
```

Register that folder under **Data Sources & Mounts**. Unmount later with:

```bash
fusermount3 -u "$HOME/NSLS_II_Link/smi-pass-319371" || \
  fusermount -u "$HOME/NSLS_II_Link/smi-pass-319371"
```

The proposal SFTP server is direct; it does not require the two-hop beamline
workstation jump used for some legacy data.

### macOS

Install Homebrew if needed, then install macFUSE and SSHFS:

```bash
brew install --cask macfuse
brew install gromgit/fuse/sshfs-mac
```

macOS may require approval of the macFUSE system extension under **System
Settings → Privacy & Security** and may request a restart. Then mount:

```bash
mkdir -p "$HOME/NSLS_II_Link/smi-pass-319371"
sshfs -o follow_symlinks,reconnect,ServerAliveInterval=15,ServerAliveCountMax=3 \
  yuzhang@sftp.nsls2.bnl.gov:/nsls2/data/smi/proposals/2026-2/pass-319371/ \
  "$HOME/NSLS_II_Link/smi-pass-319371"
```

On the first connection, accept the host only if its ED25519 fingerprint is
`SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE`. Enter the BNL password,
select Duo option `1`, approve the push, and register the mounted folder under
**Data Sources & Mounts**. Unmount with:

```bash
umount "$HOME/NSLS_II_Link/smi-pass-319371"
```

Mountain Duck Online mode is also available on macOS when a desktop mount is
preferred.

### Mount troubleshooting

- `Permission denied` usually means the BNL password/Duo authentication failed
  or the account is not authorized for that proposal.
- `Connection timed out` usually means the BNL VPN or network route is needed.
- A mount that worked earlier but is now empty may need to be unmounted and
  reconnected after a network interruption.
- pyScattViz never writes credentials into its configuration. It saves only
  remote-to-mounted path mappings in `~/.pyscattviz/path_mappings.json`.
- Never unmount while a frame is actively loading.

## File selection and lazy loading

The **File Selection** page scans directory entries but does not open images,
NPZ arrays, or CSV tables. A configurable cap prevents a broad match from
building an unbounded in-memory table. The viewer opens only the current frame.

Boolean expressions support `AND`, `OR`, `NOT`, parentheses, quoted phrases,
and wildcards:

```text
Kim AND (0.1000deg OR 0.1500deg) NOT AgBH
"sample one" OR sample_two
Kim_*_WAXS
```

Adjacent terms imply `AND`. A pasted or uploaded filename list provides exact
selection. Product prefixes and extensions are normalized, so
`Cir_Avg_sample.tif.csv`, `qimg_sample.tif.npz`, and `sample` select the same
frame.

## Publication plots

The **Publication Plot** page reads only the explicitly selected circular-average
CSVs. It supports science/notebook/presentation/poster themes, maximum or
integral normalization, q-range selection, log axes, vertical offsets, legend
control, and PNG/SVG/PDF downloads.

## Python plotting API

The earlier `pyViz` functionality now lives under the supported pyScattViz
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
and SMI.

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
```

More detail is available in [the user guide](docs/USER_GUIDE.md),
[the mount guide](docs/MOUNTS.md), and
[the plotting API guide](docs/PLOTTING_API.md).

## Contact and license

I welcome issue reports at <https://github.com/yugangzhang/pyScattViz/issues>.
Scientific-use questions can be sent to Yugang Zhang at `yuzhang@bnl.gov`.

pyScattViz is released under the MIT License.
