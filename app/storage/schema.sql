-- Olive Harvester MVP schema (SQLite).

CREATE TABLE IF NOT EXISTS harvest_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id           TEXT NOT NULL,
    maturity_class      TEXT,
    confidence          REAL,
    frequency_hz        REAL,
    amplitude_mm        REAL,
    duration_target_s   REAL,
    duration_actual_s   REAL,
    harvested_mass_g    REAL,
    status              TEXT NOT NULL,        -- 'completed' | 'stopped'
    operator_override   INTEGER NOT NULL DEFAULT 0,
    image_url           TEXT,
    ended_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    severity     TEXT NOT NULL,
    code         TEXT NOT NULL,
    message      TEXT NOT NULL,
    raised_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_branch ON harvest_sessions(branch_id);
CREATE INDEX IF NOT EXISTS idx_sessions_ended   ON harvest_sessions(ended_at);
