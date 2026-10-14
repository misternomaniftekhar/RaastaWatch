"""YOLO inference wrapper. Ultralytics is imported lazily so other modules work without it."""
import os
from PIL import Image, ImageDraw
from .severity import Detection

MODEL_PATH = os.environ.get("MODEL_PATH", "models/pothole.pt")


class ModelMissing(RuntimeError):
    pass


def load_model(path: str = MODEL_PATH):
    if not os.path.exists(path):
        raise ModelMissing(
            f"No model found at '{path}'. Put a pretrained pothole/road-damage YOLO .pt file there "
            "or set MODEL_PATH in .env.")
    from ultralytics import YOLO
    return YOLO(path)


def detect(model, image: Image.Image, conf: float = 0.25):
    """Return (detections, annotated_image)."""
    image = image.convert("RGB")
    res = model.predict(image, conf=conf, verbose=False)[0]
    names = res.names
    dets = []
    for b in res.boxes:
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
        dets.append(Detection(x1, y1, x2, y2, float(b.conf[0]), names.get(int(b.cls[0]), "damage")))
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    for d in dets:
        draw.rectangle([d.x1, d.y1, d.x2, d.y2], outline=(255, 60, 60), width=max(2, image.width // 250))
        draw.text((d.x1 + 3, max(0, d.y1 - 12)), f"{d.label} {d.conf:.0%}", fill=(255, 255, 0))
    return dets, annotated
