"""AI summary for maintenance teams. Only structured facts go in, so the model can't invent details."""
import os

PROMPT = (
    "You write short notes for a road maintenance team. Using ONLY the facts below, write 3-4 plain "
    "sentences: what was found, where, how urgent it is and why. Do not invent details (no road names, "
    "depths or costs).\n\nFacts:\n{facts}"
)


def facts_text(r: dict) -> str:
    return (
        f"- Damage detections: {r['count']}\n"
        f"- Damage covers about {r['area_ratio']:.1%} of the photographed area\n"
        f"- Top detection confidence: {r['max_conf']:.0%}\n"
        f"- Severity: {r['label']} (risk score {r['score']:.2f} out of 1.00)\n"
        f"- Location: {r['lat']:.5f}, {r['lon']:.5f} (source: {r['location_source']})\n"
        f"- Duplicate reports of this spot so far: {r.get('dup_count', 0)}"
    )


def fallback(r: dict) -> str:
    return (
        f"{r['label']}-severity road damage reported at {r['lat']:.5f}, {r['lon']:.5f}. "
        f"{r['count']} detection(s) covering ~{r['area_ratio']:.1%} of the photo, top confidence "
        f"{r['max_conf']:.0%} (risk score {r['score']:.2f}). Inspection recommended."
    )


def generate(r: dict) -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return fallback(r)
    try:
        from groq import Groq
        resp = Groq(api_key=key).chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "user", "content": PROMPT.format(facts=facts_text(r))}],
            temperature=0.2, max_tokens=200)
        return resp.choices[0].message.content.strip()
    except Exception:
        return fallback(r)
