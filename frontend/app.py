import os
import requests
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL")
if not BACKEND_URL:
    try:
        BACKEND_URL = st.secrets.get("BACKEND_URL")
    except Exception:
        pass
if not BACKEND_URL:
    BACKEND_URL = "http://127.0.0.1:8000"

BACKEND_URL = str(BACKEND_URL).strip().rstrip("/")

# Page configuration
st.set_page_config(
    page_title="QueryPilot — Multi-Agent SQL Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling (Modern Enterprise Dashboard - Dark & Light Mode Adaptive) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Badges & Chips */
    .hero-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.35);
        color: #6366f1;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #10b981;
        display: inline-block;
    }

    /* KPI Metrics Card */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 14px;
        margin: 16px 0;
    }
    .metric-box {
        background: var(--secondary-background-color, #f8fafc);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 12px;
        padding: 14px 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-title {
        font-size: 0.75rem;
        text-transform: uppercase;
        font-weight: 700;
        opacity: 0.75;
        letter-spacing: 0.05em;
    }
    .metric-num {
        font-size: 1.55rem;
        font-weight: 800;
        color: var(--text-color, inherit);
        margin-top: 4px;
    }

    /* Agent Pipeline Breadcrumb Trail */
    .pipeline-wrapper {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        padding: 12px 16px;
        background: var(--secondary-background-color, #f8fafc);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 10px;
        margin: 14px 0;
    }
    .pipeline-pill {
        background: var(--background-color, #ffffff);
        border: 1px solid rgba(128, 128, 128, 0.3);
        color: var(--text-color, inherit);
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .pipeline-arrow {
        color: rgba(128, 128, 128, 0.7);
        font-size: 0.8rem;
    }

    /* Audited Summary Banner */
    .summary-banner {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.35);
        border-left: 4px solid #10b981;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 14px 0 20px 0;
    }
    .summary-heading {
        color: #10b981;
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .summary-body {
        color: var(--text-color, inherit);
        font-size: 0.92rem;
        line-height: 1.55;
    }

    /* Human in the loop review alert */
    .hitl-banner {
        background: rgba(245, 158, 11, 0.12);
        border: 1px solid rgba(245, 158, 11, 0.35);
        border-left: 4px solid #f59e0b;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 16px 0;
    }
    .hitl-title {
        color: #f59e0b;
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .hitl-desc {
        color: var(--text-color, inherit);
        opacity: 0.9;
        font-size: 0.88rem;
    }

    /* Chat bubble cards */
    .chat-card-user {
        background: var(--secondary-background-color, #f8fafc);
        border: 1px solid rgba(128, 128, 128, 0.25);
        color: var(--text-color, inherit);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .chat-card-agent {
        background: var(--background-color, #ffffff);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-left: 3px solid #6366f1;
        color: var(--text-color, inherit);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }

    /* Sidebar cards */
    .sidebar-card {
        background: var(--secondary-background-color, #f8fafc);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 10px;
    }

    /* Streamlit overrides */
    div.stButton > button:first-child {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "pending_approval" not in st.session_state:
    st.session_state["pending_approval"] = None


def get_auth_headers():
    token = st.session_state.get("auth_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def logout_user():
    try:
        requests.post(f"{BACKEND_URL}/auth/logout", headers=get_auth_headers(), timeout=5)
    except Exception:
        pass
    st.session_state["authenticated"] = False
    st.session_state["auth_token"] = None
    st.session_state["user"] = None
    st.session_state.pop("dataset_info", None)
    st.session_state.pop("chat_history", None)
    st.session_state.pop("pending_approval", None)
    st.rerun()


def fetch_history():
    try:
        res = requests.get(f"{BACKEND_URL}/history", headers=get_auth_headers(), timeout=5)
        if res.status_code == 200:
            return res.json().get("history", [])
    except Exception:
        pass
    return []


def render_query_results(data: dict, user_question: str):
    """Renders query metrics, pipeline trail, audited summary, and visual charts."""
    # Update local memory
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    st.session_state["chat_history"].append({"role": "user", "content": user_question})
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": data["summary"],
        "sql": data["sql"]
    })

    # Agent Pipeline Trail
    st.markdown("#### 🤖 Multi-Agent Pipeline Trail")
    trail_items = data.get("agent_trail", [])
    pills_html = ' <span class="pipeline-arrow">➔</span> '.join([f'<span class="pipeline-pill">{agent}</span>' for agent in trail_items])
    st.markdown(f'<div class="pipeline-wrapper">{pills_html}</div>', unsafe_allow_html=True)

    # Performance Metric Cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">⚡ Execution Latency</div>
            <div class="metric-num">{data.get('latency_seconds', 0)}s</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">📊 Rows Returned</div>
            <div class="metric-num">{data.get('row_count', len(data.get('rows', [])))}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">🔧 Healing Retries</div>
            <div class="metric-num">{data.get('attempts_needed', 1)}</div>
        </div>
        """, unsafe_allow_html=True)

    # Audited Executive Summary
    st.markdown(f"""
    <div class="summary-banner">
        <div class="summary-heading">📋 Audited Executive Summary</div>
        <div class="summary-body">{data['summary']}</div>
    </div>
    """, unsafe_allow_html=True)

    # Interactive Data Table
    df_results = pd.DataFrame(data.get("rows", []))
    st.markdown("#### 📊 Query Output Table")
    if not df_results.empty:
        st.dataframe(df_results, use_container_width=True)

        # Plotly BI Chart
        cfg = data.get("chart_config", {})
        chart_type = cfg.get("chart_type", "none")
        x_col = cfg.get("x")
        y_col = cfg.get("y")

        if chart_type != "none" and x_col in df_results.columns and y_col in df_results.columns:
            st.markdown(f"#### 📈 Interactive Visualization ({chart_type.title()} Chart)")
            title = cfg.get("title", f"{y_col} by {x_col}")

            if chart_type == "bar":
                fig = px.bar(df_results, x=x_col, y=y_col, title=title)
            elif chart_type == "line":
                fig = px.line(df_results, x=x_col, y=y_col, title=title)
            elif chart_type == "pie":
                fig = px.pie(df_results, names=x_col, values=y_col, title=title)
            elif chart_type == "scatter":
                fig = px.scatter(df_results, x=x_col, y=y_col, title=title)
            else:
                fig = px.bar(df_results, x=x_col, y=y_col, title=title)

            fig.update_layout(
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    else:
        st.warning("Query returned 0 rows.")

    # Collapsible SQL Inspector
    with st.expander("🔍 Inspect Executed SQL Query"):
        st.code(data["sql"], language="sql")


# ==========================================
# AUTHENTICATION SCREEN (LOGIN & REGISTER)
# ==========================================
if not st.session_state["authenticated"]:
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.6, 1])

    with col2:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 20px;">
            <div class="hero-chip">⚡ Multi-Agent SQL Engine v4.1</div>
            <h1 style="font-weight: 800; font-size: 2.3rem; margin: 4px 0; color: var(--text-color, inherit);">QueryPilot</h1>
            <p style="opacity: 0.75; font-size: 0.95rem; margin-top: 0;">Natural Language SQL Intelligence with LangGraph & DuckDB</p>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])

        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("login_form"):
                login_id = st.text_input("Username or Email", placeholder="e.g. rohan or rohan@example.com")
                login_pw = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Sign In to QueryPilot", use_container_width=True, type="primary")

                if submitted:
                    if not login_id.strip() or not login_pw.strip():
                        st.error("Please enter both credentials.")
                    else:
                        try:
                            res = requests.post(
                                f"{BACKEND_URL}/auth/login",
                                json={"username_or_email": login_id, "password": login_pw},
                                timeout=10
                            )
                            if res.status_code == 200:
                                data = res.json()
                                st.session_state["authenticated"] = True
                                st.session_state["auth_token"] = data["token"]
                                st.session_state["user"] = data["user"]
                                st.rerun()
                            else:
                                try:
                                    err_msg = res.json().get("detail", "Invalid login credentials.")
                                except Exception:
                                    err_msg = f"Backend returned HTTP {res.status_code}: {res.text}"
                                st.error(err_msg)
                        except Exception as e:
                            st.error(f"Cannot connect to backend: {e}")

        with tab_signup:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("signup_form"):
                full_name = st.text_input("Full Name", placeholder="e.g. Rohan Kumbhar")
                reg_username = st.text_input("Username", placeholder="e.g. rohan_k")
                reg_email = st.text_input("Email Address", placeholder="e.g. rohan@example.com")
                reg_pw = st.text_input("Password (min 6 chars)", type="password", placeholder="••••••••")
                reg_pw2 = st.text_input("Confirm Password", type="password", placeholder="••••••••")
                created = st.form_submit_button("Register New Account", use_container_width=True, type="primary")

                if created:
                    if not reg_username.strip() or not reg_email.strip() or not reg_pw.strip():
                        st.error("Username, email, and password are required.")
                    elif reg_pw != reg_pw2:
                        st.error("Passwords do not match.")
                    elif len(reg_pw) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        try:
                            res = requests.post(
                                f"{BACKEND_URL}/auth/register",
                                json={
                                    "username": reg_username,
                                    "email": reg_email,
                                    "password": reg_pw,
                                    "full_name": full_name
                                },
                                timeout=10
                            )
                            if res.status_code == 200:
                                data = res.json()
                                st.session_state["authenticated"] = True
                                st.session_state["auth_token"] = data["token"]
                                st.session_state["user"] = data["user"]
                                st.rerun()
                            else:
                                try:
                                    err_msg = res.json().get("detail", "Registration failed.")
                                except Exception:
                                    err_msg = f"Backend returned HTTP {res.status_code}: {res.text}"
                                st.error(err_msg)
                        except Exception as e:
                            st.error(f"Cannot connect to backend: {e}")

    st.stop()


# ==========================================
# AUTHENTICATED DASHBOARD
# ==========================================

# Load history on startup
if not st.session_state.get("chat_history"):
    st.session_state["chat_history"] = fetch_history()

# Header
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
    <div>
        <h2 style="font-weight: 800; margin: 0; color: var(--text-color, inherit);">⚡ QueryPilot Dashboard</h2>
        <p style="opacity: 0.75; font-size: 0.92rem; margin: 2px 0 0 0;">Multi-Agent Orchestration • LangGraph Memory • DuckDB SQL Execution</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    user = st.session_state.get("user", {})
    initial = (user.get("full_name") or user.get("username") or "U")[:1].upper()
    display_title = user.get("full_name") or user.get("username", "User")

    # Profile Card
    st.markdown(f"""
    <div class="sidebar-card">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 36px; height: 36px; border-radius: 50%; background: #6366f1; color: white; display: flex; align-items: center; justify-content: center; font-weight: 700;">
                {initial}
            </div>
            <div>
                <div style="font-weight: 700; color: var(--text-color, inherit); font-size: 0.92rem;">{display_title}</div>
                <div style="opacity: 0.75; font-size: 0.76rem;">@{user.get('username')}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Log Out", use_container_width=True):
        logout_user()

    st.divider()

    # Section 1: Ingestion
    st.markdown("### 📁 1. Data Ingestion")
    data_option = st.radio("Dataset mode:", ["Upload your CSV", "Use sample sales dataset"])

    file_to_send = None
    if data_option == "Upload your CSV":
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded_file is not None:
            file_to_send = ("dataset.csv", uploaded_file.getvalue(), "text/csv")
    else:
        sample_path = os.path.join("sample_data", "sales_sample.csv")
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                file_to_send = ("sales_sample.csv", f.read(), "text/csv")
            st.caption("Using pre-loaded `sales_sample.csv`")

    if st.button("Sync Data to Engine", use_container_width=True):
        if file_to_send:
            with st.spinner("Indexing table in DuckDB..."):
                try:
                    res = requests.post(
                        f"{BACKEND_URL}/upload",
                        files={"file": file_to_send},
                        headers=get_auth_headers(),
                        timeout=30
                    )
                    if res.status_code == 200:
                        st.session_state["dataset_info"] = res.json()["dataset_info"]
                        st.success(f"Indexed {res.json()['dataset_info']['row_count']} rows successfully!")
                    elif res.status_code == 401:
                        st.error("Session expired.")
                        logout_user()
                    else:
                        st.error(f"Upload failed: {res.text}")
                except Exception as err:
                    st.error(f"Connection error: {err}")
        else:
            st.warning("Please choose or upload a CSV file.")

    if "dataset_info" in st.session_state:
        info = st.session_state["dataset_info"]
        st.markdown(f"""
        <div class="sidebar-card" style="padding: 10px; margin-top: 10px;">
            <div style="font-size: 0.82rem; font-weight: 700; color: #10b981;"><span class="status-dot"></span> Active: <code>{info['table_name']}</code></div>
            <div style="font-size: 0.76rem; opacity: 0.75; margin-top: 2px;">{info['row_count']} rows • {len(info['columns'])} columns</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Section 2: Conversational Memory
    st.markdown("### 🧠 2. LangGraph Memory")
    total_turns = len(st.session_state.get("chat_history", [])) // 2
    st.caption(f"Conversational turns remembered: **{total_turns}**")
    if st.button("🗑️ Clear History", use_container_width=True):
        try:
            requests.delete(f"{BACKEND_URL}/history", headers=get_auth_headers(), timeout=5)
            st.session_state["chat_history"] = []
            st.success("Memory cleared!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")


# ==========================================
# MAIN INTERACTION PANEL
# ==========================================

# Conversational History Accordion
if st.session_state.get("chat_history"):
    history_turns = len(st.session_state["chat_history"]) // 2
    with st.expander(f"💬 Conversation History ({history_turns} previous turns)", expanded=False):
        for msg in st.session_state["chat_history"]:
            if msg.get("role") == "user":
                st.markdown(f"""
                <div class="chat-card-user">
                    <span style="font-weight: 700; color: var(--text-color, inherit);">👤 You:</span> {msg.get('content')}
                </div>
                """, unsafe_allow_html=True)
            else:
                sql_line = f'<div style="margin-top: 4px; font-size: 0.78rem; opacity: 0.75;">SQL: <code>{msg.get("sql")}</code></div>' if msg.get("sql") else ""
                st.markdown(f"""
                <div class="chat-card-agent">
                    <span style="font-weight: 700; color: #818cf8;">🤖 QueryPilot:</span> {msg.get('content')}
                    {sql_line}
                </div>
                """, unsafe_allow_html=True)

# Query Box
st.markdown("### 💬 Ask Query or Follow-Up")
question = st.text_input(
    "Ask business question:",
    placeholder="e.g. Which region had the highest total revenue? -> Follow-up: What was its average order value?",
    label_visibility="collapsed"
)

# Execution Controls
c_run, c_hitl = st.columns([1.2, 2.8])
with c_hitl:
    hitl_mode = st.checkbox("🛡️ Require Human Review & Approval before executing", value=False)

with c_run:
    if not hitl_mode:
        run_label = "⚡ Run Multi-Agent Query"
    else:
        run_label = "📋 Plan & Draft for Review"
    submit_query = st.button(run_label, type="primary", use_container_width=True)

# Handle Query Execution
if submit_query:
    if not question.strip():
        st.warning("Please enter a question first.")
    else:
        endpoint = "/draft_query" if hitl_mode else "/query"
        spinnerText = "Agents are planning and drafting SQL query for review..." if hitl_mode else "Multi-Agent team is planning, executing, and auditing..."
        
        with st.spinner(spinnerText):
            try:
                res = requests.post(
                    f"{BACKEND_URL}{endpoint}",
                    json={"question": question},
                    headers=get_auth_headers(),
                    timeout=60
                )
                if res.status_code == 200:
                    res_data = res.json()
                    if res_data.get("status") == "awaiting_approval":
                        st.session_state["pending_approval"] = {
                            "question": question,
                            "sql": res_data["sql"],
                            "agent_trail": res_data.get("agent_trail", []),
                            "thread_id": res_data.get("thread_id", ""),
                            "review_reason": res_data.get("review_reason", "Human review requested prior to execution.")
                        }
                        st.rerun()
                    else:
                        render_query_results(res_data, question)
                elif res.status_code == 401:
                    st.error("Session expired. Please log in again.")
                    logout_user()
                else:
                    st.error(f"Error ({res.status_code}): {res.json().get('detail', res.text)}")
            except Exception as e:
                st.error(f"Error connecting to backend: {e}")


# ==========================================
# HUMAN-IN-THE-LOOP APPROVAL CARD
# ==========================================
if st.session_state.get("pending_approval"):
    pending = st.session_state["pending_approval"]
    st.markdown("<br>", unsafe_allow_html=True)
    
    review_reason = pending.get("review_reason", "Human approval required prior to query execution.")
    st.markdown(f"""
    <div class="hitl-banner">
        <div class="hitl-title">⚠️ Human Approval Required: {review_reason}</div>
        <div class="hitl-desc">Inspect, edit, or adjust the drafted SQL query below before execution.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"**Target Question:** `{pending['question']}`")
    
    # Editable SQL Area
    user_edited_sql = st.text_area(
        "SQL Statement (Editable):",
        value=pending["sql"],
        height=120,
        help="You can modify filters, columns, or clauses directly."
    )

    col_app, col_rej = st.columns(2)
    with col_app:
        if st.button("✅ Approve & Execute Query", type="primary", use_container_width=True):
            with st.spinner("Executing approved query and verifying results..."):
                try:
                    res = requests.post(
                        f"{BACKEND_URL}/execute_approved",
                        json={
                            "thread_id": pending["thread_id"],
                            "question": pending["question"],
                            "approved_sql": user_edited_sql,
                            "agent_trail": pending.get("agent_trail", [])
                        },
                        headers=get_auth_headers(),
                        timeout=60
                    )
                    if res.status_code == 200:
                        exec_data = res.json()
                        st.session_state["pending_approval"] = None
                        st.success("Query approved and executed successfully!")
                        render_query_results(exec_data, pending["question"])
                    elif res.status_code == 401:
                        st.error("Session expired.")
                        logout_user()
                    else:
                        st.error(f"Execution error: {res.json().get('detail', res.text)}")
                except Exception as e:
                    st.error(f"Error during execution: {e}")

    with col_rej:
        if st.button("❌ Reject & Cancel", use_container_width=True):
            st.session_state["pending_approval"] = None
            st.warning("Draft query cancelled.")
            st.rerun()