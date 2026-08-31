"""
Streamlit frontend. Uses a persistent requests.Session() so the httpOnly
JWT cookie set by the backend is stored and replayed automatically —
Streamlit's own session_state is NOT used to store the token (never store
auth tokens in anything JS-readable or serializable to client state).
"""
import streamlit as st
import requests

API_URL =st.secrets.get("API_URL", "http://localhost:8000")

if "session" not in st.session_state:
    st.session_state.session = requests.Session()
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

st.set_page_config(page_title="Requirement Drift Auditor", layout="wide")
st.title("Requirement Drift & Consistency Auditor")

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
if st.sidebar.button("Logout"):
    st.session_state.session.post(f"{API_URL}/auth/logout")
    st.session_state.logged_in = False
    st.rerun()

page = st.sidebar.radio("Navigate", ["Analyze Text", "Upload Documents", "Ask the Assistant"])

if page == "Analyze Text":
    st.subheader("Compare two requirement statements")
    original = st.text_area("Original requirement", max_chars=5000)
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
            col1, col2, col3 = st.columns(3)
            col1.metric("Severity", data["severity"])
            col2.metric("Cosine Similarity", data["cosine_similarity"])
            col3.metric("NLI Label", data["nli_label"])
            if data["model_disagreement_flag"]:
                st.warning("Note: the contradiction model and severity classifier disagreed on this pair.")
        else:
            st.error(r.json().get("detail", "Request failed."))

elif page == "Upload Documents":
    st.subheader("Upload original and updated SRS documents")
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
            st.session_state["last_audit_id"] = r.json()["audit_id"]
            st.json(r.json())
        else:
            st.error(r.json().get("detail", "Upload failed."))

elif page == "Ask the Assistant":
    st.subheader("Ask about your most recent audit")
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
