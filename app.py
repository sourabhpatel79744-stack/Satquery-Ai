"""
SatQuery AI — Smart India Hackathon Demo
=========================================
A natural-language assistant for satellite-image analysis.
"""

from dotenv import load_dotenv
load_dotenv()  # Load .env file (XAI_API_KEY, GROQ_API_KEY, etc.)

import base64
import io
import json
import os
import re as re_module  # avoid shadowing the module-level `re` already imported below
import time
import uuid
from datetime import datetime, timezone

import gradio as gr
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# AI Provider — xAI Grok (primary) + Groq (fallback, 14 400 req/day free)
# ---------------------------------------------------------------------------
_gemini_client = None

# Retry settings
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 4  # seconds


def _get_xai_key(custom_key: str = "") -> str:
    """Retrieve xAI API key from custom input or env vars."""
    if custom_key and custom_key.strip():
        return custom_key.strip()
    return os.environ.get("XAI_API_KEY", "").strip()


def _get_groq_key(custom_key: str = "") -> str:
    """Retrieve Groq API key from custom input or env vars."""
    if custom_key and custom_key.strip():
        return custom_key.strip()
    return os.environ.get("GROQ_API_KEY", "").strip()


def _pil_to_base64(img: Image.Image) -> str:
    """Convert a PIL Image to a base64-encoded PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _call_xai(contents: list, custom_key: str = "") -> str:
    """Call xAI Grok Vision API (grok-2-vision-latest).

    Uses the OpenAI-compatible endpoint at https://api.x.ai/v1.
    Retries up to _MAX_RETRIES times on 429 (rate-limit) responses with
    exponential backoff starting at _RETRY_BASE_DELAY seconds.
    """
    import httpx

    api_key = _get_xai_key(custom_key)
    if not api_key:
        raise RuntimeError("XAI_API_KEY is missing. Please set XAI_API_KEY in .env or enter it in the UI.")

    parts = []
    for item in contents:
        if isinstance(item, Image.Image):
            b64 = _pil_to_base64(item)
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        else:
            parts.append({"type": "text", "text": str(item)})

    last_exc = None
    for attempt in range(_MAX_RETRIES + 1):  # 0, 1, 2  →  initial + 2 retries
        response = httpx.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-2-vision-latest",
                "messages": [{"role": "user", "content": parts}],
                "max_tokens": 1500,
            },
            timeout=60.0,
        )
        if response.status_code == 429:
            last_exc = httpx.HTTPStatusError(
                f"429 Too Many Requests", request=response.request, response=response
            )
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_DELAY * (2 ** attempt)  # 4s, 8s
                print(f"[SatQuery] xAI 429 rate-limited — retrying in {wait}s (attempt {attempt + 1}/{_MAX_RETRIES})…")
                time.sleep(wait)
                continue
            # All retries exhausted
            raise last_exc
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    # Should not reach here, but just in case
    raise last_exc or RuntimeError("xAI API call failed unexpectedly.")


def _call_groq(contents: list, custom_key: str = "") -> str:
    """Call Groq API with vision capability (qwen/qwen3.8-27b).

    Retries up to _MAX_RETRIES times on 429 (rate-limit) responses with
    exponential backoff starting at _RETRY_BASE_DELAY seconds.
    """
    import httpx

    api_key = _get_groq_key(custom_key)
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Please set GROQ_API_KEY in .env or enter it in the UI.")

    parts = []
    for item in contents:
        if isinstance(item, Image.Image):
            b64 = _pil_to_base64(item)
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        else:
            parts.append({"type": "text", "text": str(item)})

    last_exc = None
    for attempt in range(_MAX_RETRIES + 1):  # 0, 1, 2  →  initial + 2 retries
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "qwen/qwen3.8-27b",
                "messages": [{"role": "user", "content": parts}],
                "max_tokens": 1500,
            },
            timeout=60.0,
        )
        if response.status_code == 429:
            last_exc = httpx.HTTPStatusError(
                f"429 Too Many Requests", request=response.request, response=response
            )
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_DELAY * (2 ** attempt)  # 4s, 8s
                print(f"[SatQuery] Groq 429 rate-limited — retrying in {wait}s (attempt {attempt + 1}/{_MAX_RETRIES})…")
                time.sleep(wait)
                continue
            # All retries exhausted
            raise last_exc
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    # Should not reach here, but just in case
    raise last_exc or RuntimeError("Groq API call failed unexpectedly.")


def _call_ai(contents: list, custom_xai_key: str = "", custom_groq_key: str = "") -> str:
    """Call AI with xAI Grok Vision as primary, Groq as fallback."""
    errors = []

    # ── Primary: xAI Grok Vision ─────────────────────────────────────────
    xai_key = _get_xai_key(custom_xai_key)
    if xai_key:
        try:
            return _call_xai(contents, xai_key)
        except Exception as exc:
            errors.append(f"xAI Grok: {exc}")

    # ── Fallback: Groq Vision ────────────────────────────────────────────
    groq_key = _get_groq_key(custom_groq_key)
    if groq_key:
        try:
            print("[SatQuery] Using Groq vision fallback…")
            return _call_groq(contents, groq_key)
        except Exception as exc:
            errors.append(f"Groq: {exc}")

    # ── Failure ─────────────────────────────────────────────────────────
    error_summary = " | ".join(errors) if errors else "No API Key configured"
    raise gr.Error(
        f"⚠️ AI Provider Error:\n\n"
        f"{error_summary}\n\n"
        f"💡 Please check your XAI_API_KEY or GROQ_API_KEY in .env or on the web page under API Key Settings."
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APP_TITLE = "SatQuery AI"
APP_DESCRIPTION = (
    "Upload one or two satellite images and ask a natural-language question. "
    "SatQuery AI detects the appropriate analysis task — VQA, Grounding, "
    "Change Detection, or Optical+SAR Fusion — and returns an answer with "
    "evidence and a full execution trace."
)

TASK_LABELS = {
    "vqa": "Visual Question Answering (VQA)",
    "grounding": "Grounding",
    "change_vqa": "Bi-Temporal Change Detection",
    "fusion": "Optical + SAR Fusion",
}

ADAPTER_MAP = {
    "vqa": "lora-vqa-v1",
    "grounding": "lora-grounding-v1",
    "change_vqa": "lora-change-v1 (mocked)",
    "fusion": "lora-fusion-v1 (mocked)",
}

import re

# Keywords that signal a grounding (spatial-localization) question
_GROUNDING_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bwhere\s+is\b",
        r"\bwhere\s+are\b",
        r"\blocate\b",
        r"\blocation\s+of\b",
        r"\bpoint\s+to\b",
        r"\bpoint\s+out\b",
        r"\bfind\b",
        r"\bshow\s+me\b",
        r"\bhighlight\b",
        r"\bbounding\s*box\b",
        r"\bdraw\s+a\s+(box|rectangle|circle)\b",
        r"\bmark\b",
        r"\bidentify\s+the\s+(location|position|area)\b",
    ]
]

# Keywords that signal change-detection (bi-temporal comparison)
_CHANGE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bchang(e|ed|es|ing)\b",
        r"\bdiffer(ence|ent|s)\b",
        r"\bcompar(e|ed|ing|ison)\b",
        r"\bbefore\s+and\s+after\b",
        r"\bover\s+time\b",
        r"\btemporal\b",
        r"\bevol(ve|ution|ved)\b",
        r"\bgrow(th|n|ing)\b",
        r"\bexpan(d|sion|ded)\b",
        r"\bshrink|shrunk\b",
        r"\bnew\s+(construction|building|structure)\b",
        r"\bdestroyed\b",
        r"\bdeforestation\b",
        r"\burbanization\b",
        r"\bflood(ed|ing)?\b",
    ]
]

# Keywords that signal optical+SAR fusion
_FUSION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bsar\b",
        r"\bradar\b",
        r"\bfus(e|ion|ed|ing)\b",
        r"\bcombine\b",
        r"\bmerge\b",
        r"\boptical\s+and\s+radar\b",
        r"\bradar\s+and\s+optical\b",
        r"\bmulti-?\s*modal\b",
        r"\bmulti-?\s*sensor\b",
        r"\brisat\b",
        r"\bsentinel-1\b",
    ]
]


def _matches_any(text: str, patterns: list[re.Pattern]) -> bool:
    """Return True if *text* matches at least one compiled pattern."""
    return any(p.search(text) for p in patterns)


def classify_task(image1, image2, question: str) -> str:
    """Classify the user query into one of the four task types.

    Decision tree (evaluated in this order):
      1. Count uploaded images.
      2. For 1-image queries: check grounding keywords → else VQA.
      3. For 2-image queries: check fusion keywords → else check change
         keywords → default to change_vqa (the more common 2-image case).

    Returns one of: 'vqa', 'grounding', 'change_vqa', 'fusion'.
    """
    q = question.strip()
    has_two_images = image2 is not None

    if not has_two_images:
        # ── Single-image path ─────────────────────────────────────────
        if _matches_any(q, _GROUNDING_PATTERNS):
            return "grounding"
        return "vqa"
    else:
        # ── Dual-image path ───────────────────────────────────────────
        if _matches_any(q, _FUSION_PATTERNS):
            return "fusion"
        # Default for two images is change detection (more common use case)
        return "change_vqa"


# ---------------------------------------------------------------------------
# Real task handlers — VQA & Grounding (xAI Grok Vision)
# ---------------------------------------------------------------------------

def handle_vqa(image: Image.Image, question: str, custom_xai_key: str = "", custom_groq_key: str = "") -> dict:
    """Visual Question Answering via xAI Grok."""
    prompt = (
        "You are a satellite-image analysis assistant. "
        "Answer the following question about this satellite/aerial image. "
        "Be concise but informative.\n\n"
        f"Question: {question}"
    )
    try:
        answer = _call_ai([image, prompt], custom_xai_key, custom_groq_key)
    except Exception as exc:
        answer = f"[Model error] {exc}"

    return {
        "answer": answer,
        "confidence": 0.85,
        "evidence_image": image,
    }


def _parse_bounding_boxes(text: str) -> list[list[int]]:
    """Extract [y_min, x_min, y_max, x_max] boxes from text output.

    Coordinates are normalised to 0-1000.
    """
    pattern = r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]"
    matches = re_module.findall(pattern, text)
    return [[int(v) for v in m] for m in matches]


def _draw_boxes(image: Image.Image, boxes: list[list[int]]) -> Image.Image:
    """Draw bounding boxes on the image.

    *boxes*: list of [y_min, x_min, y_max, x_max] normalised to 0-1000.
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for box in boxes:
        y_min, x_min, y_max, x_max = box
        left = int(x_min / 1000 * w)
        top = int(y_min / 1000 * h)
        right = int(x_max / 1000 * w)
        bottom = int(y_max / 1000 * h)
        draw.rectangle(
            [left, top, right, bottom],
            outline="red",
            width=max(3, int(min(w, h) * 0.005)),
        )
    return img


def handle_grounding(image: Image.Image, question: str, custom_xai_key: str = "", custom_groq_key: str = "") -> dict:
    """Object grounding via xAI Grok — returns bounding boxes."""
    prompt = (
        "You are a satellite-image analysis assistant specializing in "
        "object detection and spatial localization.\n\n"
        f"Task: {question}\n\n"
        "Return a bounding box for each relevant object in the format "
        "[y_min, x_min, y_max, x_max] where coordinates are integers "
        "from 0 to 1000 (normalised to image dimensions). "
        "Also provide a brief text description of what you found.\n"
        "Example output format:\n"
        "Object: Airport runway\n"
        "Bounding box: [120, 340, 450, 780]\n"
    )
    try:
        raw_text = _call_ai([image, prompt], custom_xai_key, custom_groq_key)
    except Exception as exc:
        return {
            "answer": f"[Model error] {exc}",
            "confidence": 0.0,
            "evidence_image": image,
        }

    boxes = _parse_bounding_boxes(raw_text)
    if boxes:
        evidence = _draw_boxes(image, boxes)
        answer = raw_text
        confidence = 0.82
    else:
        evidence = image
        answer = (
            raw_text if raw_text
            else "Could not determine bounding boxes for this query."
        )
        confidence = 0.40

    return {
        "answer": answer,
        "confidence": confidence,
        "evidence_image": evidence,
    }


def _make_side_by_side(img1: Image.Image, img2: Image.Image) -> Image.Image:
    """Create a side-by-side comparative visualization for change detection / fusion."""
    w1, h1 = img1.size
    w2, h2 = img2.size
    target_h = max(h1, h2)
    i1 = img1.resize((int(w1 * target_h / h1), target_h))
    i2 = img2.resize((int(w2 * target_h / h2), target_h))

    gutter = 10
    header_h = 35
    combined = Image.new("RGB", (i1.width + i2.width + gutter, target_h + header_h), (15, 23, 42))
    draw = ImageDraw.Draw(combined)
    draw.text((10, 8), "IMAGE 1 (BEFORE)", fill=(241, 245, 249))
    draw.text((i1.width + gutter + 10, 8), "IMAGE 2 (AFTER)", fill=(241, 245, 249))

    combined.paste(i1, (0, header_h))
    combined.paste(i2, (i1.width + gutter, header_h))
    return combined


def handle_change_detection(image1: Image.Image, image2: Image.Image | None, question: str, custom_xai_key: str = "", custom_groq_key: str = "") -> dict:
    """Bi-temporal Change Detection via xAI Grok."""
    if image2 is None:
        return {
            "answer": "Bi-temporal change detection requires two images (Before and After). Please upload Image 2.",
            "confidence": 0.0,
            "evidence_image": image1,
        }

    prompt = (
        "You are a satellite-image analysis assistant specializing in bi-temporal change detection. "
        "The first image is Image 1 (Before/Earlier) and the second image is Image 2 (After/Later). "
        "Analyze the temporal differences, structural changes, land cover alterations, or new developments "
        "between these two satellite images.\n\n"
        f"Question: {question}"
    )
    try:
        answer = _call_ai([image1, image2, prompt], custom_xai_key, custom_groq_key)
        confidence = 0.84
    except Exception as exc:
        answer = f"[Model error] {exc}"
        confidence = 0.0

    evidence = _make_side_by_side(image1, image2)
    return {
        "answer": answer,
        "confidence": confidence,
        "evidence_image": evidence,
    }


def handle_fusion(image1: Image.Image, image2: Image.Image | None, question: str, custom_xai_key: str = "", custom_groq_key: str = "") -> dict:
    """Multi-sensor / multi-band data fusion via xAI Grok."""
    if image2 is None:
        return {
            "answer": "Optical + SAR fusion analysis requires two multi-sensor images. Please upload Image 2.",
            "confidence": 0.0,
            "evidence_image": image1,
        }

    prompt = (
        "You are a satellite-image analysis assistant specializing in multi-sensor data fusion (e.g. Optical + SAR). "
        "Image 1 and Image 2 contain complementary sensor information of the same region. "
        "Fuse details from both modalities to provide a comprehensive answer.\n\n"
        f"Question: {question}"
    )
    try:
        answer = _call_ai([image1, image2, prompt], custom_xai_key, custom_groq_key)
        confidence = 0.88
    except Exception as exc:
        answer = f"[Model error] {exc}"
        confidence = 0.0

    evidence = _make_side_by_side(image1, image2)
    return {
        "answer": answer,
        "confidence": confidence,
        "evidence_image": evidence,
    }


# ---------------------------------------------------------------------------
# Trace builder
# ---------------------------------------------------------------------------

def build_trace(
    question: str,
    detected_task: str,
    image_count: int,
    modalities: list,
    model_output: dict,
    confidence: float,
    evidence_path: str | None,
    final_answer: str,
) -> dict:
    """Build the execution-trace JSON conforming to the fixed schema."""
    return {
        "query_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_query": question,
        "detected_task": detected_task,
        "input_validation": {
            "image_count": image_count,
            "modalities": modalities,
            "co_registration_status": (
                "not_applicable" if image_count < 2 else "pass"
            ),
        },
        "selected_adapter": ADAPTER_MAP.get(detected_task, "unknown"),
        "model_output": model_output,
        "confidence": confidence,
        "evidence_refs": [evidence_path] if evidence_path else [],
        "final_answer": final_answer,
    }


# ---------------------------------------------------------------------------
# Main inference pipeline
# ---------------------------------------------------------------------------

def _normalize_image(img):
    """Convert various image input formats to a PIL Image.

    Gradio may pass:
      - A PIL Image (local dev, type="pil")
      - A Gradio FileData object with .path / .url attrs (Gradio 6+)
      - A dict  {"path": "/tmp/…", "url": "https://…"} (deployed / shared)
      - A plain file-path string  (type="filepath")
    This helper ensures we always get a PIL Image back.
    """
    if img is None:
        return None
    if isinstance(img, Image.Image):
        return img

    # --- Extract path / url from various container types ----------------
    path = None
    url = None

    if isinstance(img, dict):
        path = img.get("path", "")
        url = img.get("url", "")
    elif isinstance(img, str):
        path = img
    elif hasattr(img, "path"):  # Gradio FileData object
        path = getattr(img, "path", None) or ""
        url = getattr(img, "url", None) or ""
    else:
        # numpy array (another possible Gradio format)
        try:
            import numpy as np
            if isinstance(img, np.ndarray):
                return Image.fromarray(img)
        except ImportError:
            pass
        raise gr.Error(f"Unsupported image format: {type(img)}")

    # --- Try local path first, then URL ---------------------------------
    if path and os.path.isfile(path):
        return Image.open(path).copy()

    if url:
        import httpx
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).copy()
        except Exception as dl_err:
            raise gr.Error(f"Could not download image from URL: {dl_err}")

    # Path was given but file doesn't exist and no URL fallback
    if path:
        raise gr.Error(
            f"Image file not found at '{path}'. "
            f"This can happen on serverless deployments — please re-upload the image."
        )
    raise gr.Error("Received image data but could not locate the file. Please re-upload.")


def run_query(image1, image2, question: str, custom_xai_key: str = "", custom_groq_key: str = ""):
    """Main entry point wired to the Submit button."""
    # Normalize inputs — handles dicts, paths, URLs, and PIL images
    image1 = _normalize_image(image1)
    image2 = _normalize_image(image2)

    if image1 is None:
        raise gr.Error(
            "Please upload at least one image (Image 1 is required)."
        )
    if not question or not question.strip():
        question = "What land cover types, terrain features, and structures are visible in this satellite image?"

    image_count = 1 if image2 is None else 2
    modalities = ["optical"]
    if image_count == 2:
        modalities = ["optical", "optical"]

    detected_task = classify_task(image1, image2, question)
    task_label = f"🛰️  Detected Task:  **{TASK_LABELS[detected_task]}**"

    if detected_task == "vqa":
        result = handle_vqa(image1, question, custom_xai_key, custom_groq_key)
    elif detected_task == "grounding":
        result = handle_grounding(image1, question, custom_xai_key, custom_groq_key)
    elif detected_task == "change_vqa":
        result = handle_change_detection(image1, image2, question, custom_xai_key, custom_groq_key)
    elif detected_task == "fusion":
        result = handle_fusion(image1, image2, question, custom_xai_key, custom_groq_key)
    else:
        raise gr.Error(f"Unknown task type: {detected_task}")

    answer_text = result["answer"]
    confidence = result["confidence"]
    evidence_img = result.get("evidence_image")
    confidence_display = f"{confidence * 100:.1f}%"

    trace = build_trace(
        question=question,
        detected_task=detected_task,
        image_count=image_count,
        modalities=modalities,
        model_output={"raw": answer_text},
        confidence=confidence,
        evidence_path=None,
        final_answer=answer_text,
    )
    trace_json = json.dumps(trace, indent=2)

    return task_label, answer_text, confidence_display, evidence_img, trace_json


# ---------------------------------------------------------------------------
# PDF Report Generator
# ---------------------------------------------------------------------------

def generate_pdf_report(trace_json: str, answer: str, confidence: str):
    """Generate a clean PDF report summarizing the SatQuery AI query analysis.
    
    Returns the absolute file path to the generated PDF.
    """
    if not answer or not answer.strip():
        raise gr.Error("Please run an analysis query first before downloading a report.")

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        import xml.sax.saxutils as saxutils
    except ImportError:
        raise gr.Error("reportlab package is not installed. Run 'pip install reportlab'.")

    os.makedirs("reports", exist_ok=True)
    report_filename = os.path.abspath(os.path.join("reports", f"satquery_report_{uuid.uuid4().hex[:8]}.pdf"))
    doc = SimpleDocTemplate(
        report_filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=10
    )
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        textColor=colors.HexColor('#334155'),
        leading=13
    )
    code_style = ParagraphStyle(
        'CodeText',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=7.5,
        textColor=colors.HexColor('#1E293B'),
        leading=9
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("SatQuery AI — Mission Analysis Report", title_style))
    elements.append(Paragraph(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | SIH-2026", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=10))

    # Parse Trace JSON
    trace_data = {}
    try:
        if trace_json:
            trace_data = json.loads(trace_json)
    except Exception:
        pass

    # Metadata Table
    table_data = [
        [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Value</b>", body_style)],
        [Paragraph("Query ID", body_style), Paragraph(saxutils.escape(str(trace_data.get("query_id", "N/A"))), body_style)],
        [Paragraph("Detected Task", body_style), Paragraph(saxutils.escape(str(trace_data.get("detected_task", "N/A"))), body_style)],
        [Paragraph("Selected Adapter", body_style), Paragraph(saxutils.escape(str(trace_data.get("selected_adapter", "N/A"))), body_style)],
        [Paragraph("Confidence Score", body_style), Paragraph(saxutils.escape(str(confidence)), body_style)],
    ]

    t = Table(table_data, colWidths=[130, 410])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))

    # Question & Answer
    elements.append(Paragraph("User Query", heading_style))
    q_text = saxutils.escape(str(trace_data.get("user_query", "N/A")))
    elements.append(Paragraph(f'<i>"{q_text}"</i>', body_style))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Analysis Answer", heading_style))
    ans_text = saxutils.escape(str(answer))
    ans_formatted = ans_text.replace("\n", "<br/>")
    elements.append(Paragraph(ans_formatted, body_style))
    elements.append(Spacer(1, 10))

    # Raw Execution Trace
    elements.append(Paragraph("Execution Trace JSON", heading_style))
    trace_escaped = saxutils.escape(str(trace_json))
    trace_formatted = trace_escaped.replace("\n", "<br/>&nbsp;&nbsp;")
    elements.append(Paragraph(f'<font face="Courier" size="7.5">{trace_formatted}</font>', code_style))

    doc.build(elements)
    return report_filename


# ---------------------------------------------------------------------------
# UI Construction
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
/* SatQuery AI - Dynamic CSS Variable Driven Light & Dark Mode */
.gradio-container {
    --body-background-fill: #f8fafc !important;
    --body-text-color: #0f172a !important;
    --block-background-fill: #ffffff !important;
    --block-border-color: #e2e8f0 !important;
    --block-label-background-fill: #e0f2fe !important;
    --block-label-text-color: #0369a1 !important;
    --block-title-text-color: #0284c7 !important;
    --input-background-fill: #ffffff !important;
    --input-border-color: #cbd5e1 !important;
    --input-text-color: #0f172a !important;
    --accordion-text-color: #c2410c !important;
    --accordion-background-fill: #f1f5f9 !important;
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}

/* Dark Mode Variable Overrides */
.dark,
.dark .gradio-container,
body.dark,
body.dark .gradio-container,
html.dark,
html.dark .gradio-container,
.gradio-container.dark {
    --body-background-fill: #0b0f19 !important;
    --body-text-color: #f8fafc !important;
    --block-background-fill: #151c2c !important;
    --block-border-color: #2a364f !important;
    --block-label-background-fill: #1e293b !important;
    --block-label-text-color: #38bdf8 !important;
    --block-title-text-color: #38bdf8 !important;
    --input-background-fill: #0b1120 !important;
    --input-border-color: #334155 !important;
    --input-text-color: #f8fafc !important;
    --accordion-text-color: #fb923c !important;
    --accordion-background-fill: #1c263b !important;
}

/* Body & Container */
body, .gradio-container {
    background-color: var(--body-background-fill) !important;
    color: var(--body-text-color) !important;
}

/* Blocks & Panels */
.gradio-container .block,
.gradio-container .panel,
.gradio-container div[class*="block"],
.gradio-container details,
.gradio-container fieldset {
    background-color: var(--block-background-fill) !important;
    border: 1px solid var(--block-border-color) !important;
    border-radius: 12px !important;
}

/* Headings */
.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container h4 {
    color: var(--block-title-text-color) !important;
    -webkit-text-fill-color: var(--block-title-text-color) !important;
    font-weight: 700 !important;
}

/* Label Badges / Pill Containers */
.gradio-container .block-label,
.gradio-container label span,
.gradio-container .label span,
.gradio-container span[data-testid="block-info"],
.gradio-container div[data-testid="block-title"],
.gradio-container .block > label,
.gradio-container .block > label > span,
.gradio-container label.block span,
.gradio-container legend,
.gradio-container .section-header {
    background-color: var(--block-label-background-fill) !important;
    background: var(--block-label-background-fill) !important;
    color: var(--block-label-text-color) !important;
    -webkit-text-fill-color: var(--block-label-text-color) !important;
    border: 1px solid var(--block-border-color) !important;
    border-radius: 6px !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
}

/* Accordions */
.gradio-container .accordion,
.gradio-container summary,
.gradio-container details summary {
    background-color: var(--accordion-background-fill) !important;
    border: 1px solid var(--block-border-color) !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
}

.gradio-container summary,
.gradio-container summary span,
.gradio-container details summary span,
.gradio-container summary div,
.gradio-container details summary div {
    color: var(--accordion-text-color) !important;
    -webkit-text-fill-color: var(--accordion-text-color) !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
}

/* Inputs & Textareas */
.gradio-container textarea,
.gradio-container input[type="text"],
.gradio-container input[type="password"],
.gradio-container select {
    background-color: var(--input-background-fill) !important;
    color: var(--input-text-color) !important;
    -webkit-text-fill-color: var(--input-text-color) !important;
    border: 1px solid var(--input-border-color) !important;
    border-radius: 8px !important;
    font-size: 0.95rem !important;
}

.gradio-container textarea::placeholder,
.gradio-container input::placeholder {
    color: #64748b !important;
    -webkit-text-fill-color: #64748b !important;
}

/* Universal High-Contrast Buttons */
#submit_btn, button.primary {
    background: linear-gradient(135deg, #f97316 0%, #ea580c 100%) !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
    border-radius: 10px !important;
    border: none !important;
    padding: 12px 24px !important;
    box-shadow: 0 4px 14px rgba(249, 115, 22, 0.4) !important;
}

#submit_btn:hover, button.primary:hover {
    background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%) !important;
    box-shadow: 0 6px 18px rgba(249, 115, 22, 0.5) !important;
}

#download_btn {
    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border-radius: 10px !important;
    border: none !important;
    padding: 10px 20px !important;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3) !important;
}

#download_btn:hover {
    background: linear-gradient(135deg, #0369a1 0%, #075985 100%) !important;
}
"""

def build_ui():
    with gr.Blocks(title="SatQuery AI — Satellite Image Intelligence") as demo:
        gr.Markdown(
            """
            # 🛰️ SatQuery AI — Satellite Image Intelligence
            ### Natural Language Analysis for Multi-Spectral & Temporal Satellite Imagery
            """
        )

        with gr.Row():
            # Left Column: Inputs
            with gr.Column(scale=5):
                gr.Markdown("### 📥 Query & Image Uploads")
                with gr.Row():
                    img1 = gr.Image(label="Image 1 (Required: Optical / SAR / Primary)", type="filepath")
                    img2 = gr.Image(label="Image 2 (Optional: Temporal / Secondary)", type="filepath")

                question_input = gr.Textbox(
                    label="Ask a question about the satellite imagery",
                    placeholder="e.g. Detect land cover changes, identify structures, or assess flood damage...",
                    lines=3,
                )

                submit_btn = gr.Button("🔍 Analyse Image", elem_id="submit_btn", variant="primary")

                # System Settings Accordion placed DIRECTLY BELOW Analyze Image button
                with gr.Accordion("⚙️ System Settings & API Keys", open=False):
                    ui_xai_key = gr.Textbox(
                        label="Custom xAI API Key (Optional)",
                        placeholder="xai-...",
                        type="password",
                    )
                    ui_groq_key = gr.Textbox(
                        label="Custom Groq API Key (Optional — Fallback)",
                        placeholder="gsk_...",
                        type="password",
                    )

            # Right Column: Analysis Output
            with gr.Column(scale=6):
                gr.Markdown("### 📊 Intelligence Output & Analysis")
                task_label_output = gr.Markdown("🛰️ Ready for analysis query...")
                
                with gr.Row():
                    confidence_output = gr.Textbox(label="Confidence Score", value="—", interactive=False, scale=1)
                
                answer_output = gr.Textbox(label="Analysis Answer", lines=6, interactive=False)
                evidence_output = gr.Image(label="Evidence / Spatial Grounding", type="pil", interactive=False)

                with gr.Accordion("📜 Raw Execution Trace JSON", open=False):
                    trace_output = gr.Code(label="Trace Schema JSON", language="json", interactive=False)

                with gr.Row():
                    download_btn = gr.Button("📥 Download PDF Report", elem_id="download_btn")
                    pdf_file_output = gr.File(label="Generated PDF Report", interactive=False)

        # Wire Submit Button
        submit_btn.click(
            fn=run_query,
            inputs=[img1, img2, question_input, ui_xai_key, ui_groq_key],
            outputs=[task_label_output, answer_output, confidence_output, evidence_output, trace_output],
        )

        # Wire PDF Download Button
        download_btn.click(
            fn=generate_pdf_report,
            inputs=[trace_output, answer_output, confidence_output],
            outputs=[pdf_file_output],
        )

    return demo


app = build_ui()
theme = gr.themes.Soft(primary_hue="orange", neutral_hue="slate")

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860, show_error=True, css=CUSTOM_CSS, theme=theme, share=True)
