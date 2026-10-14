# RaastaWatch AI

Upload a road photo -> YOLO detects damage -> location captured -> severity scored ->
duplicates grouped -> dashboard tracks repair status -> AI drafts a maintenance summary.

## Run
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # add GROQ_API_KEY, ADMIN_PIN
# put a pretrained pothole/road-damage YOLO weights file at models/pothole.pt
python scripts/seed_demo.py                           # optional demo data
streamlit run app.py
```

## Layout
- `app.py` - Streamlit UI (Report tab + Dashboard tab)
- `core/detector.py` - YOLO inference + box drawing
- `core/severity.py` - transparent score: 0.5 size + 0.3 confidence + 0.2 count; Low <0.33, Medium <0.66, High
- `core/geo.py` - EXIF GPS + haversine distance
- `core/duplicates.py` - same-spot grouping (radius + perceptual hash check)
- `core/summary.py` - Groq summary from structured facts only (template fallback with no key)
- `core/db.py` - SQLite: `groups` (one real issue, holds status) and `reports` (each upload)

## Known limitations (state these in your demo)
- Size score depends on camera distance/angle, so it is a relative indicator, not a measurement.
- Duplicate detection uses location radius (default 20 m); GPS error can merge or split issues.
- Model quality depends entirely on the weights you provide.
