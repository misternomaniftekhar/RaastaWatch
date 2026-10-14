"""Duplicate grouping: same spot (haversine radius) + optional perceptual-hash sanity check."""
import os
import imagehash
from PIL import Image
from . import db
from .geo import haversine_m

RADIUS_M = float(os.environ.get("DUPLICATE_RADIUS_M", 20))
CLOSE_M = 8.0          # within this distance we trust location alone
PHASH_MAX_DIST = 28    # beyond this the pictures look unrelated (64-bit hash)


def compute_phash(image: Image.Image) -> str:
    return str(imagehash.phash(image.convert("RGB")))


def find_duplicate(lat: float, lon: float, phash=None):
    """Return (group_dict, distance_m) of the best matching open group, or (None, None)."""
    best, best_d = None, None
    for g in db.open_group_candidates():
        d = haversine_m(lat, lon, g["lat"], g["lon"])
        if d > RADIUS_M:
            continue
        if d > CLOSE_M and phash:
            hashes = db.group_phashes(g["id"])
            if hashes:
                h = imagehash.hex_to_hash(phash)
                if min(h - imagehash.hex_to_hash(x) for x in hashes) > PHASH_MAX_DIST:
                    continue
        if best_d is None or d < best_d:
            best, best_d = g, d
    return best, best_d
