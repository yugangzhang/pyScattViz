import json
from types import SimpleNamespace

import pytest

from pyscattviz.globus_cli import (
    GlobusCLIError,
    GlobusConsentRequired,
    _run_globus,
    find_current_nsls2_collection,
    find_personal_collections,
    globus_identity,
    globus_task_status,
    list_globus_directory,
    normalize_globus_path,
    submit_file_transfer,
)


def _completed(payload, returncode=0, stderr=""):
    return SimpleNamespace(
        returncode=returncode,
        stdout=json.dumps(payload) if not isinstance(payload, str) else payload,
        stderr=stderr,
    )


def test_globus_identity_uses_existing_cli_login(monkeypatch):
    monkeypatch.setattr(
        "pyscattviz.globus_cli.subprocess.run",
        lambda *args, **kwargs: _completed({"preferred_username": "yuzhang@bnl.gov"}),
    )
    assert globus_identity(executable="globus") == "yuzhang@bnl.gov"


def test_globus_listing_parses_folders_and_files(monkeypatch):
    payload = {
        "DATA": [
            {"name": "projects", "type": "dir", "last_modified": "2026-08-18"},
            {"name": "proposal.pdf", "type": "file", "size": 2048},
        ]
    }
    monkeypatch.setattr(
        "pyscattviz.globus_cli.subprocess.run",
        lambda *args, **kwargs: _completed(payload),
    )
    rows = list_globus_directory(
        "/nsls2/data/smi/proposals/2026-2/pass-319371", executable="globus"
    )
    assert rows[0]["name"] == "projects/"
    assert rows[0]["is_dir"]
    assert rows[1]["size"] == "2.0 KiB"


def test_globus_command_error_is_user_facing(monkeypatch):
    monkeypatch.setattr(
        "pyscattviz.globus_cli.subprocess.run",
        lambda *args, **kwargs: _completed("", returncode=1, stderr="Login required"),
    )
    with pytest.raises(GlobusCLIError, match="Login required"):
        _run_globus(["whoami"], executable="globus")


def test_globus_consent_error_has_a_specific_exception(monkeypatch):
    payload = {
        "code": "ConsentRequired",
        "message": "Missing required data_access consent",
        "required_scopes": ["urn:globus:auth:scope:transfer.api.globus.org:all"],
    }
    monkeypatch.setattr(
        "pyscattviz.globus_cli.subprocess.run",
        lambda *args, **kwargs: _completed("", returncode=4, stderr=json.dumps(payload)),
    )
    with pytest.raises(GlobusConsentRequired, match="one-time") as error:
        _run_globus(
            ["ls", "819379a8-47db-439d-a5ba-a2387b79add9:/path"],
            executable="globus",
        )
    assert error.value.required_scopes == (
        "urn:globus:auth:scope:transfer.api.globus.org:all",
        "https://auth.globus.org/scopes/819379a8-47db-439d-a5ba-a2387b79add9/data_access",
    )


def test_current_nsls2_collection_excludes_retired_and_prefers_domain(monkeypatch):
    payload = {
        "DATA": [
            {
                "id": "old",
                "display_name": "NSLS2 (this endpoint is retired)",
                "domain": "old.data.globus.org",
            },
            {
                "id": "current",
                "display_name": "NSLS2",
                "domain": "globus.nsls2.bnl.gov",
            },
        ]
    }
    monkeypatch.setattr(
        "pyscattviz.globus_cli.subprocess.run",
        lambda *args, **kwargs: _completed(payload),
    )
    assert find_current_nsls2_collection(executable="globus") == "current"


def test_normalize_globus_path():
    assert normalize_globus_path("/nsls2/data/smi/") == "/nsls2/data/smi"
    with pytest.raises(GlobusCLIError):
        normalize_globus_path("relative/path")


def test_find_personal_collections(monkeypatch):
    payload = {
        "DATA": [
            {
                "id": "personal-id",
                "display_name": "Yugang Windows",
                "owner_string": "yuzhang@bnl.gov",
                "gcp_connected": True,
            }
        ]
    }
    monkeypatch.setattr(
        "pyscattviz.globus_cli.subprocess.run",
        lambda *args, **kwargs: _completed(payload),
    )
    assert find_personal_collections(executable="globus") == [
        {
            "id": "personal-id",
            "display_name": "Yugang Windows",
            "owner": "yuzhang@bnl.gov",
            "connected": True,
        }
    ]


def test_submit_selected_files_as_one_batch_and_check_task(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[1:3] == ["task", "show"]:
            return _completed({"task_id": "task-1", "status": "SUCCEEDED"})
        return _completed({"task_id": "task-1"})

    monkeypatch.setattr("pyscattviz.globus_cli.subprocess.run", fake_run)
    task_id = submit_file_transfer(
        "source-id",
        "destination-id",
        [("/remote/q_image/a file.npz", "/cache/q_image/a file.npz")],
        executable="globus",
    )

    assert task_id == "task-1"
    assert "'/remote/q_image/a file.npz' '/cache/q_image/a file.npz'" in calls[0][1][
        "input"
    ]
    assert globus_task_status(task_id, executable="globus")["status"] == "SUCCEEDED"
