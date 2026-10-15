import io
import os
import uuid

import folium
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageOps
from streamlit_folium import st_folium

load_dotenv()

try:
    from core import db, detector, duplicates, geo, severity, summary  # noqa: E402
except Exception as e:
    import traceback
    st.error(f"Import failed: {e}")
    st.code(traceback.format_exc())
    st.stop()
st.set_page_config(page_title="RaastaWatch AI", page_icon="🛣️", layout="wide")
db.init_db()

DEFAULT_CENTER = (30.3753, 69.3451)  # Pakistan centre; change to your city
SEV_COLORS = {"Low": "green", "Medium": "orange", "High": "red"}
ADMIN_PIN = os.environ.get("ADMIN_PIN", "")


@st.cache_resource(show_spinner="Loading detection model...")
def get_model():
    return detector.load_model()


def severity_badge(label: str) -> str:
    return {"Low": "🟢", "Medium": "🟠", "High": "🔴"}[label] + f" {label}"


# ---------------------------------------------------------------- Report tab
def report_tab():
    st.subheader("Report road damage")
    up = st.file_uploader("Upload a road photo", type=["jpg", "jpeg", "png"])
    if not up:
        st.info("Upload a clear photo of the road surface to begin.")
        return

    raw = up.getvalue()
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    conf = st.slider("Detection confidence threshold", 0.10, 0.90, 0.25, 0.05)

    try:
        model = get_model()
    except detector.ModelMissing as e:
        st.error(str(e))
        return

    file_key = f"{up.name}-{len(raw)}-{conf}"
    if st.session_state.get("det_key") != file_key:
        dets, annotated = detector.detect(model, image, conf)
        st.session_state.update(det_key=file_key, dets=dets, annotated=annotated, summary_text="")
    dets, annotated = st.session_state["dets"], st.session_state["annotated"]

    c1, c2 = st.columns([3, 2])
    c1.image(annotated, caption=f"{len(dets)} detection(s)", use_container_width=True)

    sev = severity.compute(dets, image.width, image.height)
    with c2:
        st.metric("Severity", severity_badge(sev["label"]), f"score {sev['score']:.2f}")
        if sev["breakdown"]:
            st.caption("How the score is calculated")
            st.dataframe(pd.DataFrame(
                [{"Factor": n, "Weight": w, "Value": round(v, 2), "Contribution": round(w * v, 3)}
                 for n, w, v in sev["breakdown"]]), hide_index=True, use_container_width=True)
        else:
            st.warning("No damage detected. Try a lower threshold or a clearer photo.")

    if not dets:
        return

    # ---- location
    st.markdown("#### Location")
    exif = geo.exif_gps(raw)
    options = (["Photo GPS (EXIF)"] if exif else []) + ["My device location", "Pick on map"]
    source = st.radio("Location source", options, horizontal=True)
    lat = lon = None
    if source == "Photo GPS (EXIF)":
        lat, lon = exif
        st.success(f"Using GPS from photo: {lat:.5f}, {lon:.5f}")
    elif source == "My device location":
        from streamlit_geolocation import streamlit_geolocation
        st.caption("Your browser will ask for permission.")
        loc = streamlit_geolocation()
        if loc and loc.get("latitude"):
            lat, lon = loc["latitude"], loc["longitude"]
            st.success(f"Got location: {lat:.5f}, {lon:.5f}")
    if source == "Pick on map" or lat is None:
        st.caption("Click the map to drop a pin on the damaged spot.")
        center = st.session_state.get("pin", DEFAULT_CENTER)
        m = folium.Map(location=center, zoom_start=15 if "pin" in st.session_state else 6)
        if "pin" in st.session_state:
            folium.Marker(st.session_state["pin"]).add_to(m)
        out = st_folium(m, height=350, use_container_width=True, key="pin_map")
        if out and out.get("last_clicked"):
            new = (out["last_clicked"]["lat"], out["last_clicked"]["lng"])
            if st.session_state.get("pin") != new:
                st.session_state["pin"] = new
                st.rerun()
        if "pin" in st.session_state:
            lat, lon = st.session_state["pin"]
            source = "Map pin"
            st.success(f"Pin: {lat:.5f}, {lon:.5f}")

    if lat is None:
        st.info("Set a location to continue.")
        return

    # ---- duplicates
    phash = duplicates.compute_phash(image)
    grp, dist = duplicates.find_duplicate(lat, lon, phash)
    if grp:
        st.warning(f"Likely duplicate: matches issue #{grp['id']} ({dist:.0f} m away, "
                   f"{grp['report_count']} report(s)). Submitting will add to that issue.")
    else:
        st.success("No existing report nearby. This will create a new issue.")

    # ---- summary
    st.markdown("#### Summary for maintenance team")
    facts = dict(sev, lat=lat, lon=lon, location_source=source,
                 dup_count=grp["report_count"] if grp else 0)
    if st.button("Generate AI summary"):
        with st.spinner("Writing summary..."):
            st.session_state["summary_text"] = summary.generate(facts)
    text = st.text_area("Editable summary", key="summary_text", height=120)

    if st.button("Submit report", type="primary"):
        os.makedirs("data/uploads", exist_ok=True)
        path = f"data/uploads/{uuid.uuid4().hex}.jpg"
        annotated.save(path, quality=88)  # re-encoded, so original EXIF is not stored
        gid = db.add_report(dict(
            lat=lat, lon=lon, location_source=source, image_path=path, phash=phash,
            num_detections=sev["count"], max_conf=sev["max_conf"], area_ratio=sev["area_ratio"],
            severity_score=sev["score"], severity_label=sev["label"], summary=text), group_id=grp["id"] if grp else None)
        st.success(f"Report saved to issue #{gid}.")
        st.session_state.pop("det_key", None)


# ------------------------------------------------------------- Dashboard tab
def dashboard_tab():
    st.subheader("Live dashboard")
    allg = db.list_groups()
    if not allg:
        st.info("No reports yet. Submit one, or run `python scripts/seed_demo.py` for demo data.")
        return

    f1, f2 = st.columns(2)
    status_f = f1.selectbox("Status", ["All"] + db.STATUSES)
    sev_f = f2.selectbox("Severity", ["All", "High", "Medium", "Low"])
    groups = db.list_groups(None if status_f == "All" else status_f, None if sev_f == "All" else sev_f)

    k = st.columns(4)
    k[0].metric("Issues", len(allg))
    k[1].metric("Total reports", sum(g["report_count"] for g in allg))
    k[2].metric("High severity (open)", sum(1 for g in allg if g["severity_label"] == "High" and g["status"] != "Repaired"))
    k[3].metric("Repaired", sum(1 for g in allg if g["status"] == "Repaired"))

    if not groups:
        st.info("Nothing matches these filters.")
        return
    m = folium.Map(location=(groups[0]["lat"], groups[0]["lon"]), zoom_start=13)
    for g in groups:
        folium.CircleMarker(
            (g["lat"], g["lon"]), radius=6 + min(g["report_count"], 10),
            color=SEV_COLORS[g["severity_label"]], fill=True, fill_opacity=0.7,
            tooltip=f"#{g['id']} {g['severity_label']} | {g['status']} | {g['report_count']} report(s)").add_to(m)
    st_folium(m, height=420, use_container_width=True, key="dash_map", returned_objects=[])

    df = pd.DataFrame(groups)[["id", "severity_label", "max_score", "report_count", "status", "lat", "lon", "updated_at"]]
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.markdown("#### Issue details")
    gid = st.selectbox("Issue", [g["id"] for g in groups])
    g = next(x for x in groups if x["id"] == gid)
    for r in db.list_reports(gid):
        with st.expander(f"Report #{r['id']} | {severity_badge(r['severity_label'])} | {r['created_at']}"):
            if r["image_path"] and os.path.exists(r["image_path"]):
                st.image(r["image_path"], width=380)
            st.write(r["summary"] or "_No summary_")

    st.markdown("#### Update repair status (maintenance staff)")
    pin = st.text_input("Admin PIN", type="password")
    new = st.selectbox("New status", db.STATUSES, index=db.STATUSES.index(g["status"]))
    if st.button("Update status"):
        if ADMIN_PIN and pin == ADMIN_PIN:
            db.set_status(gid, new)
            st.success("Status updated.")
            st.rerun()
        else:
            st.error("Incorrect PIN.")


st.title("🛣️ RaastaWatch AI")
st.caption("Report road damage. Prioritise repairs.")
tab1, tab2 = st.tabs(["Report damage", "Dashboard"])
with tab1:
    report_tab()
with tab2:
    dashboard_tab()
