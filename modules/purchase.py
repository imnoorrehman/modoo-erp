import streamlit as st
import pandas as pd
from datetime import date, timedelta
from db import qdf, qrun, audit, post_journal_entry, update_account_balance, next_number
from ui import page_header, badge

def fmt(n):
    if n is None or (isinstance(n, float) and pd.isna(n)):
        n = 0
    return f"Rs. {n:,.0f}"

def render():
    page_header("Purchase", "Bills & vendor payments")
    user = st.session_state.get('username', '')

    tab1, tab2, tab3 = st.tabs(["📋 Bills", "➕ New Bill", "💸 Record Payment"])

    # ── TAB 1: LIST ────────────────────────────────────────────────────────────
    with tab1:
        search  = st.text_input("Search", placeholder="Number, vendor…", label_visibility="collapsed")
        fstatus = st.selectbox("Status", ["All","draft","posted","paid","partial","cancelled"],
                               label_visibility="collapsed")

        q = """SELECT id, number, date, party_name, total, paid, (total-paid) as balance, status
               FROM bills WHERE 1=1"""
        params = []
        if search:
            q += " AND (number LIKE ? OR party_name LIKE ?)"
            params += [f"%{search}%"] * 2
        if fstatus != "All":
            q += " AND status=?"
            params.append(fstatus)
        q += " ORDER BY id DESC"

        df = qdf(q, tuple(params))
        if df.empty:
            st.info("No bills found.")
        else:
            df['status_badge'] = df['status'].apply(badge)
            for col in ['total', 'paid', 'balance']:
                df[col] = df[col].apply(fmt)
            df = df.rename(columns={'number':'#','date':'Date','party_name':'Vendor',
                                    'total':'Total','paid':'Paid','balance':'Balance','status_badge':'Status'})
            st.write(df[['#','Vendor','Date','Total','Paid','Balance','Status']].to_html(escape=False, index=False),
                     unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### View / Post Bill")
        bill_list = qdf("SELECT id, number, party_name FROM bills ORDER BY id DESC")
        if not bill_list.empty:
            opts = {f"{r['number']} — {r['party_name']}": r['id'] for _, r in bill_list.iterrows()}
            sel  = st.selectbox("Select Bill", list(opts.keys()))
            if sel:
                bid   = opts[sel]
                bill  = qdf("SELECT * FROM bills WHERE id=?", (bid,)).iloc[0]
                lines = qdf("SELECT product_name, qty, unit_price, subtotal FROM bill_lines WHERE bill_id=?", (bid,))

                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Vendor:** {bill['party_name']}")
                c2.markdown(f"**Date:** {bill['date']}  **Due:** {bill['due_date']}")
                c3.markdown(f"**Status:** {badge(bill['status'])}", unsafe_allow_html=True)

                if not lines.empty:
                    st.dataframe(lines.rename(columns={'product_name':'Product','qty':'Qty',
                                                       'unit_price':'Unit Price','subtotal':'Subtotal'}),
                                 use_container_width=True, hide_index=True)
                    c4, c5 = st.columns(2)
                    c4.metric("Total", fmt(bill['total']))
                    c5.metric("Balance Due", fmt(bill['total'] - bill['paid']))

                if bill['status'] == 'draft':
                    if st.button("🚀 Post Bill", key=f"postb_{bid}"):
                        _post_bill(bid, user)
                        st.success("Bill posted & inventory updated.")
                        st.rerun()
                if bill['status'] not in ('paid', 'cancelled'):
                    if st.button("❌ Cancel Bill", key=f"cancelb_{bid}"):
                        qrun("UPDATE bills SET status='cancelled' WHERE id=?", (bid,))
                        audit(user, "CANCEL", "Bill", bid, f"Cancelled {bill['number']}")
                        st.warning("Bill cancelled.")
                        st.rerun()

    # ── TAB 2: NEW BILL ────────────────────────────────────────────────────────
    with tab2:
        vendors  = qdf("SELECT id, name FROM parties WHERE type IN ('Vendor','Both') AND active=1 ORDER BY name")
        products = qdf("SELECT id, name, cost_price, unit FROM products WHERE active=1 ORDER BY name")

        if vendors.empty:
            st.warning("Add a Vendor contact first.")
            return

        with st.form("new_bill_form", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                vend_names = vendors['name'].tolist()
                vend_sel   = st.selectbox("Vendor *", vend_names)
                vend_id    = int(vendors.loc[vendors['name'] == vend_sel, 'id'].iloc[0])
            with c2:
                bill_date  = st.date_input("Bill Date", value=date.today())
                due_date   = st.date_input("Due Date", value=date.today() + timedelta(days=30))
            with c3:
                notes = st.text_area("Notes", height=70)

            st.markdown("**Line Items**")
            if products.empty:
                st.warning("No products in Inventory.")
                submitted = st.form_submit_button("Save Bill", disabled=True)
            else:
                prod_names = products['name'].tolist()
                n_lines = st.number_input("Number of line items", min_value=1, max_value=20, value=1)
                lines = []
                for i in range(int(n_lines)):
                    lc1, lc2, lc3 = st.columns([3, 1, 1])
                    with lc1:
                        pname = st.selectbox(f"Product {i+1}", prod_names, key=f"bp_{i}")
                        prod_row = products.loc[products['name'] == pname].iloc[0]
                    with lc2:
                        qty = st.number_input("Qty", min_value=0.001, value=1.0, key=f"bq_{i}", format="%.3f")
                    with lc3:
                        uprice = st.number_input("Unit Price", min_value=0.0,
                                                 value=float(prod_row['cost_price']), key=f"bu_{i}")
                    lines.append((int(prod_row['id']), pname, qty, uprice, qty * uprice))

                total = sum(l[4] for l in lines)
                st.markdown(f"**Bill Total: {fmt(total)}**")
                submitted = st.form_submit_button("💾 Save Bill")

            if submitted and not products.empty:
                bill_number = next_number("BILL-", "bills")
                bid = qrun("""INSERT INTO bills (number,date,due_date,party_id,party_name,status,notes,total,created_by)
                              VALUES (?,?,?,?,?,?,?,?,?)""",
                           (bill_number, str(bill_date), str(due_date), vend_id, vend_sel,
                            'draft', notes, total, user))
                for pid, pname, qty, up, sub in lines:
                    qrun("""INSERT INTO bill_lines (bill_id,product_id,product_name,qty,unit_price,subtotal)
                            VALUES (?,?,?,?,?,?)""", (bid, pid, pname, qty, up, sub))
                audit(user, "CREATE", "Bill", bid, f"Created {bill_number} for {vend_sel} — {fmt(total)}")
                st.success(f"✅ Bill {bill_number} saved (Draft). Open bill above to Post it.")
                st.rerun()

    # ── TAB 3: PAYMENT ─────────────────────────────────────────────────────────
    with tab3:
        unpaid = qdf("""SELECT id, number, party_name, (total-paid) as balance
                        FROM bills WHERE status IN ('posted','partial') AND total > paid
                        ORDER BY id DESC""")
        if unpaid.empty:
            st.info("No outstanding bills.")
            return

        with st.form("bill_payment_form"):
            opts = {f"{r['number']} — {r['party_name']} (Due: {fmt(r['balance'])})": (r['id'], r['balance'])
                    for _, r in unpaid.iterrows()}
            sel    = st.selectbox("Bill", list(opts.keys()))
            bid, balance = opts[sel]
            pdate  = st.date_input("Payment Date", value=date.today())
            amt    = st.number_input("Amount Paid", min_value=0.01, max_value=float(balance), value=float(balance))
            acc    = st.selectbox("Paid From", ["Cash on Hand", "Bank Account"])
            if st.form_submit_button("✅ Record Payment"):
                bill = qdf("SELECT * FROM bills WHERE id=?", (bid,)).iloc[0]
                new_paid   = float(bill['paid']) + amt
                new_status = 'paid' if new_paid >= float(bill['total']) else 'partial'
                qrun("UPDATE bills SET paid=?, status=? WHERE id=?", (new_paid, new_status, bid))

                post_journal_entry(str(pdate), "payment", bill['number'],
                    f"Payment to {bill['party_name']}",
                    [("Accounts Payable", bill['party_name'], "Payment", amt, 0),
                     (acc, bill['party_name'], "Payment", 0, amt)],
                    user)
                update_account_balance("Accounts Payable", amt, 0)
                update_account_balance(acc, 0, amt)
                audit(user, "PAYMENT", "Bill", bid, f"Paid {fmt(amt)} on {bill['number']}")
                st.success(f"✅ Payment of {fmt(amt)} recorded.")
                st.rerun()

def _post_bill(bid, user):
    bill  = qdf("SELECT * FROM bills WHERE id=?", (bid,)).iloc[0]
    lines = qdf("SELECT * FROM bill_lines WHERE bill_id=?", (bid,))

    # Journal: Dr Inventory, Cr AP
    je_lines = [
        ("Inventory", bill['party_name'], f"Bill {bill['number']}", float(bill['total']), 0),
        ("Accounts Payable", bill['party_name'], f"Bill {bill['number']}", 0, float(bill['total'])),
    ]
    for _, line in lines.iterrows():
        qrun("UPDATE products SET qty_on_hand = qty_on_hand + ?, cost_price = ? WHERE id=?",
             (float(line['qty']), float(line['unit_price']), int(line['product_id'])))
        qrun("""INSERT INTO stock_moves (date,product_id,product_name,move_type,qty,ref_type,ref_id,notes,created_by)
                VALUES (?,?,?,?,?,?,?,?,?)""",
             (bill['date'], int(line['product_id']), line['product_name'], 'in',
              float(line['qty']), 'bill', bid, f"Purchase {bill['number']}", user))

    post_journal_entry(bill['date'], "purchase", bill['number'],
                       f"Purchase bill {bill['number']} — {bill['party_name']}", je_lines, user)
    update_account_balance("Inventory", float(bill['total']), 0)
    update_account_balance("Accounts Payable", 0, float(bill['total']))

    qrun("UPDATE bills SET status='posted' WHERE id=?", (bid,))
    audit(user, "POST", "Bill", bid, f"Posted {bill['number']} — {fmt(float(bill['total']))}")
