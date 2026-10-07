"""SQLite storage layer: persists completed harvest sessions and the
alert log, so the dashboard's "Harvesting session history" panel survives
a restart. Deliberately raw sqlite3 (no ORM) — simple, transparent, and
easy to inspect directly on a Raspberry Pi later.
"""
