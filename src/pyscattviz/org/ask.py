"""
Ask AI about an org: a question in plain words, answered by an AI model from
the org's records — and, for a folder not yet an org, a proposal of how to
read it.

pyScattViz does not hold a model. It uses the command-line AI tools
configured on the machine it runs on, for the user who runs it
(:func:`backends`):

==========  ==============================================================
``codex``   the user's Codex configuration (``$CODEX_HOME/config.toml``):
            its model and provider
``claude``  Claude Code, all tools off
``gemini``  Gemini CLI, read-only (plan) mode
``ollama``  one backend per local model (``ollama list``), if its server runs
==========  ==============================================================

Which models a user is offered is theirs to say, outside the repository, in
``~/.config/pyScattViz/ask.json`` (or the file ``PYSCATTVIZ_ASK_CONFIG``
names; :func:`user_config`)::

    {"models": [{"tool": "codex", "model": "<a model>"},
                {"tool": "claude", "model": "<another>", "note": "fast"}],
     "env": {"<VARIABLE THE TOOL READS>": "$<VARIABLE IT IS IN>"}}

The models listed come first, the first the default, in place of that
tool's own default; ``env`` is passed to the tools, ``$NAME`` taken from the
environment (a key is named, never written).

**Asking** (:func:`ask`): the org goes to the model as text
(:func:`context`) — what it is, raw against reduced per folder and
detector, one line per sample, and the frames of the samples the question
names. The model is told to answer from them alone (:func:`prompt`) and
runs in an empty temporary folder with no tools it needs to use.

**Proposing** (:func:`propose_source`): the model is shown a data folder's
tree — folder names, file counts, a few file names
(:func:`pyscattviz.org.layouts.describe_tree`), never a file's contents —
and the layouts there are, and answers with one as JSON. The proposal is
checked (:func:`pyscattviz.org.layouts.check_options`) and only shown: the
user looks at the frames it reads and builds the org, or does not.

Nothing is written by a model. A model bills the account of whoever runs
the GUI, so asking is on for a local GUI and off on a password-protected
one unless its owner turns it on (``PYSCATTVIZ_ASK=1``, ``pyscattviz
--ask``; :func:`enabled`).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from pyscattviz.org import cms, layouts

ASK_ENV = "PYSCATTVIZ_ASK"
DEFAULT_ENV = "PYSCATTVIZ_AI_DEFAULT"
MODEL_ENV = "PYSCATTVIZ_AI_MODEL"
CONFIG_ENV = "PYSCATTVIZ_ASK_CONFIG"
#: The user's own list of models (see the module's docstring).
USER_CONFIG = "~/.config/pyScattViz/ask.json"
PASSWORD_ENV = "PYSCATTVIZ_PASSWORD"
#: Samples whose frames go with a question, at most.
MAX_NAMED = 6
#: Frames listed per named sample, at most.
MAX_FRAMES = 150
#: Characters of context the model is given, at most (the frames of named
#: samples are dropped from the end first).
MAX_CONTEXT = 60_000
TIMEOUT_S = 240


# ---------------------------------------------------------------------------
# The models on this machine
# ---------------------------------------------------------------------------


@dataclass
class Backend:
    """One way of asking: a command line that reads the prompt on stdin.
    ``{out}`` in *argv* becomes a file the tool writes its answer to (when
    *output* is ``"file"``); otherwise the answer is its stdout."""

    key: str
    title: str
    argv: Tuple[str, ...]
    model: str = ""
    available: bool = True
    note: str = ""
    output: str = "stdout"  # "stdout" | "file"
    env: Dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """``codex · <model> (<provider>)``."""
        model = f" · {self.model}" if self.model else ""
        note = f" ({self.note})" if self.note else ""
        return f"{self.title}{model}{note}"


def _top_level(path: Path) -> Dict[str, str]:
    """The top-level ``key = "value"`` pairs of a TOML file (before its
    first table), without needing a TOML reader."""
    out = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        if line.strip().startswith("["):
            break
        match = re.match(r'^\s*([A-Za-z0-9_.-]+)\s*=\s*"([^"]*)"', line)
        if match:
            out[match.group(1)] = match.group(2)
    return out


def codex_config() -> Dict[str, str]:
    """The user's Codex defaults: ``model`` and ``model_provider``."""
    home = Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser()
    return _top_level(home / "config.toml")


def user_config() -> Dict:
    """The user's own models and environment for asking (``ask.json``,
    outside the repository): ``{"models": [...], "env": {...}}``, empty when
    there is none or it cannot be read."""
    path = Path(os.environ.get(CONFIG_ENV) or USER_CONFIG).expanduser()
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _env(config: Mapping) -> Dict[str, str]:
    """``env`` of the user's config, ``$NAME`` taken from the environment;
    a variable that is not set is left out."""
    out = {}
    for name, value in (config.get("env") or {}).items():
        value = os.path.expandvars(str(value))
        if value and "$" not in value:
            out[str(name)] = value
    return out


def _codex(model: str = "", note: str = "") -> Backend:
    config = codex_config()
    model = model or os.environ.get(MODEL_ENV, "")
    argv = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--color",
        "never",
        "-c",
        'model_reasoning_effort="low"',
        "-o",
        "{out}",
    ]
    if model:
        argv += ["-c", f'model="{model}"']
    provider = config.get("model_provider", "")
    return Backend(
        f"codex:{model}" if model else "codex",
        "codex",
        tuple(argv + ["-"]),
        model=model or config.get("model", ""),
        available=shutil.which("codex") is not None,
        note=", ".join(n for n in (provider, note) if n),
        output="file",
    )


def _claude(model: str = "", note: str = "") -> Backend:
    argv = ["claude", "-p", "--tools", "", "--output-format", "text", "--no-session-persistence"]
    if model:
        argv += ["--model", model]
    return Backend(
        f"claude:{model}" if model else "claude",
        "claude",
        tuple(argv),
        model=model or os.environ.get("ANTHROPIC_MODEL", ""),
        note=note,
        available=shutil.which("claude") is not None,
    )


def _gemini(model: str = "", note: str = "") -> Backend:
    settings = Path("~/.gemini/settings.json").expanduser()
    found_model = ""
    try:
        found = json.loads(settings.read_text(encoding="utf-8")).get("model", "")
        found_model = found.get("name", "") if isinstance(found, dict) else str(found)
    except (OSError, ValueError, AttributeError):
        pass
    argv = [
        "gemini",
        "-p",
        "Answer the question above, as instructed.",
        "--approval-mode",
        "plan",
        "-o",
        "text",
    ]
    if model:
        argv += ["-m", model]
    return Backend(
        f"gemini:{model}" if model else "gemini",
        "gemini",
        tuple(argv),
        model=model or found_model,
        note=note,
        available=shutil.which("gemini") is not None,
    )


_TOOLS = {"codex": _codex, "claude": _claude, "gemini": _gemini}


def _configured(config: Mapping) -> List[Backend]:
    """The models the user listed, as backends."""
    out = []
    for entry in config.get("models") or []:
        if not isinstance(entry, Mapping) or entry.get("tool") not in _TOOLS:
            continue
        out.append(_TOOLS[entry["tool"]](str(entry.get("model", "")), str(entry.get("note", ""))))
    return out


def _ollama() -> List[Backend]:
    if shutil.which("ollama") is None:
        return []
    try:
        listed = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return []
    if listed.returncode != 0:
        return []
    names = [line.split()[0] for line in listed.stdout.splitlines()[1:] if line.strip()]
    return [
        Backend(f"ollama:{name}", "ollama", ("ollama", "run", name), model=name, note="local")
        for name in names
    ]


def backends(*, include_missing: bool = False) -> List[Backend]:
    """The AI tools configured here, the default first: the models the user
    listed (:func:`user_config`), then codex, claude, gemini — each tool's
    own default unless the user listed models of it — and the local ollama
    models; or first the one named by ``PYSCATTVIZ_AI_DEFAULT``. Tools not
    installed are left out unless *include_missing*."""
    config = user_config()
    listed = _configured(config)
    own = {b.title for b in listed}
    found = listed + [make() for tool, make in _TOOLS.items() if tool not in own] + _ollama()
    env = _env(config)
    for b in found:
        b.env = {**env, **b.env}
    if not include_missing:
        found = [b for b in found if b.available]
    first = os.environ.get(DEFAULT_ENV, "")
    if first:
        found.sort(key=lambda b: first not in (b.key, b.title, b.model))
    return found


def enabled() -> bool:
    """Whether this GUI may ask: ``PYSCATTVIZ_ASK`` on or off; unset, only a
    GUI without a password (a local one) asks — on a shared server the model
    would bill its owner's account."""
    wanted = os.environ.get(ASK_ENV, "").strip().lower()
    if wanted in ("1", "true", "yes", "on"):
        return True
    if wanted in ("0", "false", "no", "off"):
        return False
    return not os.environ.get(PASSWORD_ENV)


def _chosen(backend) -> Optional[Backend]:
    if isinstance(backend, Backend):
        return backend
    found = backends()
    if backend:
        return next((b for b in found if b.key == backend), None)
    return found[0] if found else None


def _shown(text: str, *paths: str) -> str:
    """*text* with temporary folders and the home folder not spelled out."""
    for path, alias in [(p, "<tmp>") for p in paths] + [(str(Path.home()), "~")]:
        text = text.replace(path, alias)
    return text


def _run(chosen: Backend, full: str, timeout: float) -> Tuple[str, str, float]:
    """``(answer, error, seconds)`` of *chosen* given the prompt *full*, run
    in an empty temporary folder. Never raises."""
    with tempfile.TemporaryDirectory(prefix="pyscattviz-ask-") as tmp:
        work = Path(tmp) / "work"
        work.mkdir()
        out = Path(tmp) / "answer.md"
        argv = [a.replace("{out}", str(out)) for a in chosen.argv]
        start = time.monotonic()
        error, text = "", ""
        try:
            if shutil.which(argv[0]) is None:
                raise FileNotFoundError(argv[0])
            run = subprocess.run(
                argv,
                input=full,
                capture_output=True,
                text=True,
                cwd=work,
                timeout=timeout,
                env={**os.environ, **chosen.env},
            )
            if chosen.output == "file" and out.is_file():
                text = out.read_text(encoding="utf-8")
            else:
                text = run.stdout
            if run.returncode != 0:
                tail = "\n".join((run.stderr or run.stdout).strip().splitlines()[-6:])
                error = f"{chosen.title} stopped (exit {run.returncode}): {tail}"
        except FileNotFoundError:
            error = f"{argv[0]} is not installed here."
        except subprocess.TimeoutExpired:
            error = f"{chosen.title} took longer than {timeout:.0f} s."
        except OSError as exc:
            error = f"{chosen.title} could not start: {exc}"
        return _shown(text.strip(), tmp), _shown(error, tmp), time.monotonic() - start


NO_MODEL = "No AI model found here (codex, claude, gemini or ollama)."


# ---------------------------------------------------------------------------
# What the model is given
# ---------------------------------------------------------------------------


def _cell(value) -> str:
    if value is None or (not isinstance(value, (str, list, tuple)) and pd.isna(value)):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:g}"
    return str(value)


def _rows(table: pd.DataFrame, columns: Sequence[str]) -> List[str]:
    columns = [c for c in columns if c in table.columns]
    return [" | ".join(columns)] + [
        " | ".join(_cell(r[c]) for c in columns) for r in table.to_dict("records")
    ]


def mentioned(question: str, samples: pd.DataFrame, *, limit: int = MAX_NAMED) -> List[Tuple]:
    """The ``(folder, sample)`` a question names, by sample name (the
    longest names first, so ``film_A10`` is not taken for ``film_A1``), at
    most *limit*."""
    if samples is None or samples.empty or not question:
        return []
    text = question.lower()
    found, taken = [], []
    pairs = sorted(zip(samples["folder"], samples["sample"]), key=lambda p: -len(str(p[1])))
    for folder, sample in pairs:
        name = str(sample).lower()
        for match in re.finditer(re.escape(name), text):
            span = range(match.start(), match.end())
            before = text[match.start() - 1] if match.start() else " "
            after = text[match.end()] if match.end() < len(text) else " "
            if before.isalnum() or after.isalnum() or any(i in t for t in taken for i in span):
                continue
            found.append((folder, sample))
            taken.append(span)
            break
    return found[:limit]


def context(
    frames: pd.DataFrame,
    *,
    question: str = "",
    org=None,
    progress: Optional[pd.DataFrame] = None,
    source=None,
    root=None,
    today: Optional[_dt.date] = None,
    limit: int = MAX_CONTEXT,
) -> str:
    """The org as text for a model: what it is, raw against reduced per
    folder and detector, one line per sample, the frames of the samples the
    question names (:func:`mentioned`) — at most *limit* characters.
    Folder names only: no path on this machine."""
    today = today or _dt.date.today()
    samples = cms.sample_table(frames)
    name = getattr(getattr(getattr(org, "project", None), "config", None), "name", "") or (
        Path(root).name if root else ""
    )
    parts = [
        f"# {name or 'Scattering data'} — X-ray scattering frames, reduced",
        f"Today {today.isoformat()}.",
    ]
    description = getattr(getattr(getattr(org, "project", None), "config", None), "description", "")
    if description:
        parts.append(description)
    if source is not None:
        label = (
            layouts.LAYOUTS[source.layout].label
            if source.layout in layouts.LAYOUTS
            else source.layout
        )
        parts.append(
            f"Read as: {label}"
            + (f", options {json.dumps(source.options)}" if source.options else "")
        )
    parts += [
        "",
        "## How to read the records",
        "- folder: an experiment folder (one measurement campaign: static spots, a "
        "humidity run, spin coating …); det: the detector (saxs, waxs, maxs).",
        "- kind static: spots (pos, x in mm) and incident angles (th, degrees); repeats "
        "are frames of the same spot and angle.",
        "- kind insitu: a run in time — time_s from the run's first frame; RH (%) and "
        "T_C (°C) where the names carry them.",
        "- I(q) is the circular average (cir); q-image and q–φ are 2D maps; QC is a "
        "quick-look picture. 'still to reduce' are raw frames without I(q) yet.",
    ]
    if progress is not None and not progress.empty:
        parts += ["", "## Raw against reduced, per folder and detector"]
        shown = progress.rename(
            columns={
                "cir": "I(q)",
                "qimg": "q-image",
                "qphi": "q-phi",
                "to_reduce": "still to reduce",
                "raw_changed": "last raw",
                "reduced_changed": "last reduced",
            }
        )
        parts += _rows(
            shown,
            [
                "folder",
                "det_folder",
                "raw",
                "stitched",
                "I(q)",
                "q-image",
                "q-phi",
                "qc",
                "still to reduce",
                "last raw",
                "last reduced",
            ],
        )
    parts += [
        "",
        f"## Samples ({len(samples)}; {len(frames)} reduced frames in all), one line each",
    ]
    parts += _rows(samples, list(samples.columns))
    if org is not None:
        notes = [
            f"- {s.sample_id}: {s.notes}" + (f" [tags: {', '.join(s.tags)}]" if s.tags else "")
            for s in org.project.samples.values()
            if s.notes or s.tags
        ]
        if notes:
            parts += ["", "## Notes and tags kept in the org"] + notes
    text = "\n".join(parts)
    columns = [
        "det",
        "stem",
        "pos",
        "x",
        "th",
        "exposure_s",
        "scan",
        "frame",
        "index",
        "elapsed_s",
        "RH",
        "T_C",
    ]
    for folder, sample in mentioned(question, samples):
        own = cms.frames_of(frames, folder, sample)
        more = len(own) - MAX_FRAMES
        block = "\n".join(
            [f"\n\n## Frames of {sample} in {folder} ({len(own)})"]
            + _rows(own.head(MAX_FRAMES), columns)
            + ([f"(+{more} more frames left out)"] if more > 0 else [])
        )
        if len(text) + len(block) > limit:
            text += "\n\n(frames of further named samples left out for length)"
            break
        text += block
    return text[:limit]


def prompt(question: str, records_text: str, history: Sequence[Tuple[str, str]] = ()) -> str:
    """The instructions, the records and the question, as one prompt."""
    before = "".join(f"\nQ: {q}\nA: {a[:1500]}\n" for q, a in list(history)[-3:])
    return (
        "You answer questions about an X-ray scattering experiment's records: which samples "
        "were measured, how, and how far the data reduction has got.\n"
        "Rules:\n"
        "- Answer only from the records below. If something is not in them, say plainly that "
        "it is not in the records — do not guess. The records hold names and counts, not the "
        "scattering itself: say so when a question needs the data.\n"
        "- Name the folder and sample for every fact about samples.\n"
        "- Be concise: Markdown, a short list or a small table, no preamble.\n"
        "- Suggestions are welcome when asked: mark them **Suggestion**, and ground each in "
        "named records.\n"
        "- Do not run commands, read files or browse: everything you may use is below.\n"
        "\n=== RECORDS ===\n"
        + records_text
        + "\n=== END OF RECORDS ===\n"
        + (f"\nThe conversation so far:{before}" if before else "")
        + f"\nQuestion: {question}\n"
    )


# ---------------------------------------------------------------------------
# Asking
# ---------------------------------------------------------------------------


@dataclass
class Answer:
    text: str
    backend: str
    model: str
    seconds: float
    prompt_chars: int
    error: str = ""
    samples: List[str] = field(default_factory=list)
    context: str = ""

    def as_dict(self) -> Dict:
        return asdict(self)


def ask(
    question: str,
    frames: pd.DataFrame,
    *,
    backend=None,
    timeout: float = TIMEOUT_S,
    history: Sequence[Tuple[str, str]] = (),
    **context_kwargs,
) -> Answer:
    """*question* answered by *backend* (a :class:`Backend`, a key, or the
    default of :func:`backends`) from the org's *frames* (and what
    :func:`context` takes besides). Never raises: a missing tool, a timeout
    or a failed run comes back as ``Answer.error``."""
    chosen = _chosen(backend)
    records_text = context(frames, question=question, **context_kwargs)
    full = prompt(question, records_text, history)
    named = [
        f"{sample} ({folder})" for folder, sample in mentioned(question, cms.sample_table(frames))
    ]
    if chosen is None:
        return Answer(
            "",
            str(backend or ""),
            "",
            0.0,
            len(full),
            error=NO_MODEL,
            samples=named,
            context=records_text,
        )
    text, error, seconds = _run(chosen, full, timeout)
    return Answer(
        text,
        chosen.key,
        chosen.model,
        seconds,
        len(full),
        error=error,
        samples=named,
        context=records_text,
    )


# ---------------------------------------------------------------------------
# Proposing how a folder is read
# ---------------------------------------------------------------------------


@dataclass
class Proposal:
    """A model's proposal of how to read a folder: a layout, its options, a
    name for the org and why. *error* says what is wrong with it, if
    anything — a proposal with an error is not built from."""

    layout: str = ""
    options: Dict = field(default_factory=dict)
    name: str = ""
    why: str = ""
    error: str = ""
    text: str = ""
    backend: str = ""
    model: str = ""
    seconds: float = 0.0
    prompt_chars: int = 0
    context: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.layout) and not self.error

    def as_dict(self) -> Dict:
        return asdict(self)


def layouts_text() -> str:
    """The layouts there are and the options each takes, for a model."""
    lines = []
    for layout in layouts.LAYOUTS.values():
        lines.append(f"- {layout.key}: {layout.label} — {layout.description}")
        for name, what in layout.options.items():
            lines.append(f"    option {name}: {what}")
    return "\n".join(lines)


def proposal_prompt(tree: str, *, hint: str = "", detected: Optional[str] = None) -> str:
    """The instructions, the layouts and a folder's tree, as one prompt."""
    fields = ", ".join(f"{k} ({t.__name__})" for k, t in layouts.PATTERN_FIELDS.items())
    return (
        "You set up how a viewer of X-ray scattering data reads a data folder: which layout "
        "reads it, and with which options.\n"
        "Rules:\n"
        "- Choose one of the layouts listed, and only options it lists; leave an option out "
        "when what it does by default is right.\n"
        f"- A sample_pattern is a Python regular expression; its named groups may only be: "
        f"{fields}. (?P<sample>…) is required. Check it against the example file names in "
        "the tree: it must match them, and the sample group must hold the sample's name "
        "without the angle, position, time or detector.\n"
        "- Reply with ONE JSON object and nothing else, no code fence: "
        '{"layout": "<key>", "options": {...}, "name": "<a short title for the org>", '
        '"why": "<one or two sentences>"}\n'
        "- Do not run commands, read files or browse: everything you may use is below.\n"
        "\n=== LAYOUTS ===\n"
        + layouts_text()
        + "\n=== END OF LAYOUTS ===\n"
        + (
            f"\nThe viewer's own guess is the layout {detected!r}.\n"
            if detected
            else "\nThe viewer recognised no layout by itself.\n"
        )
        + "\n=== THE FOLDER (names, file counts, a few file names) ===\n"
        + tree
        + "\n=== END OF THE FOLDER ===\n"
        + (f"\nWhat the user says about it: {hint}\n" if hint else "")
    )


def parse_proposal(text: str) -> Proposal:
    """The proposal in a model's reply: its JSON object, checked. Never
    raises — what is wrong is the proposal's *error*."""
    found = Proposal(text=text)
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        found.error = "The reply holds no JSON object."
        return found
    try:
        data = json.loads(body[start : end + 1])
    except ValueError as exc:
        found.error = f"The reply's JSON does not read: {exc}"
        return found
    if not isinstance(data, dict):
        found.error = "The reply's JSON is not an object."
        return found
    found.layout = str(data.get("layout") or "")
    found.name = str(data.get("name") or "")
    found.why = str(data.get("why") or "")
    options = data.get("options") or {}
    if not isinstance(options, dict):
        found.error = "options must be an object."
        return found
    found.options = options
    try:
        found.options = layouts.check_options(found.layout, options)
    except KeyError as exc:
        found.error = str(exc.args[0]) if exc.args else str(exc)
    except ValueError as exc:
        found.error = str(exc)
    return found


def propose_source(
    root, *, backend=None, hint: str = "", timeout: float = TIMEOUT_S, depth: int = 5
) -> Proposal:
    """A model's proposal of how to read the folder *root* (a
    :class:`Proposal`, checked, not built). Never raises."""
    root = Path(root)
    tree = layouts.describe_tree(root, depth=depth)
    full = proposal_prompt(tree, hint=hint, detected=layouts.detect_layout(root))
    chosen = _chosen(backend)
    if chosen is None:
        return Proposal(error=NO_MODEL, prompt_chars=len(full), context=tree)
    text, error, seconds = _run(chosen, full, timeout)
    found = parse_proposal(text) if not error else Proposal(text=text, error=error)
    found.backend, found.model, found.seconds = chosen.key, chosen.model, seconds
    found.prompt_chars, found.context = len(full), tree
    return found


__all__ = [
    "ASK_ENV",
    "DEFAULT_ENV",
    "MODEL_ENV",
    "CONFIG_ENV",
    "USER_CONFIG",
    "MAX_NAMED",
    "MAX_CONTEXT",
    "Backend",
    "codex_config",
    "user_config",
    "backends",
    "enabled",
    "mentioned",
    "context",
    "prompt",
    "Answer",
    "ask",
    "Proposal",
    "layouts_text",
    "proposal_prompt",
    "parse_proposal",
    "propose_source",
]
