import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

from db import init_db, qdf, hash_pw, audit
from ui import MODOO_CSS, sidebar_nav

# ── INIT ───────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MoDoo Business Suite",
    page_icon="🟣",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(MODOO_CSS, unsafe_allow_html=True)
init_db()

# ── LOGIN GATE ─────────────────────────────────────────────────────────────────
if not st.session_state.get('logged_in'):
    st.markdown("""
    <div style="min-height:100vh; display:flex; align-items:center; justify-content:center; flex-direction:column; padding:0px;">
        <div style="text-align:center; margin-bottom:32px;">
            <div style="font-size:48px; font-weight:800; color:#101828; letter-spacing:-2px; font-family:'Plus Jakarta Sans',sans-serif;">
                Mo<span style="color:#875BF7;">Doo</span>
            </div>
            <div style="color:#667085; font-size:15px; margin-top:6px; letter-spacing:.04em;">Business Management Suite</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("""
        <div class="card" style="padding:32px 28px;">
            <div style="font-size:18px; font-weight:700; color:#101828; margin-bottom:20px;">Sign In</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In →", use_container_width=True)

            if submitted:
                user = qdf("SELECT * FROM users WHERE username=? AND active=1", (username,))
                if not user.empty and user.iloc[0]['password'] == hash_pw(password):
                    row = user.iloc[0]
                    st.session_state['logged_in'] = True
                    st.session_state['username']  = row['username']
                    st.session_state['role']      = row['role']
                    st.session_state['full_name'] = row['full_name'] or row['username']
                    audit(row['username'], "LOGIN", "System", None, "User signed in")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        st.markdown("""
        <div style="text-align:center; margin-top:12px; color:#98A2B3; font-size:12px;">
            Default: admin / admin123
        </div>
        """, unsafe_allow_html=True)

    st.stop()

# ── MAIN APP ───────────────────────────────────────────────────────────────────
module = sidebar_nav()

# Lazy-import module and render
if module == "dashboard":
    from modules.dashboard   import render
elif module == "contacts":
    from modules.contacts    import render
elif module == "sales":
    from modules.sales       import render
elif module == "purchase":
    from modules.purchase    import render
elif module == "inventory":
    from modules.inventory   import render
elif module == "accounting":
    from modules.accounting  import render
elif module == "reports":
    from modules.reports     import render
elif module == "settings":
    from modules.settings    import render
else:
    def render():
        st.info("Module not found.")

render()
