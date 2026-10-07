# Olive Harvester — Control Dashboard (MVP)

A runnable web dashboard for a semi-automatic olive harvesting system
(Raspberry Pi 4 + Camera Module 3, to be connected later). Everything
hardware-related — camera, maturity detection input, sensors, and the
vibration actuator — is currently **simulated**, so the whole application
runs on a normal computer today.

## What's implemented

- Flask backend with a `HarvestController` state machine:
  `idle → ready → assessed → harvesting → ready`
- Simulated camera (`app/hardware/camera.py`) that generates a synthetic
  branch photo with a randomly chosen dominant olive maturity color
- A real (if simple) color-based maturity classifier
  (`app/core/maturity.py`) that analyzes the saved photo's pixels — it
  does **not** cheat by reading the simulator's hidden ground truth
- Vibration parameter selection from `config/vibration_profiles.yaml`
  (frequency/amplitude/duration per maturity class, operator-editable
  before starting)
- Simulated sensors (vibration feedback, motor current, mass accumulation)
  and a simulated actuator, ticking once per second in a background thread
- SQLite storage of every completed/stopped harvesting session and the
  alert log
- A single-page dashboard (`app/templates/index.html` +
  `app/static/`) with: tree/branch selection, camera/image area, maturity
  result, recommended vibration parameters (editable), start/stop
  controls, live sensor readings, harvested mass, system status, alerts,
  and session history

## Project structure

```
olive_harvester/
├── run.py                      # entry point
├── requirements.txt / requirements-dev.txt
├── pytest.ini
├── config/vibration_profiles.yaml
├── data/{captures,db}/         # created/used at runtime
├── app/
│   ├── __init__.py             # Flask app factory
│   ├── config.py                # paths + mock branch/tree map
│   ├── hardware/                # simulated camera, sensors, actuator
│   │   ├── camera.py
│   │   ├── sensors.py
│   │   └── actuator.py
│   ├── core/                    # hardware-independent logic
│   │   ├── maturity.py          # color-based maturity classifier
│   │   ├── parameters.py        # maturity -> vibration profile
│   │   └── harvest_controller.py# the state machine
│   ├── storage/                 # SQLite (schema.sql + db.py)
│   ├── api/routes.py            # REST API the dashboard calls
│   ├── templates/index.html
│   └── static/{css,js}/
└── tests/test_api.py            # automated integration tests
```

## Install

```bash
cd olive_harvester
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

## Run

```bash
python run.py
```

Then open **http://127.0.0.1:5000** in a browser. Workflow: select a
branch → Capture Image → review the maturity result and (optionally)
adjust the recommended parameters → Start Harvesting. Mass, vibration,
and current update live; the session ends automatically at the target
duration or when you click Stop, and appears in the history table.

## Test

```bash
pytest -v
```

This runs a full simulated capture → assess → harvest → history cycle
through the real Flask app (no browser needed), plus edge-case checks
(invalid branch, starting before assessment, changing branch mid-harvest).

## Swapping in real hardware later

Nothing outside `app/hardware/` knows the camera, sensors, or actuator
are simulated. To connect the real Raspberry Pi Camera Module 3 and
sensors, add real implementations in `app/hardware/` with the same
method shapes (`capture()`, `read(...)`, `start(...)/stop()/is_running`)
and swap them in `HarvestController.__init__` — `app/core/` and
`app/api/` do not change.
