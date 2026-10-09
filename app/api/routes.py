"""REST API for the dashboard: branch selection, capture, harvest
start/stop, live status, alerts, and session history. All endpoints
return JSON; the frontend (app/static/js/dashboard.js) polls /status.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, send_from_directory

api_bp = Blueprint("api", __name__)


def _controller():
    return current_app.extensions["controller"]


@api_bp.get("/branches")
def get_branches():
    return jsonify(_controller().list_branches())


@api_bp.post("/select-branch")
def select_branch():
    data = request.get_json(silent=True) or {}
    branch_id = data.get("branch_id")
    if not branch_id:
        return jsonify({"error": "branch_id is required"}), 400
    try:
        snapshot = _controller().select_branch(branch_id)
    except (ValueError, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(snapshot)


@api_bp.post("/capture")
def capture():
    try:
        snapshot = _controller().capture_and_assess()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(snapshot)


@api_bp.post("/harvest/start")
def start_harvest():
    data = request.get_json(silent=True) or {}
    overrides = {k: data.get(k) for k in ("frequency_hz", "amplitude_mm", "duration_s")}
    try:
        snapshot = _controller().start_harvest(overrides)
    except (RuntimeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(snapshot)


@api_bp.post("/harvest/stop")
def stop_harvest():
    return jsonify(_controller().stop_harvest())


@api_bp.get("/status")
def status():
    return jsonify(_controller().snapshot())


@api_bp.get("/history")
def history():
    limit = request.args.get("limit", default=20, type=int)
    return jsonify(_controller().history(limit))


@api_bp.post("/alerts/<int:alert_id>/resolve")
def resolve_alert(alert_id: int):
    return jsonify(_controller().resolve_alert(alert_id))


@api_bp.get("/captures/<path:filename>")
def get_capture(filename: str):
    capture_dir = current_app.extensions["capture_dir"]
    return send_from_directory(capture_dir, filename)
