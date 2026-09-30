from flask import Flask, request, jsonify, send_file, render_template_string
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)
from urllib.parse import urlparse, parse_qs
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape
import io
import os
import re
import requests

app = Flask(__name__)

HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>YouTube Transcript Generator</title>
  <style>
    :root {
      --bg:#0f1115; --panel:#171a21; --soft:#222733; --text:#f3f5f7;
      --muted:#9da7b3; --line:#2c3440; --accent:#ff0033;
    }
    * { box-sizing:border-box; }
    body {
      margin:0; font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      background:var(--bg); color:var(--text);
    }
    .wrap { max-width:980px; margin:0 auto; padding:48px 20px 80px; }
    h1 { margin:0 0 8px; font-size:clamp(28px,4vw,46px); letter-spacing:-.04em; }
    .sub { color:var(--muted); margin:0 0 28px; }
    .panel {
      background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px;
    }
    .row { display:flex; gap:10px; flex-wrap:wrap; }
    input, select, button {
      border-radius:12px; border:1px solid var(--line); font:inherit;
    }
    input, select {
      background:#0d1015; color:var(--text); padding:13px 14px;
    }
    input { flex:1; min-width:260px; }
    select { min-width:150px; }
    button {
      padding:13px 18px; border:0; background:var(--accent); color:white;
      font-weight:700; cursor:pointer;
    }
    button.secondary { background:var(--soft); }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .meta { display:none; margin-top:18px; color:var(--muted); font-size:14px; }
    .error { color:#ff8c9f; margin-top:14px; white-space:pre-wrap; }
    .toolbar { display:none; gap:10px; margin:18px 0 12px; flex-wrap:wrap; }
    textarea {
      width:100%; min-height:560px; resize:vertical; border-radius:16px;
      border:1px solid var(--line); background:#0d1015; color:var(--text);
      padding:20px; font:16px/1.75 Georgia, "Times New Roman", serif;
    }
    .hint { color:var(--muted); font-size:13px; margin-top:10px; }
    .spinner {
      width:16px; height:16px; border:2px solid rgba(255,255,255,.35);
      border-top-color:white; border-radius:50%; display:inline-block;
      animation:spin .8s linear infinite; vertical-align:-3px; margin-right:8px;
    }
    @keyframes spin { to { transform:rotate(360deg); } }
  </style>
</head>
<body>
  <main class="wrap">
    <h1>YouTube Transcript Generator</h1>
    <p class="sub">Full available transcript. No summary. No rewriting. Paragraph text + PDF export.</p>

    <section class="panel">
      <div class="row">
        <input id="url" placeholder="Paste YouTube video URL" autocomplete="off" />
        <select id="lang">
          <option value="auto">Auto language</option>
          <option value="en">English</option>
          <option value="hi">Hindi</option>
          <option value="te">Telugu</option>
          <option value="ta">Tamil</option>
          <option value="es">Spanish</option>
        </select>
        <button id="generate" onclick="generateTranscript()">Generate</button>
      </div>
      <div id="error" class="error"></div>
      <div id="meta" class="meta"></div>
    </section>

    <div id="toolbar" class="toolbar">
      <button class="secondary" onclick="copyTranscript()">Copy text</button>
      <button class="secondary" onclick="downloadTxt()">Save .txt</button>
      <button onclick="downloadPdf()">Save as PDF</button>
    </div>

    <textarea id="output" spellcheck="false" placeholder="Transcript will appear here..."></textarea>
    <div class="hint">
      The app uses captions/subtitles exposed by YouTube. If a video has no accessible transcript, it will report that instead of inventing text.
    </div>
  </main>

<script>
let currentTitle = "YouTube Transcript";
let currentVideoId = "";

async function generateTranscript() {
  const url = document.getElementById("url").value.trim();
  const language = document.getElementById("lang").value;
  const btn = document.getElementById("generate");
  const error = document.getElementById("error");
  const output = document.getElementById("output");
  const meta = document.getElementById("meta");
  const toolbar = document.getElementById("toolbar");

  error.textContent = "";
  meta.style.display = "none";
  toolbar.style.display = "none";
  output.value = "";

  if (!url) {
    error.textContent = "Paste a YouTube URL first.";
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Generating';

  try {
    const res = await fetch("/api/transcript", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({url, language})
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not fetch transcript.");

    output.value = data.text;
    currentTitle = data.title || "YouTube Transcript";
    currentVideoId = data.video_id || "";
    meta.textContent = `${currentTitle} • ${data.language_name || "Transcript"} • ${data.word_count.toLocaleString()} words`;
    meta.style.display = "block";
    toolbar.style.display = "flex";
  } catch (e) {
    error.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate";
  }
}

async function copyTranscript() {
  const text = document.getElementById("output").value;
  if (!text) return;
  await navigator.clipboard.writeText(text);
}

function downloadTxt() {
  const text = document.getElementById("output").value;
  if (!text) return;
  const blob = new Blob([text], {type:"text/plain;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = safeName(currentTitle) + ".txt";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function downloadPdf() {
  const text = document.getElementById("output").value;
  if (!text) return;

  const res = await fetch("/api/pdf", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({text, title:currentTitle, video_id:currentVideoId})
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    alert(data.error || "Could not create PDF.");
    return;
  }

  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = safeName(currentTitle) + ".pdf";
  a.click();
  URL.revokeObjectURL(a.href);
}

function safeName(name) {
  return (name || "youtube-transcript")
    .replace(/[\\/:*?"<>|]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120) || "youtube-transcript";
}
</script>
</body>
</html>
"""

def get_video_id(value: str):
    value = (value or "").strip()

    # Accept raw video IDs too.
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    try:
        u = urlparse(value)
        host = (u.hostname or "").lower()

        if host in {"youtu.be", "www.youtu.be"}:
            candidate = u.path.strip("/").split("/")[0]
            return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None

        if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
            if u.path == "/watch":
                candidate = parse_qs(u.query).get("v", [None])[0]
                return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None

            parts = [p for p in u.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
                candidate = parts[1]
                return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None
    except Exception:
        pass

    return None

def get_title(video_id: str):
    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.ok:
            return r.json().get("title") or "YouTube Transcript"
    except Exception:
        pass
    return "YouTube Transcript"

def paragraphize(snippets, target_chars=700):
    """
    Preserve transcript wording. Only inserts paragraph breaks.
    """
    paragraphs = []
    current = []
    current_len = 0

    for item in snippets:
        text = (getattr(item, "text", "") or "").replace("\n", " ").strip()
        if not text:
            continue

        current.append(text)
        current_len += len(text) + 1

        # Break at a natural punctuation boundary after enough text,
        # or force a break if a paragraph gets too long.
        natural_end = bool(re.search(r'[.!?]["\')\]]?$', text))
        if (current_len >= target_chars and natural_end) or current_len >= 1100:
            paragraphs.append(" ".join(current).strip())
            current = []
            current_len = 0

    if current:
        paragraphs.append(" ".join(current).strip())

    return "\n\n".join(paragraphs)

def fetch_transcript(video_id: str, language: str):
    api = YouTubeTranscriptApi()

    if language and language != "auto":
        fetched = api.fetch(video_id, languages=[language])
        return fetched, getattr(fetched, "language", language), getattr(fetched, "language_code", language)

    transcript_list = api.list(video_id)

    # Prefer manually created English, then generated English, then any manual,
    # then any generated transcript. This avoids translation/rewording.
    candidates = list(transcript_list)
    selected = None

    for t in candidates:
        if getattr(t, "language_code", "").lower().startswith("en") and not getattr(t, "is_generated", False):
            selected = t
            break
    if selected is None:
        for t in candidates:
            if getattr(t, "language_code", "").lower().startswith("en"):
                selected = t
                break
    if selected is None:
        for t in candidates:
            if not getattr(t, "is_generated", False):
                selected = t
                break
    if selected is None and candidates:
        selected = candidates[0]

    if selected is None:
        raise NoTranscriptFound(video_id, [], None)

    fetched = selected.fetch()
    return fetched, getattr(selected, "language", "Transcript"), getattr(selected, "language_code", "")

def register_pdf_font():
    candidates = [
        # Windows
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\nirmala.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("TranscriptFont", path))
                return "TranscriptFont"
            except Exception:
                continue

    return "Helvetica"

@app.get("/")
def home():
    return render_template_string(HTML)

@app.post("/api/transcript")
def transcript():
    data = request.get_json(silent=True) or {}
    video_id = get_video_id(data.get("url", ""))
    language = (data.get("language") or "auto").strip().lower()

    if not video_id:
        return jsonify(error="Invalid YouTube URL or video ID."), 400

    try:
        fetched, language_name, language_code = fetch_transcript(video_id, language)
        text = paragraphize(fetched)

        if not text.strip():
            return jsonify(error="The transcript was empty."), 404

        return jsonify(
            text=text,
            title=get_title(video_id),
            video_id=video_id,
            language_name=language_name,
            language_code=language_code,
            word_count=len(text.split()),
        )

    except TranscriptsDisabled:
        return jsonify(error="Transcripts are disabled for this video."), 404
    except NoTranscriptFound:
        return jsonify(error="No accessible transcript was found for this video/language."), 404
    except VideoUnavailable:
        return jsonify(error="This YouTube video is unavailable."), 404
    except CouldNotRetrieveTranscript as e:
        return jsonify(error=f"YouTube did not return a transcript. {str(e)}"), 502
    except Exception as e:
        return jsonify(error=f"Could not fetch transcript: {str(e)}"), 500

@app.post("/api/pdf")
def make_pdf():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    title = (data.get("title") or "YouTube Transcript").strip()
    video_id = (data.get("video_id") or "").strip()

    if not text:
        return jsonify(error="Transcript text is empty."), 400

    buf = io.BytesIO()
    font = register_pdf_font()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="YouTube Transcript Generator",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TranscriptTitle",
        parent=styles["Title"],
        fontName=font,
        fontSize=17,
        leading=22,
        spaceAfter=8,
        alignment=TA_LEFT,
    )
    body_style = ParagraphStyle(
        "TranscriptBody",
        parent=styles["BodyText"],
        fontName=font,
        fontSize=10.5,
        leading=16,
        spaceAfter=10,
        alignment=TA_LEFT,
    )
    meta_style = ParagraphStyle(
        "TranscriptMeta",
        parent=styles["BodyText"],
        fontName=font,
        fontSize=8.5,
        leading=12,
        textColor="#666666",
        spaceAfter=14,
    )

    story = [Paragraph(escape(title), title_style)]
    if video_id:
        story.append(
            Paragraph(
                escape(f"https://www.youtube.com/watch?v={video_id}"),
                meta_style,
            )
        )

    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        if p:
            story.append(Paragraph(escape(p).replace("\n", "<br/>"), body_style))

    doc.build(story)
    buf.seek(0)

    filename = re.sub(r'[\\/:*?"<>|]+', "", title)[:100].strip() or "youtube-transcript"
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{filename}.pdf",
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
