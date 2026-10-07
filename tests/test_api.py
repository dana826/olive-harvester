from .conftest import wait_until_not_harvesting


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


def test_full_capture_and_harvest_cycle_auto_completes(client):
    branch_id = client.get("/api/branches").get_json()[0]["id"]

    resp = client.post("/api/select-branch", json={"branch_id": branch_id})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ready"

    resp = client.post("/api/capture")
    assert resp.status_code == 200
    snapshot = resp.get_json()
    assert snapshot["status"] == "assessed"
    params = snapshot["parameters"]
    assert params["maturity_class"] in {"unripe", "turning", "semi_ripe", "ripe", "unknown"}
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


def test_manual_stop_ends_session_early(client):
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


def test_cannot_change_branch_while_harvesting(client):
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
