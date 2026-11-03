import json
import re
import textwrap


def timestamp(seconds, comma=False):
    milliseconds = max(0, round(seconds * 1000))
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}{',' if comma else '.'}{millis:03}"


def safe_text(value):
    return re.sub(r"\s+", " ", value.replace("\x00", "")).strip()


def export(session, kind):
    segments = [s for s in session["segments"] if safe_text(s["text"])]
    if kind == "txt":
        return "\n\n".join(safe_text(s["text"]) for s in segments) + "\n", "text/plain; charset=utf-8"
    if kind == "json":
        result = {k: session[k] for k in ("id","title","model","language","duration","created_at","revision")}
        result["segments"] = []
        for s in segments:
            item = {k:s[k] for k in ("n","start","end","text","original_text","reviewed","uncertain")}
            item["word_timestamps"] = s["words"] if s["text"] == s["original_text"] else None
            item["timing_note"] = "Original word alignment; model probabilities are not calibrated accuracy." if item["word_timestamps"] else "Text was edited; only original segment times are retained."
            result["segments"].append(item)
        return json.dumps(result, ensure_ascii=False, indent=2) + "\n", "application/json"
    if kind not in ("srt","vtt"):
        raise ValueError("Choose TXT, SRT, VTT or JSON")
    cues = []
    for index, s in enumerate(segments, 1):
        text = safe_text(s["text"])
        if kind == "vtt":
            text = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        text = "\n".join(textwrap.wrap(text, width=48, break_long_words=False, break_on_hyphens=False))
        prefix = f"{index}\n" if kind == "srt" else ""
        cues.append(f"{prefix}{timestamp(s['start'],kind=='srt')} --> {timestamp(s['end'],kind=='srt')}\n{text}\n")
    return ("WEBVTT\n\n" if kind == "vtt" else "") + "\n".join(cues), "text/vtt; charset=utf-8" if kind == "vtt" else "application/x-subrip; charset=utf-8"
