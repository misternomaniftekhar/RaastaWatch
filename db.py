"""SQLite storage. A *group* = one real-world road issue; *reports* are individual uploads."""
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("RW_DB_PATH", "data/raastawatch.db")
STATUSES = ["Reported", "Verified", "In progress", "Repaired"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    report_count INTEGER NOT NULL DEFAULT 1,
    max_score REAL NOT NULL DEFAULT 0,
    severity_label TEXT NOT NULL DEFAULT 'Low',
    status TEXT NOT NULL DEFAULT 'Reported',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id),
    image_path TEXT,
    phash TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    location_source TEXT,
    num_detections INTEGER NOT NULL DEFAULT 0,
    max_conf REAL NOT NULL DEFAULT 0,
    area_ratio REAL NOT NULL DEFAULT 0,
    severity_score REAL NOT NULL DEFAULT 0,
    severity_label TEXT NOT NULL DEFAULT 'Low',
    summary TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_group ON reports(group_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as c:
        c.executescript(SCHEMA)


def list_groups(status=None, label=None):
    q, args = "SELECT * FROM groups WHERE 1=1", []
    if status:
        q += " AND status=?"; args.append(status)
    if label:
        q += " AND severity_label=?"; args.append(label)
    q += " ORDER BY max_score DESC"
    with get_conn() as c:
        return [dict(r) for r in c.execute(q, args)]


def list_reports(group_id=None):
    q, args = "SELECT * FROM reports", []
    if group_id is not None:
        q += " WHERE group_id=?"; args.append(group_id)
    q += " ORDER BY created_at DESC"
    with get_conn() as c:
        return [dict(r) for r in c.execute(q, args)]


def open_group_candidates():
    """Groups not yet repaired (a repaired spot that reappears is a new issue)."""
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM groups WHERE status != 'Repaired'")]


def group_phashes(group_id):
    with get_conn() as c:
        return [r["phash"] for r in c.execute(
            "SELECT phash FROM reports WHERE group_id=? AND phash IS NOT NULL", (group_id,))]


def add_report(rep: dict, group_id=None) -> int:
    """Insert a report; create a group if group_id is None, else update the existing group."""
    now = _now()
    with get_conn() as c:
        if group_id is None:
            cur = c.execute(
                "INSERT INTO groups (lat, lon, report_count, max_score, severity_label, status, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (rep["lat"], rep["lon"], 1, rep["severity_score"], rep["severity_label"], "Reported", now, now))
            group_id = cur.lastrowid
        else:
            g = c.execute("SELECT max_score, severity_label FROM groups WHERE id=?", (group_id,)).fetchone()
            best_score, best_label = g["max_score"], g["severity_label"]
            if rep["severity_score"] > best_score:
                best_score, best_label = rep["severity_score"], rep["severity_label"]
            c.execute("UPDATE groups SET report_count=report_count+1, max_score=?, severity_label=?, updated_at=? WHERE id=?",
                      (best_score, best_label, now, group_id))
        c.execute(
            "INSERT INTO reports (group_id, image_path, phash, lat, lon, location_source, num_detections, max_conf,"
            " area_ratio, severity_score, severity_label, summary, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (group_id, rep.get("image_path"), rep.get("phash"), rep["lat"], rep["lon"], rep.get("location_source"),
             rep.get("num_detections", 0), rep.get("max_conf", 0), rep.get("area_ratio", 0),
             rep["severity_score"], rep["severity_label"], rep.get("summary"), now))
        return group_id


def set_status(group_id: int, status: str) -> None:
    assert status in STATUSES
    with get_conn() as c:
        c.execute("UPDATE groups SET status=?, updated_at=? WHERE id=?", (status, _now(), group_id))


def update_summary(report_id: int, summary: str) -> None:
    with get_conn() as c:
        c.execute("UPDATE reports SET summary=? WHERE id=?", (summary, report_id))
