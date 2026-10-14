"""Location helpers: haversine distance and EXIF GPS extraction."""
import io
import math
from PIL import Image


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _dms_to_deg(dms, ref) -> float:
    d, m, s = (float(x) for x in dms)
    deg = d + m / 60 + s / 3600
    return -deg if ref in ("S", "W") else deg


def exif_gps(image_bytes: bytes):
    """Return (lat, lon) from photo EXIF, or None if absent."""
    try:
        gps = Image.open(io.BytesIO(image_bytes)).getexif().get_ifd(0x8825)
        if gps and 2 in gps and 4 in gps:
            return (_dms_to_deg(gps[2], gps.get(1, "N")), _dms_to_deg(gps[4], gps.get(3, "E")))
    except Exception:
        pass
    return None
