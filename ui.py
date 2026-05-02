import streamlit as st

# ── THEME ──────────────────────────────────────────────────────────────────────
MODOO_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --pri:     #875BF7;
    --pri-d:   #6941C6;
    --pri-l:   #F4EBFF;
    --green:   #027A48;
    --green-l: #ECFDF3;
    --red:     #B42318;
    --red-l:   #FEF3F2;
    --amber:   #B54708;
    --amber-l: #FFFAEB;
    --navy:    #101828;
    --gray-1:  #344054;
    --gray-2:  #667085;
    --gray-3:  #98A2B3;
    --gray-4:  #D0D5DD;
    --gray-5:  #F2F4F7;
    --white:   #FFFFFF;
    --border:  #EAECF0;
    --radius:  8px;
    --shadow:  0 1px 3px rgba(16,24,40,.1), 0 1px 2px rgba(16,24,40,.06);
}

/* Base */
html, body, .stApp { font-family: 'Plus Jakarta Sans', sans-serif !important; }
.stApp { background: var(--gray-5) !important; }
.block-container { padding: 1.5rem 2rem !important; max-width: 1400px !important; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--navy) !important;
    border-right: none !important;
    min-width: 230px !important;
}
section[data-testid="stSidebar"] * { color: #C8CEDD !important; }
section[data-testid="stSidebar"] .stRadio label { 
    padding: 6px 12px !important; border-radius: 6px !important;
    cursor: pointer; transition: all .15s;
}
section[data-testid="stSidebar"] .stRadio label:hover { 
    background: rgba(255,255,255,.07) !important; color: white !important;
}

/* Cards */
.card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    box-shadow: var(--shadow);
    margin-bottom: 16px;
}
.card-title { font-size: 14px; font-weight: 600; color: var(--gray-2); margin-bottom: 4px; letter-spacing: .02em; text-transform: uppercase; }
.card-value { font-size: 28px; font-weight: 700; color: var(--navy); line-height: 1.2; }
.card-sub   { font-size: 13px; color: var(--gray-3); margin-top: 4px; }

/* Badges */
.badge { display:inline-block; padding:2px 10px; border-radius:99px; font-size:12px; font-weight:600; }
.badge-green  { background:var(--green-l);  color:var(--green); }
.badge-red    { background:var(--red-l);    color:var(--red); }
.badge-amber  { background:var(--amber-l);  color:var(--amber); }
.badge-purple { background:var(--pri-l);    color:var(--pri-d); }
.badge-gray   { background:var(--gray-5);   color:var(--gray-2); }

/* Page header */
.page-header {
    display:flex; align-items:center; justify-content:space-between;
    padding: 0 0 16px; margin-bottom:20px;
    border-bottom: 1px solid var(--border);
}
.page-title { font-size:22px; font-weight:700; color:var(--navy); margin:0; }
.page-sub   { font-size:13px; color:var(--gray-3); margin-top:2px; }

/* Tables */
.stDataFrame { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; }

/* Buttons */
.stButton>button {
    background: var(--pri) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 8px 18px !important;
    transition: all .15s !important;
}
.stButton>button:hover { background: var(--pri-d) !important; }

/* Inputs */
.stTextInput input, .stNumberInput input, .stSelectbox select,
.stDateInput input, .stTextArea textarea {
    border-radius: 6px !important;
    border: 1px solid var(--gray-4) !important;
    font-size: 14px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--pri) !important;
    box-shadow: 0 0 0 3px rgba(135,91,247,.12) !important;
}

/* Metrics */
[data-testid="stMetric"] { background:white; border-radius:var(--radius); padding:16px !important; border:1px solid var(--border); }
[data-testid="stMetricLabel"] { font-size:12px !important; color:var(--gray-2) !important; font-weight:600 !important; letter-spacing:.04em !important; text-transform:uppercase !important; }
[data-testid="stMetricValue"] { font-size:24px !important; font-weight:700 !important; color:var(--navy) !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid var(--border) !important; gap:0 !important; }
.stTabs [data-baseweb="tab"] { font-size:14px !important; font-weight:500 !important; padding:8px 18px !important; color:var(--gray-2) !important; }
.stTabs [aria-selected="true"] { color:var(--pri) !important; border-bottom: 2px solid var(--pri) !important; }

/* Expander */
.stExpander { border: 1px solid var(--border) !important; border-radius:var(--radius) !important; background:white !important; }

/* Divider */
hr { border-color: var(--border) !important; margin: 12px 0 !important; }

/* Success/Error messages */
.stAlert { border-radius: var(--radius) !important; }

/* Mono font for numbers in tables */
.mono { font-family: 'JetBrains Mono', monospace; font-size: 13px; }
</style>
"""

STATUS_BADGE = {
    'draft':     '<span class="badge badge-gray">Draft</span>',
    'posted':    '<span class="badge badge-purple">Posted</span>',
    'paid':      '<span class="badge badge-green">Paid</span>',
    'partial':   '<span class="badge badge-amber">Partial</span>',
    'cancelled': '<span class="badge badge-red">Cancelled</span>',
    'active':    '<span class="badge badge-green">Active</span>',
    'inactive':  '<span class="badge badge-gray">Inactive</span>',
}

def page_header(title, subtitle=""):
    st.markdown(f"""
    <div class="page-header">
        <div>
            <div class="page-title">{title}</div>
            {"<div class='page-sub'>"+subtitle+"</div>" if subtitle else ""}
        </div>
    </div>""", unsafe_allow_html=True)

def kpi_row(metrics):
    """metrics = [(label, value, delta, delta_color), ...]"""
    cols = st.columns(len(metrics))
    for col, (label, value, sub) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="card" style="padding:18px 20px">
                <div class="card-title">{label}</div>
                <div class="card-value">{value}</div>
                <div class="card-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

def badge(status):
    return STATUS_BADGE.get(status.lower(), f'<span class="badge badge-gray">{status}</span>')

MODULES = {
    "📊 Dashboard":    "dashboard",
    "👥 Contacts":     "contacts",
    "🧾 Sales":        "sales",
    "🛒 Purchase":     "purchase",
    "📦 Inventory":    "inventory",
    "📒 Accounting":   "accounting",
    "📈 Reports":      "reports",
    "⚙️ Settings":     "settings",
}

ROLE_ACCESS = {
    "admin":   list(MODULES.keys()),
    "manager": ["📊 Dashboard","👥 Contacts","🧾 Sales","🛒 Purchase","📦 Inventory","📒 Accounting","📈 Reports"],
    "sales":   ["📊 Dashboard","👥 Contacts","🧾 Sales","📦 Inventory"],
    "purchase":["📊 Dashboard","👥 Contacts","🛒 Purchase","📦 Inventory"],
    "viewer":  ["📊 Dashboard","📈 Reports"],
}

def sidebar_nav():
    with st.sidebar:
        st.markdown("""
        <div style="padding:20px 16px 12px; border-bottom:1px solid rgba(255,255,255,.1); margin-bottom:12px;">
            <div style="font-size:20px; font-weight:700; color:white; letter-spacing:-0.5px;">
                Mo<span style="color:#875BF7;">Doo</span>
            </div>
            <div style="font-size:11px; color:#667085; margin-top:2px; letter-spacing:.06em; text-transform:uppercase;">Business Suite</div>
        </div>
        """, unsafe_allow_html=True)

        role = st.session_state.get('role', 'viewer')
        allowed = ROLE_ACCESS.get(role, [])

        options = [m for m in MODULES.keys() if m in allowed]
        choice = st.radio("", options, label_visibility="collapsed",
                          key="nav_choice")

        st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"""
        <div style="padding:8px 4px; font-size:13px;">
            <div style="color:#C8CEDD; font-weight:600;">{st.session_state.get('full_name','User')}</div>
            <div style="color:#667085; font-size:11px; text-transform:uppercase; letter-spacing:.04em;">{role}</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Log Out", key="logout_btn"):
            for k in ['logged_in','username','role','full_name']:
                st.session_state.pop(k, None)
            st.rerun()

    return MODULES[choice]
