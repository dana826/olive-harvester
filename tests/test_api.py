from .conftest import wait_for_status, wait_until_not_harvesting


def test_branches_listed(client):
    resp = client.get("/api/branches")
    assert resp.status_code == 200
    branches = resp.get_json()
    assert len(branches) > 0
    assert "id" in branches[0] and "label" in branches[0]


def test_capture_requires_branch_selected(client):
    resp = client.post("/api/capture")
    assert resp.status_code == 400
    assert "branch" in resp.get_json()["error"].lower()


def test_select_unknown_branch_rejected(client):
    resp = client.post("/api/select-branch", json={"branch_id": "does-not-exist"})
    assert resp.status_code == 400


def test_start_harvest_requires_assessment(client):
    branch_id = client.get("/api/branches").get_json()[0]["id"]
    client.post("/api/select-branch", json={"branch_id": branch_id})
    resp = client.post("/api/harvest/start")
    assert resp.status_code == 400


def test_full_capture_and_harvest_cycle_auto_completes(client, force_class):
    force_class("semi_ripe")
    branch_id = client.get("/api/branches").get_json()[0]["id"]

    resp = client.post("/api/select-branch", json={"branch_id": branch_id})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ready"

    resp = client.post("/api/capture")
    assert resp.status_code == 200
    snapshot = resp.get_json()
    assert snapshot["status"] == "assessed"
    params = snapshot["parameters"]
    assert params["maturity_class"] == "semi_ripe"
    assert params["code"] == "C2"
    assert params["frequency_hz"] == 15.0
    assert params["frequency_hz"] > 0
    assert snapshot["capture"]["image_url"].startswith("/api/captures/")

    # Fetch the actual captured image to confirm it was really written and served.
    image_resp = client.get(snapshot["capture"]["image_url"])
    assert image_resp.status_code == 200
    assert image_resp.content_type == "image/jpeg"

    # Override to a short duration so the test doesn't wait for a full session.
    resp = client.post("/api/harvest/start", json={"duration_s": 1})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "harvesting"

    final = wait_until_not_harvesting(client)
    assert final["status"] == "ready"
    assert final["last_session"] is not None
    assert final["last_session"]["status"] == "completed"
    assert final["last_session"]["branch_id"] == branch_id
    assert final["last_session"]["harvested_mass_g"] >= 0

    history = client.get("/api/history").get_json()
    assert len(history) == 1
    assert history[0]["branch_id"] == branch_id
    assert history[0]["status"] == "completed"


def test_manual_stop_ends_session_early(client, force_class):
    force_class("semi_ripe")
    branch_id = client.get("/api/branches").get_json()[0]["id"]
    client.post("/api/select-branch", json={"branch_id": branch_id})
    client.post("/api/capture")

    resp = client.post("/api/harvest/start", json={"duration_s": 30})
    assert resp.get_json()["status"] == "harvesting"

    resp = client.post("/api/harvest/stop")
    snapshot = resp.get_json()
    assert snapshot["status"] == "ready"
    assert snapshot["last_session"]["status"] == "stopped"

    history = client.get("/api/history").get_json()
    assert history[0]["status"] == "stopped"


def test_cannot_change_branch_while_harvesting(client, force_class):
    force_class("semi_ripe")
    branches = client.get("/api/branches").get_json()
    client.post("/api/select-branch", json={"branch_id": branches[0]["id"]})
    client.post("/api/capture")
    client.post("/api/harvest/start", json={"duration_s": 30})

    resp = client.post("/api/select-branch", json={"branch_id": branches[1]["id"]})
    assert resp.status_code == 400

    client.post("/api/harvest/stop")  # cleanup


def test_alert_resolve_endpoint_is_safe_on_unknown_id(client):
    resp = client.post("/api/alerts/9999/resolve")
    assert resp.status_code == 200


def test_password_protection_when_enabled(tmp_path, monkeypatch):
    import base64

    from app import create_app
    from app.config import AppConfig

    monkeypatch.setenv("OLIVE_PASSWORD", "s3cret")
    config = AppConfig()
    config.data_dir = tmp_path
    config.capture_dir = tmp_path / "captures"
    config.db_path = tmp_path / "db" / "olive_harvester.db"
    client = create_app(config).test_client()

    assert client.get("/api/status").status_code == 401

    bad = base64.b64encode(b"user:wrong").decode()
    assert client.get("/api/status", headers={"Authorization": f"Basic {bad}"}).status_code == 401

    good = base64.b64encode(b"user:s3cret").decode()
    assert client.get("/api/status", headers={"Authorization": f"Basic {good}"}).status_code == 200


def test_profiles_are_inside_motor_range():
    from pathlib import Path
    from app.core.parameters import MAX_FREQUENCY_HZ, MIN_FREQUENCY_HZ, ParameterSelector

    selector = ParameterSelector(Path("config/vibration_profiles.yaml"))
    for name in ("semi_ripe", "ripe", "unknown"):
        hz = selector.select(name).frequency_hz
        assert MIN_FREQUENCY_HZ <= hz <= MAX_FREQUENCY_HZ, name
    unripe = selector.select("unripe")
    assert unripe.harvestable is False
    assert unripe.frequency_hz is None and unripe.duration_s is None  # no pulse planned
    assert unripe.override["frequency_hz"] == 17
    ref = selector.select("semi_ripe")
    assert (ref.frequency_hz, ref.duration_s) == (15.0, 6)
    # Paper, Eq. (1): C4 13.4 Hz, C2 15.0 Hz, C0 17.0 Hz (override only).
    assert selector.select("ripe").frequency_hz == 13.4
    assert (ref.code, selector.select("ripe").code, unripe.code) == ("C2", "C4", "C0")


def test_out_of_range_override_rejected(client, force_class):
    force_class("semi_ripe")
    branch_id = client.get("/api/branches").get_json()[0]["id"]
    client.post("/api/select-branch", json={"branch_id": branch_id})
    client.post("/api/capture")
    resp = client.post("/api/harvest/start", json={"frequency_hz": 55})
    assert resp.status_code == 400
    assert "10-20" in resp.get_json()["error"]


def test_tick_thread_restarts_after_fork(client):
    """Under gunicorn --preload the thread started at import time does not
    exist in the forked worker; the controller must restart it on demand."""
    import os

    controller = client.application.extensions["controller"]
    controller._thread_pid = -1  # simulate "thread belongs to another process"
    old_thread = controller._thread
    client.get("/api/status")
    assert controller._thread_pid == os.getpid()
    assert controller._thread is not old_thread
    assert controller._thread.is_alive()


# ---------------------------------------------------------------------
# Unripe (C0): advisory, operator confirmation, timeout, "not attempted"
# ---------------------------------------------------------------------

def _assess_unripe(client, force_class):
    force_class("unripe")
    branch_id = client.get("/api/branches").get_json()[0]["id"]
    client.post("/api/select-branch", json={"branch_id": branch_id})
    return client.post("/api/capture").get_json()


def test_unripe_shows_advisory_and_does_not_start_a_pulse(client, force_class):
    snap = _assess_unripe(client, force_class)
    assert snap["status"] == "awaiting_confirmation"
    assert snap["pulse_enabled"] is False
    params = snap["parameters"]
    assert params["maturity_class"] == "unripe"
    assert params["advisory"] == "Advisory: Unripe olives \u2014 not recommended for harvesting"
    assert params["frequency_hz"] is None and params["duration_s"] is None
    assert snap["confirmation"]["required"] is True
    assert snap["confirmation"]["override_frequency_hz"] == 17

    # The normal Start button path must not start a pulse for unripe.
    resp = client.post("/api/harvest/start", json={})
    assert resp.status_code == 400
    assert client.get("/api/status").get_json()["status"] == "awaiting_confirmation"


def test_unripe_without_confirmation_ends_as_not_attempted(client, force_class, monkeypatch):
    from app.core.harvest_controller import HarvestController

    monkeypatch.setattr(HarvestController, "CONFIRM_TIMEOUT_S", 0.6)
    _assess_unripe(client, force_class)

    final = wait_for_status(client, "ready")
    assert final["status"] == "ready"
    assert final["pulse_enabled"] is False
    row = client.get("/api/history").get_json()[0]
    assert row["status"] == "not_attempted"
    assert row["maturity_class"] == "unripe"
    assert row["frequency_hz"] is None
    assert row["duration_actual_s"] is None
    assert row["duration_target_s"] is None
    assert row["harvested_mass_g"] is None
    assert row["operator_override"] == 0


def test_unripe_decline_ends_as_not_attempted(client, force_class):
    _assess_unripe(client, force_class)
    snap = client.post("/api/harvest/stop").get_json()
    assert snap["status"] == "ready"
    assert snap["last_session"]["status"] == "not_attempted"
    assert snap["last_session"]["frequency_hz"] is None


def test_unripe_override_starts_17_hz_pulse(client, force_class):
    _assess_unripe(client, force_class)
    snap = client.post("/api/harvest/confirm-override").get_json()
    assert snap["status"] == "harvesting"
    assert snap["pulse_enabled"] is True
    assert snap["parameters"]["frequency_hz"] == 17
    assert snap["parameters"]["operator_override"] is True

    stopped = client.post("/api/harvest/stop").get_json()
    row = client.get("/api/history").get_json()[0]
    assert stopped["last_session"]["status"] == "stopped"
    assert row["frequency_hz"] == 17
    assert row["operator_override"] == 1


def test_confirm_override_rejected_when_nothing_pending(client, force_class):
    force_class("semi_ripe")
    assert client.post("/api/harvest/confirm-override").status_code == 400
    branch_id = client.get("/api/branches").get_json()[0]["id"]
    client.post("/api/select-branch", json={"branch_id": branch_id})
    client.post("/api/capture")  # semi_ripe -> normal ASSESSED path
    assert client.post("/api/harvest/confirm-override").status_code == 400


def test_capture_and_branch_change_locked_while_awaiting_confirmation(client, force_class):
    _assess_unripe(client, force_class)
    assert client.post("/api/capture").status_code == 400
    other = client.get("/api/branches").get_json()[1]["id"]
    assert client.post("/api/select-branch", json={"branch_id": other}).status_code == 400
    client.post("/api/harvest/stop")  # cleanup (declines)


def test_only_the_paper_classes_are_produced(client):
    from app.hardware.camera import CLASS_COLORS

    assert set(CLASS_COLORS) == {"unripe", "semi_ripe", "ripe"}
