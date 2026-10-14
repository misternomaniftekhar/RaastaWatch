"""Transparent severity score. All weights/caps are constants so they can be explained and tuned."""
from dataclasses import dataclass

W_AREA, W_CONF, W_COUNT = 0.5, 0.3, 0.2
AREA_CAP = 0.15   # box area >= 15% of the image counts as maximum size
COUNT_CAP = 5     # 5+ detections counts as maximum count
LOW_MAX, MED_MAX = 0.33, 0.66


@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    label: str = "pothole"

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


def label_for(score: float) -> str:
    return "Low" if score < LOW_MAX else "Medium" if score < MED_MAX else "High"


def compute(dets: list, img_w: int, img_h: int) -> dict:
    if not dets:
        return dict(score=0.0, label="Low", area_ratio=0.0, max_conf=0.0, count=0, breakdown=[])
    area_ratio = min(1.0, sum(d.area for d in dets) / float(img_w * img_h))
    max_conf = max(d.conf for d in dets)
    area_n = min(area_ratio / AREA_CAP, 1.0)
    count_n = min(len(dets) / COUNT_CAP, 1.0)
    score = round(W_AREA * area_n + W_CONF * max_conf + W_COUNT * count_n, 3)
    breakdown = [
        (f"Damage size ({area_ratio:.1%} of image)", W_AREA, area_n),
        (f"Top confidence ({max_conf:.0%})", W_CONF, max_conf),
        (f"Detections ({len(dets)})", W_COUNT, count_n),
    ]
    return dict(score=score, label=label_for(score), area_ratio=round(area_ratio, 4),
                max_conf=round(max_conf, 3), count=len(dets), breakdown=breakdown)
