"""
QR SCANNER PRO — single-file Python application
Run:
    python -m pip install streamlit opencv-python-headless pillow numpy streamlit-webrtc
    python -m streamlit run main.py

Notes:
- Gallery uploads use OpenCV's real QRCodeDetector.
- Live video uses streamlit-webrtc. Browser camera access requires permission;
  public hosting generally requires HTTPS and compatible WebRTC networking.
- History is stored in qr_scanner_history.json beside this file.
"""

import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np
import streamlit as st
from PIL import Image, ImageOps

APP_TITLE = "QR Scanner Pro"
HISTORY_FILE = Path(__file__).resolve().with_name("qr_scanner_history.json")
MAX_UPLOAD_MB = 12
MAX_HISTORY = 500

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------- Styling ----------------------------------------
st.markdown(
    """
    <style>
    :root { color-scheme: dark; }
    .stApp {
        background:
          radial-gradient(ellipse at 10% 0%, rgba(78, 55, 180, .22), transparent 38%),
          radial-gradient(ellipse at 95% 10%, rgba(0, 155, 220, .14), transparent 34%),
          #090d18;
        color: #eef2ff;
    }
    [data-testid="stHeader"] { background: rgba(9,13,24,.7); }
    .block-container { max-width: 1200px; padding-top: 1.6rem; padding-bottom: 3rem; }
    .hero {
        border: 1px solid rgba(145,160,255,.20);
        background: linear-gradient(135deg, rgba(27,35,67,.94), rgba(17,24,45,.88));
        border-radius: 24px; padding: 26px 28px; margin-bottom: 20px;
        box-shadow: 0 18px 60px rgba(0,0,0,.20);
    }
    .brand { font-size: 2rem; font-weight: 850; letter-spacing: -.045em; margin: 0; }
    .brand span { color: #8b9bff; }
    .sub { color: #aab6d4; margin-top: 6px; }
    .panel {
        border: 1px solid rgba(145,160,255,.16);
        background: rgba(17,24,43,.82);
        border-radius: 20px; padding: 20px; margin-bottom: 16px;
    }
    .muted { color: #9ba9c8; font-size: .92rem; }
    .result {
        white-space: pre-wrap; overflow-wrap: anywhere;
        background: rgba(6,11,24,.8); border: 1px solid rgba(124,142,255,.28);
        border-radius: 14px; padding: 16px; color: #eaf0ff;
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    .pill {
        display:inline-block; border-radius:999px; padding:4px 10px;
        background:rgba(108,126,255,.16); border:1px solid rgba(130,145,255,.25);
        color:#cbd4ff; font-size:.8rem; margin-right:6px;
    }
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 12px; font-weight: 650; min-height: 2.6rem;
    }
    [data-testid="stFileUploader"] {
        border: 1px dashed rgba(139,155,255,.5); border-radius: 16px;
        background: rgba(23,32,58,.45); padding: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------- Helpers ----------------------------------------
def read_history():
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        st.warning("History file could not be read. A fresh history is being used.")
    return []


def write_history(items):
    try:
        HISTORY_FILE.write_text(
            json.dumps(items[:MAX_HISTORY], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except OSError:
        st.error("Could not save scan history. Check folder permissions.")
        return False


def classify_payload(value):
    text = (value or "").strip()
    low = text.lower()
    if low.startswith(("https://", "http://")):
        return "Website URL"
    if low.startswith("wifi:"):
        return "Wi-Fi configuration"
    if low.startswith("mailto:") or re.search(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text):
        return "Email"
    if low.startswith("tel:"):
        return "Phone number"
    if low.startswith("begin:vcard"):
        return "Contact card"
    if low.startswith(("geo:", "maps:")):
        return "Location"
    if low.startswith(("upi://", "bitcoin:", "ethereum:")):
        return "Payment / crypto URI"
    return "Plain text"


def safe_http_url(value):
    try:
        parsed = urlparse((value or "").strip())
        return parsed.scheme.lower() in ("http", "https") and bool(parsed.netloc) and not any(
            ch in value for ch in ("\r", "\n", "\x00")
        )
    except (ValueError, TypeError):
        return False


def decode_image(image):
    """Return a list of decoded QR strings using OpenCV."""
    if image is None:
        return []
    detector = cv2.QRCodeDetector()
    found = []

    # Try multi-code support first, if this OpenCV build provides it.
    try:
        ok, decoded_info, points, _ = detector.detectAndDecodeMulti(image)
        if ok and decoded_info:
            found.extend(s.strip() for s in decoded_info if isinstance(s, str) and s.strip())
    except (cv2.error, AttributeError, ValueError):
        pass

    if not found:
        try:
            text, points, _ = detector.detectAndDecode(image)
            if text and text.strip():
                found.append(text.strip())
        except cv2.error:
            pass

    # If no result, retry grayscale and a scaled copy for small QR codes.
    if not found:
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            for candidate in (gray, cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)):
                text, _, _ = detector.detectAndDecode(candidate)
                if text and text.strip():
                    found.append(text.strip())
                    break
        except (cv2.error, ValueError):
            pass

    # Stable de-duplication
    return list(dict.fromkeys(found))


def add_to_history(payload, source):
    payload = payload.strip()
    if not payload:
        return
    items = st.session_state.history
    # Avoid a duplicate at the top from repeated camera frames.
    if items and items[0].get("content") == payload and items[0].get("source") == source:
        try:
            age = time.time() - float(items[0].get("epoch", 0))
            if age < 15:
                return
        except (TypeError, ValueError):
            pass
    entry = {
        "id": uuid.uuid4().hex[:12],
        "content": payload,
        "type": classify_payload(payload),
        "source": source,
        "timestamp": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "epoch": time.time(),
        "favorite": False,
    }
    st.session_state.history.insert(0, entry)
    st.session_state.history = st.session_state.history[:MAX_HISTORY]
    write_history(st.session_state.history)


def set_results(values, source):
    clean = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    if not clean:
        st.session_state.last_error = "No QR code was detected. Try a clearer, brighter image."
        return
    st.session_state.last_error = ""
    st.session_state.results = clean
    st.session_state.result_source = source
    for value in clean:
        add_to_history(value, source)


# ---------------------------- State ------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = read_history()
if "results" not in st.session_state:
    st.session_state.results = []
if "result_source" not in st.session_state:
    st.session_state.result_source = ""
if "last_error" not in st.session_state:
    st.session_state.last_error = ""
if "camera_seen" not in st.session_state:
    st.session_state.camera_seen = set()

# ---------------------------- Header -----------------------------------------
st.markdown(
    """
    <div class="hero">
      <div class="brand">◈ QR <span>SCANNER PRO</span></div>
      <div class="sub">Scan anything. Instantly. &nbsp;·&nbsp; Real QR decoding, not a demo.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar settings
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    st.caption("QR Scanner Pro")
    st.write(f"Maximum upload size: {MAX_UPLOAD_MB} MB")
    st.write(f"History limit: {MAX_HISTORY} scans")
    st.info("Camera access is requested by your browser. Public hosting usually needs HTTPS and compatible WebRTC networking.")
    if st.button("🗑️ Clear all scan history", use_container_width=True):
        st.session_state.history = []
        write_history([])
        st.success("History cleared.")
        st.rerun()

# ---------------------------- Main modes -------------------------------------
camera_tab, upload_tab, history_tab = st.tabs(["📷  Camera scanner", "🖼️  Upload image", "🕘  Scan history"])

with camera_tab:
    st.markdown('<div class="panel"><h3>Live camera scanner</h3><p class="muted">Allow camera permission when your browser asks. Hold a QR code steadily in view.</p></div>', unsafe_allow_html=True)
    try:
        from streamlit_webrtc import RTCConfiguration, WebRtcMode, VideoProcessorBase, webrtc_streamer

        class QRVideoProcessor(VideoProcessorBase):
            def __init__(self):
                self.detector = cv2.QRCodeDetector()
                self.lock = __import__("threading").Lock()
                self.latest = []
                self.last_seen = {}
                self.last_frame_error = ""

            def recv(self, frame):
                img = frame.to_ndarray(format="bgr24")
                try:
                    decoded = []
                    try:
                        ok, infos, points, _ = self.detector.detectAndDecodeMulti(img)
                        if ok and infos:
                            decoded = [x.strip() for x in infos if isinstance(x, str) and x.strip()]
                    except (cv2.error, AttributeError, ValueError):
                        pass
                    if not decoded:
                        try:
                            value, points, _ = self.detector.detectAndDecode(img)
                            if value and value.strip():
                                decoded = [value.strip()]
                        except cv2.error:
                            pass

                    now = time.time()
                    with self.lock:
                        for value in decoded:
                            # Only re-publish a given value every 3 seconds to reduce duplicate events.
                            if now - self.last_seen.get(value, 0) > 3:
                                self.last_seen[value] = now
                                self.latest.append(value)
                        self.latest = self.latest[-10:]

                    # Draw a simple visual outline when a QR is detected.
                    if decoded:
                        try:
                            _, points = self.detector.detect(img)
                            if points is not None:
                                pts = points.astype(int).reshape(-1, 2)
                                if len(pts) >= 4:
                                    cv2.polylines(img, [pts], True, (100, 255, 160), 3)
                        except (cv2.error, AttributeError, ValueError):
                            pass
                except Exception as exc:
                    with self.lock:
                        self.last_frame_error = str(exc)
                return __import__("av").VideoFrame.from_ndarray(img, format="bgr24")

            def take_latest(self):
                with self.lock:
                    values = self.latest[:]
                    self.latest.clear()
                    return values

        rtc_config = RTCConfiguration({
            "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
        })
        webrtc_ctx = webrtc_streamer(
            key="qr-scanner-live",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=rtc_config,
            media_stream_constraints={"video": True, "audio": False},
            video_processor_factory=QRVideoProcessor,
            async_processing=True,
        )

        if webrtc_ctx.video_processor:
            detected = webrtc_ctx.video_processor.take_latest()
            if detected:
                set_results(detected, "Camera")
                st.success(f"Detected {len(detected)} QR code(s) from the live camera.")
                st.rerun()
            if webrtc_ctx.state.playing:
                st.caption("🟢 Camera stream is running. Detected codes appear below.")
            else:
                st.caption("Camera is stopped. Press START to begin scanning.")
    except ImportError:
        st.error("Live camera support is not installed.")
        st.code("python -m pip install streamlit-webrtc av")
    except Exception as exc:
        st.error("The camera integration could not start in this environment.")
        st.caption(f"Details: {exc}")
        st.info("Check browser camera permission, HTTPS (for public hosting), firewall settings, and WebRTC support.")

    st.markdown("#### Latest camera result")
    if st.session_state.results and st.session_state.result_source == "Camera":
        for idx, result in enumerate(st.session_state.results, 1):
            st.markdown(f"**Result {idx} · {classify_payload(result)}**")
            st.code(result, language=None)
            if safe_http_url(result):
                st.link_button("Open link", result)
            st.button("Copy result", key=f"cam_copy_{idx}", on_click=lambda x=result: st.session_state.update(copy_payload=x))
    else:
        st.caption("No camera result yet.")

with upload_tab:
    st.markdown('<div class="panel"><h3>Scan an image</h3><p class="muted">Choose a QR code photo, screenshot, or saved image from your device.</p></div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Choose an image file",
        type=["png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"],
        accept_multiple_files=False,
        help=f"Maximum recommended file size: {MAX_UPLOAD_MB} MB.",
        key="qr_upload",
    )
    if uploaded is not None:
        if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
            st.error(f"Image is too large. Please upload a file smaller than {MAX_UPLOAD_MB} MB.")
        else:
            try:
                pil_image = Image.open(uploaded)
                pil_image = ImageOps.exif_transpose(pil_image).convert("RGB")
                if pil_image.width * pil_image.height > 30_000_000:
                    st.error("Image dimensions are too large to process safely.")
                else:
                    st.image(pil_image, caption="Uploaded image", use_container_width=True)
                    if st.button("🔎 Scan uploaded image", type="primary", use_container_width=True):
                        rgb = np.array(pil_image)
                        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                        with st.spinner("Detecting and decoding QR code…"):
                            values = decode_image(bgr)
                        if values:
                            set_results(values, "Gallery")
                            st.success(f"Successfully decoded {len(values)} QR code(s).")
                        else:
                            st.session_state.last_error = "No QR code was found. Try a sharper image with the entire code visible."
                            st.error(st.session_state.last_error)
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                st.error(f"Could not read this image: {exc}")
            except Exception as exc:
                st.error(f"Image processing failed: {exc}")

    if st.session_state.results and st.session_state.result_source == "Gallery":
        st.markdown("### Decoded result")
        for idx, result in enumerate(st.session_state.results, 1):
            st.markdown(f'<span class="pill">{classify_payload(result)}</span>', unsafe_allow_html=True)
            st.code(result, language=None)
            c1, c2 = st.columns([1, 1])
            with c1:
                st.button("📋 Copy result", key=f"up_copy_{idx}", on_click=lambda x=result: st.session_state.update(copy_payload=x), use_container_width=True)
            with c2:
                if safe_http_url(result):
                    st.link_button("🌐 Open link", result, use_container_width=True)

with history_tab:
    st.markdown('<div class="panel"><h3>Your scan history</h3><p class="muted">Stored in a local JSON file next to main.py. Hosted platforms with temporary storage may erase it on redeployment.</p></div>', unsafe_allow_html=True)
    search = st.text_input("Search history", placeholder="Search scanned text, URL, or content type…")
    filter_type = st.selectbox(
        "Filter by type",
        ["All types", "Website URL", "Plain text", "Wi-Fi configuration", "Email", "Phone number", "Contact card", "Location", "Payment / crypto URI"],
    )
    items = st.session_state.history
    if search:
        items = [x for x in items if search.lower() in x.get("content", "").lower()]
    if filter_type != "All types":
        items = [x for x in items if x.get("type") == filter_type]
    st.caption(f"{len(items)} item(s)")
    if not items:
        st.info("No matching scans yet. Scan a QR code to see it here.")
    for entry in items:
        with st.expander(f"{'⭐ ' if entry.get('favorite') else ''}{entry.get('type', 'QR code')} · {entry.get('timestamp', '')} · {entry.get('source', '')}"):
            st.code(entry.get("content", ""), language=None)
            a, b, c = st.columns(3)
            with a:
                if st.button("📋 Copy", key=f"hist_copy_{entry['id']}", use_container_width=True):
                    st.session_state.copy_payload = entry.get("content", "")
                    st.rerun()
            with b:
                if safe_http_url(entry.get("content", "")):
                    st.link_button("🌐 Open link", entry["content"], use_container_width=True)
            with c:
                if st.button("🗑️ Delete", key=f"hist_del_{entry['id']}", use_container_width=True):
                    st.session_state.history = [x for x in st.session_state.history if x.get("id") != entry["id"]]
                    write_history(st.session_state.history)
                    st.rerun()
            fav_label = "☆ Remove favorite" if entry.get("favorite") else "⭐ Add favorite"
            if st.button(fav_label, key=f"hist_fav_{entry['id']}"):
                for stored in st.session_state.history:
                    if stored.get("id") == entry["id"]:
                        stored["favorite"] = not stored.get("favorite", False)
                write_history(st.session_state.history)
                st.rerun()

# ---------------------------- Current result ---------------------------------
st.markdown("---")
st.markdown("## ✨ Current result")
if st.session_state.results:
    st.caption(f"Source: {st.session_state.result_source or 'Unknown'}")
    for idx, result in enumerate(st.session_state.results, 1):
        st.markdown(f"**{idx}. {classify_payload(result)}**")
        st.code(result, language=None)
        cols = st.columns([1, 1, 1])
        with cols[0]:
            if st.button("📋 Copy", key=f"current_copy_{idx}", use_container_width=True):
                st.session_state.copy_payload = result
                st.rerun()
        with cols[1]:
            if safe_http_url(result):
                st.link_button("🌐 Open link", result, use_container_width=True)
        with cols[2]:
            if st.button("✖ Clear", key=f"current_clear_{idx}", use_container_width=True):
                st.session_state.results = []
                st.session_state.result_source = ""
                st.rerun()
else:
    st.info("Your decoded QR result will appear here.")

if st.session_state.get("copy_payload"):
    payload = st.session_state.copy_payload
    st.markdown("**Copy this result:**")
    st.text_area("Select and copy", value=payload, height=min(180, max(70, len(payload) // 2)), key="copy_fallback")
    st.caption("If your browser supports clipboard access, select the text above and use Ctrl+C.")
    if st.button("Dismiss copy panel"):
        st.session_state.copy_payload = ""
        st.rerun()

st.markdown(
    '<p class="muted" style="text-align:center;margin-top:28px;">QR Scanner Pro · Decodes QR content only; it does not verify whether a QR code or destination is trustworthy.</p>',
    unsafe_allow_html=True,
)
