"""Seed ~20 demo issues so the dashboard looks populated. Run from the project root:
    python scripts/seed_demo.py
Edit CENTER to your city."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import db, severity  # noqa: E402

CENTER = (34.0151, 71.5249)
random.seed(7)
db.init_db()
for _ in range(20):
    score = round(random.uniform(0.1, 0.95), 3)
    lat = CENTER[0] + random.uniform(-0.03, 0.03)
    lon = CENTER[1] + random.uniform(-0.03, 0.03)
    label = severity.label_for(score)
    gid = db.add_report(dict(
        lat=lat, lon=lon, location_source="Seed", num_detections=random.randint(1, 6),
        max_conf=round(random.uniform(0.4, 0.95), 2), area_ratio=round(random.uniform(0.01, 0.2), 3),
        severity_score=score, severity_label=label,
        summary=f"{label}-severity road damage reported (demo data)."))
    for _ in range(random.randint(0, 3)):  # duplicates of the same spot
        db.add_report(dict(
            lat=lat, lon=lon, location_source="Seed", num_detections=1, max_conf=0.6, area_ratio=0.05,
            severity_score=score * 0.9, severity_label=label, summary="Duplicate report (demo data)."), group_id=gid)
    if random.random() < 0.3:
        db.set_status(gid, random.choice(db.STATUSES[1:]))
print("Seeded demo data.")
