"""
Streamlit frontend. Uses a persistent requests.Session() so the httpOnly
JWT cookie set by the backend is stored and replayed automatically —
Streamlit's own session_state is NOT used to store the token (never store
auth tokens in anything JS-readable or serializable to client state).
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go

API_URL = st.secrets.get("API_URL", "http://localhost:8000")

if "session" not in st.session_state:
    st.session_state.session = requests.Session()
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

st.set_page_config(page_title="Requirement Drift Auditor", layout="wide")

# ---------- VISUAL THEME (styling only — no logic below is changed) ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

:root {
    --bg: #F3F4FC;
    --panel: #FFFFFF;
    --panel-alt: #F7F7FD;
    --border: #E4E5F5;
    --text: #1F2547;
    --muted: #6B7094;
    --violet: #4F46E5;
    --pink: #7C6FEF;
    --green: #16A34A;
    --amber: #C2760C;
    --red: #DC2647;
    --blue: #2563EB;
    --sidebar-top: #2C3080;
    --sidebar-bottom: #1E2266;
}

.stApp { background: var(--bg); color: var(--text); }

/* Sidebar: deep indigo rail, matching the reference palette */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--sidebar-top), var(--sidebar-bottom));
    border-right: none;
}
section[data-testid="stSidebar"] * { color: #F1F1FB; }
section[data-testid="stSidebarUserContent"] {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
}
.sidebar-spacer { flex: 1 1 auto; }
section[data-testid="stSidebar"] .stButton button {
    width: 100%;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.18);
    color: #F1F1FB;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255,255,255,0.16);
}
.sidebar-brand {
    display: flex; align-items: center; gap: 10px;
    padding: 2px 2px 20px 2px;
    border-bottom: 1px solid rgba(255,255,255,0.14);
    margin-bottom: 16px;
}
.sidebar-brand .icon {
    width: 38px; height: 38px; border-radius: 11px;
    background: linear-gradient(135deg, var(--violet), var(--pink));
    display: flex; align-items: center; justify-content: center; font-size: 17px;
    flex-shrink: 0;
}
.sidebar-brand .name { font-weight: 700; font-size: 16px; }
.sidebar-brand .tagline { font-size: 11px; color: #B7B8E6; margin-top: -2px; }
.sidebar-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.6px; color: #9C9DD6; margin: 4px 0 8px 0; }
.sidebar-footer-divider { border-top: 1px solid rgba(255,255,255,0.14); margin: 10px 0 12px 0; }

/* Nav radio items styled as rounded rail buttons, solid highlight on the selected one */
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 3px; }
section[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 10px 12px;
    border-radius: 10px;
    margin-bottom: 2px;
    transition: background 0.15s ease;
    font-weight: 500;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    background: rgba(255,255,255,0.08);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"],
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: linear-gradient(135deg, var(--violet), var(--pink));
    font-weight: 700;
}

/* App title */
.app-header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.app-header .icon {
    width: 40px; height: 40px; border-radius: 10px;
    background: linear-gradient(135deg, var(--violet), var(--pink));
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
}
.app-header h1 { font-size: 26px; font-weight: 700; margin: 0; color: var(--text); }
.app-subtitle { color: var(--muted); font-size: 14px; margin: 0 0 20px 52px; }

/* Card wrapper for grouped sections */
.card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 16px;
}
.card h3 { margin-top: 0; font-size: 15px; font-weight: 600; color: var(--text); }

/* Status pill */
.pill {
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    font-size: 12px; font-weight: 600; letter-spacing: 0.2px;
}
.pill-green { background: rgba(34,197,94,0.15); color: var(--green); }
.pill-amber { background: rgba(245,165,36,0.15); color: var(--amber); }
.pill-red { background: rgba(240,70,107,0.15); color: var(--red); }
.pill-blue { background: rgba(62,139,255,0.15); color: var(--blue); }

/* Streamlit text inputs / textareas */
.stTextInput input, .stTextArea textarea {
    background: var(--panel-alt) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}

/* Primary buttons -> gradient accent (used sparingly, per action) */
.stButton button {
    background: linear-gradient(135deg, var(--violet), var(--pink));
    color: white; border: none; border-radius: 8px;
    font-weight: 600; padding: 0.5rem 1.2rem;
}
.stButton button:hover { opacity: 0.9; color: white; }

/* Metrics as quiet stat blocks (not shadow-cards) */
div[data-testid="stMetric"] {
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
}
div[data-testid="stMetricLabel"] { color: var(--muted); }
div[data-testid="stMetricValue"] { color: var(--text); }

/* Radio nav in sidebar */
div[role="radiogroup"] label { color: var(--text); }

hr { border-color: var(--border); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
    <div class="icon">🛰️</div>
    <h1>Requirement Drift & Consistency Auditor</h1>
</div>
<p class="app-subtitle">Detect semantic drift, contradictions, and impact across requirement changes.</p>
""", unsafe_allow_html=True)

SEVERITY_COLORS = {"LOW": "#16A34A", "MEDIUM": "#C2760C", "HIGH": "#DC2647"}
KNOWN_FIELDS = {"audit_id", "severity", "cosine_similarity", "nli_label", "model_disagreement_flag"}


def render_audit_results(data: dict):
    """Renders an audit result dict as pills/gauge/bar-chart instead of raw JSON.
    Reads via .get() only for display — no request/response handling changes."""
    severity = data.get("severity")
    nli_label = data.get("nli_label")
    cosine = data.get("cosine_similarity")

    top1, top2 = st.columns(2)
    with top1:
        if severity is not None:
            color = SEVERITY_COLORS.get(str(severity).upper(), "#2563EB")
            st.markdown(
                f'<div class="card"><div style="color:var(--muted);font-size:12px;margin-bottom:6px;">Severity</div>'
                f'<span class="pill" style="background:{color}22;color:{color};">{severity}</span></div>',
                unsafe_allow_html=True,
            )
    with top2:
        if nli_label is not None:
            st.markdown(
                f'<div class="card"><div style="color:var(--muted);font-size:12px;margin-bottom:6px;">NLI Label</div>'
                f'<span class="pill pill-blue">{nli_label}</span></div>',
                unsafe_allow_html=True,
            )

    if isinstance(cosine, (int, float)):
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cosine,
            number={"valueformat": ".3f"},
            gauge={
                "axis": {"range": [0, 1]},
                "bar": {"color": "#4F46E5"},
                "bgcolor": "#F7F7FD",
                "borderwidth": 1,
                "bordercolor": "#E4E5F5",
            },
            title={"text": "Cosine Similarity", "font": {"size": 14}},
        ))
        fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", font={"color": "#1F2547"})
        st.plotly_chart(fig, use_container_width=True)

    if data.get("model_disagreement_flag"):
        st.warning("Note: the contradiction model and severity classifier disagreed on this pair.")

    extra_metrics = {
        k: v for k, v in data.items()
        if k not in KNOWN_FIELDS and isinstance(v, (int, float)) and not isinstance(v, bool)
    }
    if extra_metrics:
        st.markdown('<div class="card"><h3>Additional Metrics</h3></div>', unsafe_allow_html=True)
        chart_df = pd.DataFrame(list(extra_metrics.items()), columns=["Metric", "Value"]).set_index("Metric")
        st.bar_chart(chart_df)

    with st.expander("View raw response"):
        st.json(data)

# ---------- AUTH ----------
if not st.session_state.logged_in:
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            r = st.session_state.session.post(f"{API_URL}/auth/login", json={"email": email, "password": password})
            if r.status_code == 200:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error(r.json().get("detail", "Login failed."))

    with tab_register:
        email_r = st.text_input("Email", key="reg_email")
        password_r = st.text_input("Password (8+ chars, upper/lower/digit)", type="password", key="reg_pw")
        if st.button("Register"):
            r = st.session_state.session.post(f"{API_URL}/auth/register", json={"email": email_r, "password": password_r})
            if r.status_code == 200:
                st.success("Registered — please log in.")
            else:
                st.error(str(r.json().get("detail", "Registration failed.")))

    st.stop()

# ---------- MAIN APP (post-login) ----------
st.sidebar.markdown("""
<div class="sidebar-brand">
    <div class="icon">🛰️</div>
    <div>
        <div class="name">ReqAudit</div>
        <div class="tagline">Drift & consistency</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown('<p class="sidebar-label">Navigate</p>', unsafe_allow_html=True)
NAV_ICONS = {
    "Analyze Text": "📝  Analyze Text",
    "Upload Documents": "📤  Upload Documents",
    "Ask the Assistant": "💬  Ask the Assistant",
}
_nav_choice = st.sidebar.radio(
    "Navigate", list(NAV_ICONS.values()), label_visibility="collapsed"
)
page = {v: k for k, v in NAV_ICONS.items()}[_nav_choice]

st.sidebar.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="sidebar-footer-divider"></div>', unsafe_allow_html=True)
if st.sidebar.button("🚪  Logout"):
    st.session_state.session.post(f"{API_URL}/auth/logout")
    st.session_state.logged_in = False
    st.rerun()

if page == "Analyze Text":
    st.markdown('<div class="card"><h3>Compare two requirement statements</h3></div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        original = st.text_area("Original requirement", max_chars=5000)
    with col_b:
        updated = st.text_area("Updated requirement", max_chars=5000)
    if st.button("Analyze"):
        with st.spinner("Analyzing..."):
            r = st.session_state.session.post(
                f"{API_URL}/analyze",
                json={"req_original": original, "req_updated": updated},
            )
        if r.status_code == 200:
            data = r.json()
            st.session_state["last_audit_id"] = data["audit_id"]
            st.markdown('<div class="card"><h3>Analysis Results</h3></div>', unsafe_allow_html=True)
            render_audit_results(data)
        else:
            st.error(r.json().get("detail", "Request failed."))

elif page == "Upload Documents":
    st.markdown('<div class="card"><h3>Upload original and updated SRS documents</h3></div>', unsafe_allow_html=True)
    f1 = st.file_uploader("Original document", type=["pdf", "docx", "txt"])
    f2 = st.file_uploader("Updated document", type=["pdf", "docx", "txt"])
    if st.button("Run Audit") and f1 and f2:
        with st.spinner("Processing documents..."):
            files = {
                "original_file": (f1.name, f1.getvalue()),
                "updated_file": (f2.name, f2.getvalue()),
            }
            r = st.session_state.session.post(f"{API_URL}/upload-analyze", files=files)
        if r.status_code == 200:
            data = r.json()
            st.session_state["last_audit_id"] = data["audit_id"]
            st.markdown('<div class="card"><h3>Audit Results</h3></div>', unsafe_allow_html=True)
            render_audit_results(data)
        else:
            st.error(r.json().get("detail", "Upload failed."))

elif page == "Ask the Assistant":
    st.markdown('<div class="card"><h3>Ask about your most recent audit</h3></div>', unsafe_allow_html=True)
    audit_id = st.session_state.get("last_audit_id")
    if not audit_id:
        st.info("Run an analysis first.")
    else:
        question = st.text_input("Your question", max_chars=500)
        if st.button("Ask") and question:
            r = st.session_state.session.post(
                f"{API_URL}/chat", json={"audit_id": audit_id, "question": question}
            )
            if r.status_code == 200:
                resp = r.json()
                st.write(resp["message"])
                st.caption(f"Engine: {resp.get('engine', 'unknown')}")
                if not resp["answered"]:
                    st.button("Not helpful — email support")
            else:
                st.error(r.json().get("detail", "Request failed."))