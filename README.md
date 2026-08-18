# pyScattViz

I developed **pyScattViz** to help NSLS-II collaborators transfer and review
GISAXS, GIWAXS, SAXS, and WAXS reduction products on their own computers. The
application runs locally on Windows, macOS, and Linux. Globus is the recommended
route from the NSLS2 collection to a local folder.

The first public release focuses on data review. It includes lazy filename
selection, QC images, q-space images, q–φ maps, circular averages, interactive
line cuts, and CSV export. It does not include Data Manager or UV-Vis tools.

## Quick start

Python 3.9–3.12 is supported; Python 3.11 or 3.12 is recommended for a new
installation.

```bash
git clone https://github.com/yugangzhang/pyScattViz.git
cd pyScattViz
python -m venv .venv
```

Activate the environment on macOS or Linux:

```bash
source .venv/bin/activate
```

Activate it in Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install and launch:

```bash
python -m pip install --upgrade pip
python -m pip install .
pyscattviz
```

Open <http://127.0.0.1:8501> if the browser does not open automatically.
The default server address is local-only so data are not exposed to the campus
network.

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

More detail is available in [the user guide](docs/USER_GUIDE.md) and
[the Globus guide](docs/GLOBUS.md).

## Contact and license

I welcome issue reports at <https://github.com/yugangzhang/pyScattViz/issues>.
Scientific-use questions can be sent to Yugang Zhang at `yuzhang@bnl.gov`.

pyScattViz is released under the MIT License.
