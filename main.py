
import streamlit as st
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
import io
import csv

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="QR Scanner Pro",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0b1020, #111827);
        color: #f8fafc;
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    .hero {
        padding: 28px;
        border: 1px solid #334155;
        border-radius: 22px;
        background: linear-gradient(120deg, #172554, #312e81, #111827);
        margin-bottom: 25px;
    }

    .hero h1 {
        font-size: 42px;
        color: white;
        margin-bottom: 8px;
    }

    .hero p {
        color: #cbd5e1;
        font-size: 16px;
    }

    .panel {
        background: #172033;
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 15px;
    }

    .result-box {
        background: #102b24;
        border: 1px solid #10b981;
        border-radius: 14px;
        padding: 18px;
        overflow-wrap: anywhere;
    }

    .small-text {
        color: #94a3b8;
        font-size: 13px;
    }

    div.stButton > button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 44px;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# SESSION STATE
# =========================================================

if "history" not in st.session_state:
    st.session_state.history = []

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None


# =========================================================
# QR SCANNING FUNCTIONS
# =========================================================

def open_image(uploaded_file):
    """Uploaded image PIL format-ലേക്ക് മാറ്റുന്നു."""
    image = Image.open(uploaded_file)
    image.load()
    return image.convert("RGB")


def scan_qr_codes(pil_image):
    """ചിത്രത്തിൽനിന്ന് ഒന്നോ അതിലധികമോ QR codes വായിക്കുന്നു."""

    image_array = np.array(pil_image)
    image_bgr = cv2.cvtColor(
        image_array,
        cv2.COLOR_RGB2BGR
    )

    detector = cv2.QRCodeDetector()
    results = []

    # ഒന്നിലധികം QR codes ഒരുമിച്ച് വായിക്കാൻ ശ്രമിക്കുന്നു.
    try:
        success, decoded_info, points, _ = (
            detector.detectAndDecodeMulti(image_bgr)
        )

        if success and decoded_info:
            for value in decoded_info:
                if value and value.strip():
                    results.append(value.strip())
    except cv2.error:
        pass

    # Multi-scan വിജയിച്ചില്ലെങ്കിൽ സാധാരണ scan ശ്രമിക്കുന്നു.
    if not results:
        try:
            value, points, _ = detector.detectAndDecode(
                image_bgr
            )

            if value and value.strip():
                results.append(value.strip())
        except cv2.error:
            pass

    # Duplicate results നീക്കം ചെയ്യുന്നു.
    return list(dict.fromkeys(results))


def save_results(results, source):
    """പുതിയ scan-ന്റെ ഫലങ്ങൾ history-യിൽ ചേർക്കുന്നു."""

    if not results:
        return

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    for value in results:
        record = {
            "Time": timestamp,
            "Source": source,
            "Result": value
        }

        if record not in st.session_state.history:
            st.session_state.history.append(record)

    st.session_state.last_scan = {
        "time": timestamp,
        "source": source,
        "results": results
    }


def make_csv(records):
    """Scan history CSV file ആക്കുന്നു."""

    output = io.StringIO()
    fields = ["Time", "Source", "Result"]

    writer = csv.DictWriter(
        output,
        fieldnames=fields
    )

    writer.writeheader()
    writer.writerows(records)

    return output.getvalue().encode("utf-8-sig")


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown("## 📷 QR Scanner Pro")
    st.caption("നിന്റെ Smart QR Scanning Tool")

    st.divider()

    page = st.radio(
        "MENU",
        [
            "🏠 Home",
            "📁 Image Scanner",
            "📸 Camera Scanner",
            "📜 Scan History",
            "ℹ️ About"
        ]
    )

    st.divider()

    st.markdown("### 📊 Scan Statistics")
    st.metric(
        "ആകെ സ്കാൻ ഫലങ്ങൾ",
        len(st.session_state.history)
    )

    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.history = []
        st.session_state.last_scan = None
        st.rerun()

    st.markdown(
        '<p class="small-text">QR Scanner Pro • Python + Streamlit</p>',
        unsafe_allow_html=True
    )


# =========================================================
# HEADER
# =========================================================

st.markdown("""
<div class="hero">
    <h1>📷 QR Scanner Pro</h1>
    <p>
        QR Code സ്കാൻ ചെയ്യൂ • വിവരങ്ങൾ വായിക്കൂ • ഫലങ്ങൾ
        ഡൗൺലോഡ് ചെയ്യൂ
    </p>
</div>
""", unsafe_allow_html=True)


# =========================================================
# HOME PAGE
# =========================================================

if page == "🏠 Home":

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "ആകെ സ്കാനുകൾ",
            len(st.session_state.history)
        )

    with col2:
        st.metric(
            "ഈ സെഷനിലെ ഫലങ്ങൾ",
            len(st.session_state.last_scan["results"])
            if st.session_state.last_scan else 0
        )

    with col3:
        st.metric(
            "സ്കാനർ സ്റ്റാറ്റസ്",
            "Ready ✅"
        )

    st.markdown("## 🚀 QR Scanner ഉപയോഗിക്കാം")

    left, right = st.columns(2)

    with left:
        st.markdown("""
        <div class="panel">
            <h3>📁 Image Scanner</h3>
            <p>
                മൊബൈലിലോ കമ്പ്യൂട്ടറിലോ ഉള്ള QR Code ചിത്രം
                Upload ചെയ്ത് സ്കാൻ ചെയ്യാം.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if st.button(
            "📁 Image Scanner തുറക്കുക",
            use_container_width=True
        ):
            st.session_state.open_page = "📁 Image Scanner"
            st.rerun()

    with right:
        st.markdown("""
        <div class="panel">
            <h3>📸 Camera Scanner</h3>
            <p>
                ക്യാമറയിൽ QR Code കാണിച്ച് ഒരു ചിത്രം എടുത്ത്
                അതിൽനിന്ന് വിവരങ്ങൾ വായിക്കാം.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if st.button(
            "📸 Camera Scanner തുറക്കുക",
            use_container_width=True
        ):
            st.session_state.open_page = "📸 Camera Scanner"
            st.rerun()

    # Home-ൽനിന്നുള്ള navigation
    if "open_page" in st.session_state:
        target = st.session_state.pop("open_page")

        if target == "📁 Image Scanner":
            st.info("Sidebar-ൽ Image Scanner തിരഞ്ഞെടുക്കുക.")
        elif target == "📸 Camera Scanner":
            st.info("Sidebar-ൽ Camera Scanner തിരഞ്ഞെടുക്കുക.")

    st.markdown("### ✨ പ്രധാന സവിശേഷതകൾ")

    st.markdown("""
    - 🖼️ PNG, JPG, JPEG തുടങ്ങിയ ചിത്രങ്ങൾ Upload ചെയ്യാം.
    - 📷 ക്യാമറ ഉപയോഗിച്ച് QR ചിത്രം എടുക്കാം.
    - 🔍 ചിത്രത്തിൽ ഒന്നിലധികം QR codes ഉണ്ടെങ്കിൽ കണ്ടെത്താൻ ശ്രമിക്കും.
    - 📋 സ്കാൻ ചെയ്ത വിവരങ്ങൾ Copy ചെയ്യാം.
    - 📜 സ്കാൻ History കാണാം.
    - 📥 ഫലങ്ങൾ TXT, CSV രൂപത്തിൽ Download ചെയ്യാം.
    """)


# =========================================================
# IMAGE SCANNER
# =========================================================

elif page == "📁 Image Scanner":

    st.markdown("## 📁 QR Code Image Scanner")

    st.write(
        "QR Code ഉള്ള ചിത്രം Upload ചെയ്യുക. "
        "താഴെയുള്ള ബട്ടൺ അമർത്തി സ്കാൻ ചെയ്യാം."
    )

    uploaded_file = st.file_uploader(
        "ചിത്രം തിരഞ്ഞെടുക്കുക",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        key="image_upload"
    )

    if uploaded_file is not None:

        try:
            image = open_image(uploaded_file)

            left, right = st.columns([1, 1])

            with left:
                st.image(
                    image,
                    caption="നിങ്ങൾ Upload ചെയ്ത ചിത്രം",
                    use_container_width=True
                )

            with right:
                st.markdown("### 🖼️ Image Details")
                st.write(f"**File:** {uploaded_file.name}")
                st.write(f"**Width:** {image.width}px")
                st.write(f"**Height:** {image.height}px")

                if st.button(
                    "🔍 Scan QR Code",
                    type="primary",
                    use_container_width=True
                ):
                    with st.spinner("QR Code പരിശോധിക്കുന്നു..."):
                        results = scan_qr_codes(image)

                    if results:
                        save_results(results, "Image Upload")
                        st.success(
                            f"വിജയം! {len(results)} QR ഫലം കണ്ടെത്തി."
                        )
                    else:
                        st.session_state.last_scan = {
                            "time": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "source": "Image Upload",
                            "results": []
                        }

                        st.warning(
                            "QR Code കണ്ടെത്തിയില്ല. "
                            "വ്യക്തമായ ചിത്രം ഉപയോഗിച്ച് വീണ്ടും ശ്രമിക്കുക."
                        )

        except Exception as error:
            st.error(
                "ചിത്രം തുറക്കാൻ കഴിഞ്ഞില്ല. "
                "മറ്റൊരു ചിത്രം ഉപയോഗിച്ച് ശ്രമിക്കുക."
            )

    # ഫലങ്ങൾ
    last = st.session_state.last_scan

    if last and last["source"] == "Image Upload":
        st.divider()
        st.markdown("## 📋 Scan Results")

        if last["results"]:
            for index, result in enumerate(last["results"], start=1):
                st.markdown(
                    f"### QR Code {index}"
                )

                st.code(result, language=None)

                st.download_button(
                    "📥 Download ഈ ഫലം",
                    data=result.encode("utf-8"),
                    file_name=f"qr_result_{index}.txt",
                    mime="text/plain",
                    key=f"image_result_download_{index}"
                )

                if result.lower().startswith(("https://", "http://")):
                    st.markdown(
                        f"[🔗 Link തുറക്കുക]({result})"
                    )
        else:
            st.info("ഈ ചിത്രത്തിൽനിന്ന് QR ഫലം ലഭിച്ചിട്ടില്ല.")


# =========================================================
# CAMERA SCANNER
# =========================================================

elif page == "📸 Camera Scanner":

    st.markdown("## 📸 Camera QR Scanner")

    st.info(
        "ഈ സംവിധാനം ക്യാമറയിൽനിന്ന് ഒരു ചിത്രം എടുക്കുകയാണ്. "
        "ഇത് തുടർച്ചയായി പ്രവർത്തിക്കുന്ന live video scanner അല്ല."
    )

    camera_image = st.camera_input(
        "QR Code ക്യാമറയ്ക്ക് മുന്നിൽ കാണിച്ച് ചിത്രം എടുക്കുക",
        key="camera_photo"
    )

    if camera_image is not None:

        try:
            image = open_image(camera_image)

            st.image(
                image,
                caption="ക്യാമറയിൽ എടുത്ത ചിത്രം",
                use_container_width=True
            )

            if st.button(
                "🔍 Scan Camera Image",
                type="primary",
                use_container_width=True
            ):
                with st.spinner("ക്യാമറ ചിത്രത്തിലെ QR പരിശോധിക്കുന്നു..."):
                    results = scan_qr_codes(image)

                if results:
                    save_results(results, "Camera")
                    st.success(
                        f"{len(results)} QR ഫലം കണ്ടെത്തി!"
                    )
                else:
                    st.session_state.last_scan = {
                        "time": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "source": "Camera",
                        "results": []
                    }

                    st.warning(
                        "QR Code കണ്ടെത്തിയില്ല. "
                        "ക്യാമറയിൽ QR Code വ്യക്തമായി കാണുന്നുണ്ടെന്ന് ഉറപ്പാക്കുക."
                    )

        except Exception:
            st.error(
                "ക്യാമറ ചിത്രം വായിക്കാൻ കഴിഞ്ഞില്ല. "
                "വീണ്ടും ചിത്രം എടുത്ത് ശ്രമിക്കുക."
            )

    last = st.session_state.last_scan

    if last and last["source"] == "Camera":
        st.markdown("### 📋 Camera Scan Results")

        if last["results"]:
            for index, result in enumerate(last["results"], start=1):
                st.write(f"**QR Code {index}**")
                st.code(result, language=None)

                st.download_button(
                    "📥 Download Result",
                    data=result.encode("utf-8"),
                    file_name=f"camera_qr_{index}.txt",
                    mime="text/plain",
                    key=f"camera_download_{index}"
                )

                if result.lower().startswith(("https://", "http://")):
                    st.markdown(
                        f"[🔗 Link തുറക്കുക]({result})"
                    )


# =========================================================
# SCAN HISTORY
# =========================================================

elif page == "📜 Scan History":

    st.markdown("## 📜 QR Scan History")

    records = st.session_state.history

    if records:

        st.write(f"ആകെ ഫലങ്ങൾ: **{len(records)}**")

        st.dataframe(
            records,
            use_container_width=True,
            hide_index=True
        )

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "📥 Download CSV",
                data=make_csv(records),
                file_name="qr_scan_history.csv",
                mime="text/csv",
                use_container_width=True
            )

        with col2:
            txt_content = "\n\n".join(
                f"Time: {r['Time']}\n"
                f"Source: {r['Source']}\n"
                f"Result: {r['Result']}"
                for r in records
            )

            st.download_button(
                "📄 Download TXT",
                data=txt_content.encode("utf-8"),
                file_name="qr_scan_history.txt",
                mime="text/plain",
                use_container_width=True
            )

    else:
        st.info(
            "ഇതുവരെ സ്കാൻ ചെയ്തിട്ടില്ല. "
            "Image Scanner അല്ലെങ്കിൽ Camera Scanner ഉപയോഗിക്കുക."
        )


# =========================================================
# ABOUT
# =========================================================

elif page == "ℹ️ About":

    st.markdown("## ℹ️ QR Scanner Pro")

    st.markdown("""
    QR Scanner Pro ഒരു Python + Streamlit അടിസ്ഥാനമാക്കിയ
    QR Code വായനാ വെബ് ആപ്ലിക്കേഷനാണ്.

    ### ഉപയോഗിച്ച ടെക്നോളജികൾ

    - **Python:** പ്രധാന പ്രോഗ്രാമിംഗ് ഭാഷ
    - **Streamlit:** വെബ് ഇന്റർഫേസ്
    - **OpenCV:** QR Code കണ്ടെത്താനും വായിക്കാനും
    - **NumPy:** ചിത്രങ്ങൾ കൈകാര്യം ചെയ്യാൻ
    - **Pillow:** ചിത്രങ്ങൾ തുറക്കാനും മാറ്റങ്ങൾ വരുത്താനും

    ### ശ്രദ്ധിക്കുക

    - ക്യാമറ പ്രവർത്തിക്കാൻ ബ്രൗസറിന്റെ അനുമതി ആവശ്യമാണ്.
    - സ്കാൻ History നിലവിലെ Streamlit session-ൽ മാത്രമാണ് സൂക്ഷിക്കുന്നത്.
    - App restart ചെയ്താലോ session നഷ്ടപ്പെട്ടാലോ History ഇല്ലാതാകാം.
    - ഈ ആപ്പ് QR ഉള്ള ചിത്രങ്ങൾ സ്കാൻ ചെയ്യുന്നതാണ്; live video streaming അല്ല.
    - QR-ൽ ലഭിക്കുന്ന ലിങ്കുകൾ തുറക്കുന്നതിന് മുമ്പ് അവ വിശ്വസനീയമാണെന്ന് പരിശോധിക്കുക.
    """)

st.divider()

st.markdown(
    "<p style='text-align:center;color:#94a3b8;'>"
    "QR Scanner Pro • Built with Python 🐍"
    "</p>",
    unsafe_allow_html=True
)
