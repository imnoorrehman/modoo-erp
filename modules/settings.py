import streamlit as st
from db import qdf, qrun, audit, hash_pw
from ui import page_header

def render():
    page_header("Settings", "System configuration & audit log")
    user = st.session_state.get('username', '')
    role = st.session_state.get('role', 'viewer')

    tab1, tab2, tab3 = st.tabs(["👤 My Profile", "📋 Audit Log", "🔧 System (Admin)"])

    # ── TAB 1: MY PROFILE ─────────────────────────────────────────────────────
    with tab1:
        me = qdf("SELECT username, full_name, role, created_at FROM users WHERE username=?", (user,))
        if not me.empty:
            me = me.iloc[0]
            st.markdown(f"""
            <div class="card">
                <div style="font-size:18px; font-weight:700; color:#101828;">{me['full_name'] or me['username']}</div>
                <div style="color:#667085; margin-top:4px;">@{me['username']} · {me['role'].upper()} · Member since {me['created_at'][:10]}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("#### Change Password")
        with st.form("change_pw_form"):
            old_pw  = st.text_input("Current Password", type="password")
            new_pw  = st.text_input("New Password", type="password")
            conf_pw = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("🔒 Update Password"):
                cur = qdf("SELECT password FROM users WHERE username=?", (user,))
                if cur.empty or cur['password'].iloc[0] != hash_pw(old_pw):
                    st.error("Current password is incorrect.")
                elif new_pw != conf_pw:
                    st.error("New passwords do not match.")
                elif len(new_pw) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    qrun("UPDATE users SET password=? WHERE username=?", (hash_pw(new_pw), user))
                    audit(user, "UPDATE", "User", None, "Password changed")
                    st.success("✅ Password updated successfully.")

    # ── TAB 2: AUDIT LOG ──────────────────────────────────────────────────────
    with tab2:
        col1, col2, col3 = st.columns(3)
        with col1:
            auser = st.text_input("Filter by User", placeholder="Username…", label_visibility="collapsed")
        with col2:
            amodel = st.selectbox("Module", ["All","Contact","Invoice","Bill","Product","Account",
                                              "JournalEntry","Inventory","User"], label_visibility="collapsed")
        with col3:
            aaction = st.selectbox("Action", ["All","CREATE","UPDATE","DELETE","POST","CANCEL","PAYMENT","ADJUST"], label_visibility="collapsed")

        q = "SELECT ts, user, action, model, record_id, details FROM audit_log WHERE 1=1"
        params = []
        if auser:
            q += " AND user LIKE ?"
            params.append(f"%{auser}%")
        if amodel != "All":
            q += " AND model=?"
            params.append(amodel)
        if aaction != "All":
            q += " AND action=?"
            params.append(aaction)
        q += " ORDER BY id DESC LIMIT 500"

        df = qdf(q, tuple(params))
        if df.empty:
            st.info("No activity logs found.")
        else:
            st.caption(f"{len(df)} log entries")
            st.dataframe(df.rename(columns={
                'ts':'Timestamp','user':'User','action':'Action',
                'model':'Module','record_id':'Record ID','details':'Details'
            }), use_container_width=True, hide_index=True)

    # ── TAB 3: SYSTEM (ADMIN) ─────────────────────────────────────────────────
    with tab3:
        if role != 'admin':
            st.warning("Administrator access required.")
            return

        st.markdown("#### User Management")
        df = qdf("SELECT id, username, full_name, role, active, created_at FROM users ORDER BY id")
        st.dataframe(df.rename(columns={
            'id':'ID','username':'Username','full_name':'Full Name',
            'role':'Role','active':'Active','created_at':'Created'
        }), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Reset User Password (Admin)")
        with st.form("admin_reset_pw"):
            users_list = qdf("SELECT username FROM users ORDER BY username")['username'].tolist()
            target_user = st.selectbox("User", users_list)
            new_pw      = st.text_input("New Password", type="password")
            if st.form_submit_button("🔒 Reset Password"):
                if len(new_pw) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    qrun("UPDATE users SET password=? WHERE username=?", (hash_pw(new_pw), target_user))
                    audit(user, "UPDATE", "User", None, f"Admin reset password for: {target_user}")
                    st.success(f"Password reset for {target_user}.")

        st.markdown("---")
        st.markdown("#### Toggle User Status")
        with st.form("toggle_user_form"):
            target = st.selectbox("User to toggle", users_list, key="toggle_sel")
            if st.form_submit_button("Toggle Active/Inactive"):
                cur = qdf("SELECT active FROM users WHERE username=?", (target,))
                if not cur.empty:
                    new_val = 0 if cur['active'].iloc[0] == 1 else 1
                    qrun("UPDATE users SET active=? WHERE username=?", (new_val, target))
                    status = "Activated" if new_val else "Deactivated"
                    audit(user, "UPDATE", "User", None, f"{status} user: {target}")
                    st.success(f"User {target} {status.lower()}.")
                    st.rerun()
