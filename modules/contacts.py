import streamlit as st
from db import qdf, qrun, audit
from ui import page_header, badge

def render():
    page_header("Contacts", "Manage customers, vendors and users")
    user = st.session_state.get('username', '')
    role = st.session_state.get('role', 'viewer')

    tab1, tab2, tab3 = st.tabs(["📋 All Contacts", "➕ Add Contact", "👤 Users" if role == 'admin' else "👤 Users (Admin)"])

    # ── TAB 1: LIST ────────────────────────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("Search", placeholder="Name, phone, email…", label_visibility="collapsed")
        with col2:
            ftype = st.selectbox("Type", ["All", "Customer", "Vendor", "Both"], label_visibility="collapsed")

        q = "SELECT id, name, type, email, phone, address, tax_id FROM parties WHERE active=1"
        params = []
        if search:
            q += " AND (name LIKE ? OR email LIKE ? OR phone LIKE ?)"
            params += [f"%{search}%"] * 3
        if ftype != "All":
            q += " AND type=?"
            params.append(ftype)
        q += " ORDER BY name"

        df = qdf(q, tuple(params))
        if df.empty:
            st.info("No contacts found.")
        else:
            st.dataframe(df.rename(columns={
                'id':'ID','name':'Name','type':'Type','email':'Email',
                'phone':'Phone','address':'Address','tax_id':'Tax ID'
            }), use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} contact(s) found")

    # ── TAB 2: ADD ─────────────────────────────────────────────────────────────
    with tab2:
        with st.form("add_contact_form"):
            col1, col2 = st.columns(2)
            with col1:
                name    = st.text_input("Full Name *")
                ctype   = st.selectbox("Type *", ["Customer", "Vendor", "Both"])
                email   = st.text_input("Email")
            with col2:
                phone   = st.text_input("Phone")
                tax_id  = st.text_input("NTN / Tax ID")
                address = st.text_area("Address", height=70)

            if st.form_submit_button("💾 Save Contact"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    rid = qrun("INSERT INTO parties (name,type,email,phone,address,tax_id) VALUES (?,?,?,?,?,?)",
                               (name.strip(), ctype, email, phone, address, tax_id))
                    audit(user, "CREATE", "Contact", rid, f"Added {ctype}: {name}")
                    st.success(f"✅ Contact '{name}' saved.")
                    st.rerun()

        # Edit / deactivate
        st.markdown("---")
        st.markdown("#### Edit Contact")
        contacts = qdf("SELECT id, name FROM parties WHERE active=1 ORDER BY name")
        if not contacts.empty:
            options = {row['name']: row['id'] for _, row in contacts.iterrows()}
            sel = st.selectbox("Select contact to edit", list(options.keys()))
            if sel:
                pid = options[sel]
                p = qdf("SELECT * FROM parties WHERE id=?", (pid,))
                if not p.empty:
                    p = p.iloc[0]
                    with st.form("edit_contact_form"):
                        c1, c2 = st.columns(2)
                        with c1:
                            en = st.text_input("Name", value=p['name'])
                            et = st.selectbox("Type", ["Customer","Vendor","Both"],
                                              index=["Customer","Vendor","Both"].index(p['type']))
                            ee = st.text_input("Email", value=p['email'] or "")
                        with c2:
                            ep = st.text_input("Phone", value=p['phone'] or "")
                            etx = st.text_input("Tax ID", value=p['tax_id'] or "")
                            ea = st.text_area("Address", value=p['address'] or "", height=70)
                        col_s, col_d = st.columns([3, 1])
                        with col_s:
                            save = st.form_submit_button("💾 Update")
                        with col_d:
                            deact = st.form_submit_button("🗑 Deactivate", type="secondary")
                        if save:
                            qrun("UPDATE parties SET name=?,type=?,email=?,phone=?,address=?,tax_id=? WHERE id=?",
                                 (en, et, ee, ep, ea, etx, pid))
                            audit(user, "UPDATE", "Contact", pid, f"Updated: {en}")
                            st.success("Updated.")
                            st.rerun()
                        if deact:
                            qrun("UPDATE parties SET active=0 WHERE id=?", (pid,))
                            audit(user, "DELETE", "Contact", pid, f"Deactivated: {p['name']}")
                            st.warning("Contact deactivated.")
                            st.rerun()

    # ── TAB 3: USERS (admin only) ──────────────────────────────────────────────
    with tab3:
        if role != 'admin':
            st.warning("Administrator access required.")
            return

        from db import hash_pw
        st.markdown("#### System Users")
        users_df = qdf("SELECT id, username, full_name, role, active, created_at FROM users ORDER BY id")
        st.dataframe(users_df.rename(columns={
            'id':'ID','username':'Username','full_name':'Full Name',
            'role':'Role','active':'Active','created_at':'Created'
        }), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Add / Update User")
        with st.form("user_form"):
            c1, c2 = st.columns(2)
            with c1:
                uname = st.text_input("Username *")
                fname = st.text_input("Full Name")
                pw    = st.text_input("Password *", type="password")
            with c2:
                urole = st.selectbox("Role", ["admin","manager","sales","purchase","viewer"])
            if st.form_submit_button("➕ Create User"):
                if not uname or not pw:
                    st.error("Username and password are required.")
                else:
                    existing = qdf("SELECT id FROM users WHERE username=?", (uname,))
                    if not existing.empty:
                        st.error("Username already exists.")
                    else:
                        rid = qrun("INSERT INTO users (username,password,full_name,role) VALUES (?,?,?,?)",
                                   (uname, hash_pw(pw), fname, urole))
                        audit(user, "CREATE", "User", rid, f"Created user: {uname} [{urole}]")
                        st.success(f"User '{uname}' created.")
                        st.rerun()
