# pyScattViz

I developed **pyScattViz** to help NSLS-II collaborators transfer and review
GISAXS, GIWAXS, SAXS, and WAXS reduction products on their own computers. The
application runs locally on Windows, macOS, and Linux. Globus is the recommended
route from the NSLS2 collection to a local folder. An authenticated Globus CLI
session can browse proposal folders without transferring the whole tree.

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

## NSLS-II Globus workflow

1. Connect to the BNL campus network or VPN when required by the local setup.
2. Install and start Globus Connect Personal.
3. Sign in at [Globus](https://app.globus.org/file-manager) with Brookhaven
   National Laboratory and BNL Domain credentials.
4. Search Collections for `NSLS2`; leave all collection filters unchecked.
5. Enter a proposal path such as:

   ```text
   /nsls2/data/cms/proposals/2026-2/pass-xxxxxx
   ```

   For SMI, replace `cms` with `smi`.
6. Transfer the required folders to the personal collection. For visualization,
   transferring only `Results/gisaxs`, `Results/giwaxs`, `Results/tsaxs`, or
   `Results/twaxs` is much smaller than transferring the complete raw dataset.
7. Start pyScattViz and save the local destination on **Globus & Data Sources**.

To browse NSLS-II directory names without transferring them, authenticate the
Globus CLI once from the repository folder:

```powershell
.\.venv\Scripts\globus.exe login
```

On macOS or Linux, the equivalent command is:

```bash
./.venv/bin/globus login
```

After the BNL browser login and Duo verification succeed, start pyScattViz and
open **Globus & Data Sources → Globus CLI browser**. Select **Check Globus
login**, paste the `/nsls2/data/...` path, and select **List remote folder**.
The first listing may require one additional collection-specific consent. If
the GUI requests it, run:

```powershell
.\.venv\Scripts\globus.exe session consent "urn:globus:auth:scope:transfer.api.globus.org:all" "https://auth.globus.org/scopes/819379a8-47db-439d-a5ba-a2387b79add9/data_access"
```

Complete the BNL browser approval/Duo flow, return to the GUI, and select
**Retry remote listing after consent**. The GUI does not need to be restarted,
and this consent is normally required only once. On macOS/Linux, substitute
`./.venv/bin/globus` for `.\.venv\Scripts\globus.exe`.

The collection UUID is editable in the GUI. Select **Refresh current NSLS2
collection ID** if NSLS-II replaces the collection in the future; the browser
will search for the current non-retired `NSLS2` collection.
This remote browser does not download arrays. Viewer loading will use a
selective local Globus cache rather than a mounted Windows drive.

Official references:

- [NSLS-II Globus instructions](https://wiki-nsls2.bnl.gov/MX/index.php?title=Globus)
- [BNL illustrated Globus guide](https://www.bnl.gov/cryo-em/userguide/files/globus-access.pdf)
- [Globus Connect Personal documentation](https://docs.globus.org/globus-connect-personal/)

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
[the Globus guide](docs/GLOBUS.md), and
[the plotting API guide](docs/PLOTTING_API.md).

## Contact and license

I welcome issue reports at <https://github.com/yugangzhang/pyScattViz/issues>.
Scientific-use questions can be sent to Yugang Zhang at `yuzhang@bnl.gov`.

pyScattViz is released under the MIT License.
