import streamlit as st
import pandas as pd
from datetime import date
from db import qdf, qrun, audit, post_journal_entry, update_account_balance, next_number
from ui import page_header, badge

def fmt(n):
    if n is None or (isinstance(n, float) and pd.isna(n)):
        n = 0
    return f"Rs. {n:,.0f}"

def render():
    page_header("Accounting", "Chart of accounts, journal entries & ledger")
    user = st.session_state.get('username', '')

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Chart of Accounts",
        "📖 Journal Entries",
        "➕ New Entry",
        "📋 General Ledger",
        "🏦 Partner Ledger",
    ])

    # ── TAB 1: CHART OF ACCOUNTS ───────────────────────────────────────────────
    with tab1:
        df = qdf("""SELECT code, name, category, account_type, balance
                    FROM accounts WHERE active=1 ORDER BY code""")

        for cat in ['Asset', 'Liability', 'Equity', 'Income', 'Expense']:
            sub = df[df['category'] == cat].copy()
            if sub.empty:
                continue
            total = sub['balance'].sum()
            with st.expander(f"**{cat}** — {fmt(total)}", expanded=(cat in ['Asset','Income'])):
                sub['balance'] = sub['balance'].apply(fmt)
                st.dataframe(sub.rename(columns={
                    'code':'Code','name':'Account','category':'Category',
                    'account_type':'Type','balance':'Balance'
                }), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Add Account")
        with st.form("add_acc_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                acode = st.text_input("Account Code *")
                aname = st.text_input("Account Name *")
            with c2:
                acat  = st.selectbox("Category", ["Asset","Liability","Equity","Income","Expense"])
                atype = st.text_input("Type (cash/bank/receivable/payable/etc.)", value="other")
            if st.form_submit_button("➕ Add Account"):
                if not acode or not aname:
                    st.error("Code and name are required.")
                else:
                    rid = qrun("INSERT INTO accounts (code,name,category,account_type) VALUES (?,?,?,?)",
                               (acode, aname, acat, atype))
                    audit(user, "CREATE", "Account", rid, f"Added account: {acode} {aname}")
                    st.success(f"Account '{aname}' added.")
                    st.rerun()

    # ── TAB 2: JOURNAL ENTRIES LIST ────────────────────────────────────────────
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            search = st.text_input("Search", placeholder="Number, reference…", label_visibility="collapsed")
        with col2:
            jtype_f = st.selectbox("Type", ["All","manual","sale","purchase","receipt","payment"], label_visibility="collapsed")

        q = "SELECT id, number, date, type, reference, narration, status, created_by FROM journal_entries WHERE 1=1"
        params = []
        if search:
            q += " AND (number LIKE ? OR reference LIKE ? OR narration LIKE ?)"
            params += [f"%{search}%"] * 3
        if jtype_f != "All":
            q += " AND type=?"
            params.append(jtype_f)
        q += " ORDER BY id DESC LIMIT 100"

        df = qdf(q, tuple(params))
        if df.empty:
            st.info("No journal entries found.")
        else:
            df['status'] = df['status'].apply(badge)
            st.write(df.rename(columns={
                'id':'ID','number':'#','date':'Date','type':'Type',
                'reference':'Reference','narration':'Narration','status':'Status','created_by':'By'
            }).to_html(escape=False, index=False), unsafe_allow_html=True)

        # View lines
        st.markdown("---")
        st.markdown("#### View Entry Lines")
        entries = qdf("SELECT id, number, narration FROM journal_entries ORDER BY id DESC LIMIT 50")
        if not entries.empty:
            opts = {f"{r['number']} — {r['narration']}": r['id'] for _, r in entries.iterrows()}
            sel  = st.selectbox("Select Entry", list(opts.keys()))
            if sel:
                eid   = opts[sel]
                lines = qdf("""SELECT account_name, partner, narration, debit, credit
                               FROM journal_lines WHERE entry_id=?""", (eid,))
                if not lines.empty:
                    lines['debit']  = lines['debit'].apply(fmt)
                    lines['credit'] = lines['credit'].apply(fmt)
                    st.dataframe(lines.rename(columns={
                        'account_name':'Account','partner':'Partner',
                        'narration':'Narration','debit':'Debit','credit':'Credit'
                    }), use_container_width=True, hide_index=True)

    # ── TAB 3: NEW JOURNAL ENTRY ───────────────────────────────────────────────
    with tab3:
        accounts = qdf("SELECT id, name FROM accounts WHERE active=1 ORDER BY code")
        acc_names = accounts['name'].tolist()

        st.info("All manual journal entries are posted immediately.")
        with st.form("new_je_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                jdate = st.date_input("Date", value=date.today())
                jref  = st.text_input("Reference")
            with c2:
                jnar  = st.text_area("Narration", height=70)

            st.markdown("**Entry Lines** (must balance: Total Debit = Total Credit)")
            n_lines = st.number_input("Number of lines", min_value=2, max_value=20, value=2)
            lines = []
            total_dr = total_cr = 0.0
            for i in range(int(n_lines)):
                lc1, lc2, lc3, lc4 = st.columns([3, 2, 1, 1])
                with lc1:
                    acc = st.selectbox(f"Account {i+1}", acc_names, key=f"je_acc_{i}")
                with lc2:
                    partner = st.text_input("Partner", key=f"je_par_{i}", label_visibility="collapsed",
                                            placeholder="Partner (optional)")
                with lc3:
                    dr = st.number_input("Debit", min_value=0.0, value=0.0, key=f"je_dr_{i}")
                with lc4:
                    cr = st.number_input("Credit", min_value=0.0, value=0.0, key=f"je_cr_{i}")
                lines.append((acc, partner, f"Line {i+1}", dr, cr))
                total_dr += dr; total_cr += cr

            bal_ok = abs(total_dr - total_cr) < 0.01
            if total_dr > 0:
                if bal_ok:
                    st.success(f"✅ Balanced — Dr: {fmt(total_dr)}  |  Cr: {fmt(total_cr)}")
                else:
                    st.error(f"❌ Not balanced — Dr: {fmt(total_dr)}  |  Cr: {fmt(total_cr)}  |  Diff: {fmt(abs(total_dr-total_cr))}")

            submitted = st.form_submit_button("🚀 Post Journal Entry")
            if submitted:
                if not bal_ok:
                    st.error("Entry does not balance. Please correct before posting.")
                elif total_dr == 0:
                    st.error("Entry cannot be zero.")
                else:
                    eid = post_journal_entry(str(jdate), "manual", jref, jnar, lines, user)
                    for acc_name, _, __, dr, cr in lines:
                        update_account_balance(acc_name, dr, cr)
                    audit(user, "CREATE", "JournalEntry", eid,
                          f"Manual JE | {jnar} | Dr: {fmt(total_dr)}")
                    st.success(f"✅ Journal entry posted.")
                    st.rerun()

    # ── TAB 4: GENERAL LEDGER ─────────────────────────────────────────────────
    with tab4:
        col1, col2, col3 = st.columns(3)
        with col1:
            accounts_list = qdf("SELECT name FROM accounts WHERE active=1 ORDER BY code")
            sel_acc = st.selectbox("Account", accounts_list['name'].tolist())
        with col2:
            date_from = st.date_input("From", value=date(date.today().year, 1, 1))
        with col3:
            date_to = st.date_input("To", value=date.today())

        df = qdf("""SELECT je.date, je.number, jl.partner, jl.narration, jl.debit, jl.credit
                    FROM journal_lines jl
                    JOIN journal_entries je ON jl.entry_id = je.id
                    WHERE jl.account_name=? AND je.date BETWEEN ? AND ?
                    ORDER BY je.date, je.id""",
                 (sel_acc, str(date_from), str(date_to)))

        if df.empty:
            st.info("No transactions in this period.")
        else:
            df['balance'] = (df['debit'].cumsum() - df['credit'].cumsum())
            total_dr = df['debit'].sum()
            total_cr = df['credit'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Debit",  fmt(total_dr))
            c2.metric("Total Credit", fmt(total_cr))
            c3.metric("Net",          fmt(total_dr - total_cr))

            for col in ['debit', 'credit', 'balance']:
                df[col] = df[col].apply(fmt)
            st.dataframe(df.rename(columns={
                'date':'Date','number':'Entry #','partner':'Partner',
                'narration':'Narration','debit':'Debit','credit':'Credit','balance':'Balance'
            }), use_container_width=True, hide_index=True)

    # ── TAB 5: PARTNER LEDGER ─────────────────────────────────────────────────
    with tab5:
        parties = qdf("SELECT name FROM parties WHERE active=1 ORDER BY name")
        if parties.empty:
            st.info("No parties found.")
            return
        sel_party = st.selectbox("Partner", parties['name'].tolist())
        col_a, col_b = st.columns(2)
        with col_a:
            pfrom = st.date_input("From", value=date(date.today().year, 1, 1), key="pl_from")
        with col_b:
            pto   = st.date_input("To",   value=date.today(), key="pl_to")

        df = qdf("""SELECT je.date, je.number, je.type, jl.account_name, jl.narration, jl.debit, jl.credit
                    FROM journal_lines jl
                    JOIN journal_entries je ON jl.entry_id = je.id
                    WHERE jl.partner=? AND je.date BETWEEN ? AND ?
                    ORDER BY je.date, je.id""",
                 (sel_party, str(pfrom), str(pto)))

        if df.empty:
            st.info(f"No transactions for {sel_party} in this period.")
        else:
            total_dr = df['debit'].sum()
            total_cr = df['credit'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Debit",  fmt(total_dr))
            c2.metric("Total Credit", fmt(total_cr))
            c3.metric("Net Balance",  fmt(total_dr - total_cr))

            for col in ['debit', 'credit']:
                df[col] = df[col].apply(fmt)
            st.dataframe(df.rename(columns={
                'date':'Date','number':'Entry #','type':'Type',
                'account_name':'Account','narration':'Narration',
                'debit':'Debit','credit':'Credit'
            }), use_container_width=True, hide_index=True)
