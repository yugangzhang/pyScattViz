# pyScattViz

I developed **pyScattViz** to help NSLS-II collaborators transfer and review
GISAXS, GIWAXS, SAXS, and WAXS reduction products on their own computers. The
application runs locally on Windows, macOS, and Linux. Globus is the recommended
route from the NSLS2 collection to a local folder.

The package focuses on data review. It includes lazy filename selection, QC
images, q-space images, q–φ maps, circular averages, interactive line cuts,
publication-figure export, and a reusable Python plotting API. I consolidated
my earlier `pyViz` plotting work into this repository so one installation now
covers both GUI review and notebook/script plotting.

## Quick start

Python 3.9–3.12 is supported. I recommend 64-bit Python 3.12 for a new
installation. Follow the section for the operating system in use.

### Windows 10 or 11 — PowerShell

Install Python once before creating the environment. The following command
uses Windows Package Manager:

```powershell
winget install --exact --id Python.Python.3.12
```

If Git is not already installed:

```powershell
winget install --exact --id Git.Git
```

Close every PowerShell window after installation, open a new PowerShell window,
and verify both programs:

```powershell
py -3.12 --version
git --version
```

If `winget` is unavailable, install the 64-bit release from
[python.org/downloads/windows](https://www.python.org/downloads/windows/).
Select **Add python.exe to PATH** and install the **Python launcher (`py`)**,
then reopen PowerShell.

Clone and install pyScattViz:

```powershell
cd $HOME
git clone https://github.com/yugangzhang/pyScattViz.git
cd .\pyScattViz
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\pyscattviz.exe
```

For an existing clone, start at `cd $HOME\pyScattViz`. These commands call the
environment executables directly, so PowerShell script-execution policy does
not need to be changed and environment activation is optional.

If Windows displays “Python was not found; run without arguments to install
from the Microsoft Store,” a real Python installation is missing or the Store
alias is taking precedence. Install Python as shown above and use `py -3.12`
instead of `python`.

### macOS — Terminal

Confirm that Python 3.9 or newer and Git are available:

```bash
python3 --version
git --version
```

If Python is missing or too old, install Python 3.12 from
[python.org/downloads/macos](https://www.python.org/downloads/macos/) or use
Homebrew with `brew install python@3.12 git`. Then run:

```bash
cd "$HOME"
git clone https://github.com/yugangzhang/pyScattViz.git
cd pyScattViz
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install .
./.venv/bin/pyscattviz
```

### Linux — Terminal

On Ubuntu or Debian, install the prerequisites once:

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip
```

On Fedora, use `sudo dnf install git python3`. Then run:

```bash
cd "$HOME"
git clone https://github.com/yugangzhang/pyScattViz.git
cd pyScattViz
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install .
./.venv/bin/pyscattviz
```

### Opening and stopping the application

Open <http://127.0.0.1:8501> if the browser does not open automatically. Stop
the application with `Ctrl+C` in the terminal. The default server address is
local-only so data are not exposed to the campus network.

For a later update on Windows:

```powershell
cd $HOME\pyScattViz
git pull
.\.venv\Scripts\python.exe -m pip install --upgrade .
.\.venv\Scripts\pyscattviz.exe
```

For a later update on macOS or Linux:

```bash
cd "$HOME/pyScattViz"
git pull
./.venv/bin/python -m pip install --upgrade .
./.venv/bin/pyscattviz
```

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
