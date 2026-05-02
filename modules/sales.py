import streamlit as st
import pandas as pd
from datetime import date, timedelta
from db import qdf, qrun, qmany, audit, post_journal_entry, update_account_balance, next_number
from ui import page_header, badge

def fmt(n):
    if n is None or (isinstance(n, float) and pd.isna(n)):
        n = 0
    return f"Rs. {n:,.0f}"

def render():
    page_header("Sales", "Invoices & customer payments")
    user = st.session_state.get('username', '')

    tab1, tab2, tab3 = st.tabs(["📋 Invoices", "➕ New Invoice", "💰 Record Payment"])

    # ── TAB 1: LIST ────────────────────────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("Search invoices", placeholder="Number, customer…", label_visibility="collapsed")
        with col2:
            fstatus = st.selectbox("Status", ["All","draft","posted","paid","partial","cancelled"], label_visibility="collapsed")

        q = """SELECT id, number, date, party_name, total, paid, (total-paid) as balance, status
               FROM invoices WHERE 1=1"""
        params = []
        if search:
            q += " AND (number LIKE ? OR party_name LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]
        if fstatus != "All":
            q += " AND status=?"
            params.append(fstatus)
        q += " ORDER BY id DESC"

        df = qdf(q, tuple(params))
        if df.empty:
            st.info("No invoices found.")
        else:
            df['status_badge'] = df['status'].apply(badge)
            df['total']   = df['total'].apply(fmt)
            df['paid']    = df['paid'].apply(fmt)
            df['balance'] = df['balance'].apply(fmt)
            df = df.rename(columns={'number':'#','date':'Date','party_name':'Customer',
                                    'total':'Total','paid':'Paid','balance':'Balance','status_badge':'Status'})
            st.write(df[['#','Customer','Date','Total','Paid','Balance','Status']].to_html(escape=False, index=False),
                     unsafe_allow_html=True)

        # View single invoice
        st.markdown("---")
        st.markdown("#### View / Post Invoice")
        inv_list = qdf("SELECT id, number, party_name FROM invoices ORDER BY id DESC")
        if not inv_list.empty:
            opts = {f"{r['number']} — {r['party_name']}": r['id'] for _, r in inv_list.iterrows()}
            sel = st.selectbox("Select Invoice", list(opts.keys()))
            if sel:
                inv_id = opts[sel]
                inv    = qdf("SELECT * FROM invoices WHERE id=?", (inv_id,)).iloc[0]
                lines  = qdf("SELECT product_name, qty, unit_price, subtotal FROM invoice_lines WHERE invoice_id=?", (inv_id,))

                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Customer:** {inv['party_name']}")
                c2.markdown(f"**Date:** {inv['date']}  **Due:** {inv['due_date']}")
                c3.markdown(f"**Status:** {badge(inv['status'])}", unsafe_allow_html=True)

                if not lines.empty:
                    st.dataframe(lines.rename(columns={'product_name':'Product','qty':'Qty',
                                                       'unit_price':'Unit Price','subtotal':'Subtotal'}),
                                 use_container_width=True, hide_index=True)
                    c4, c5 = st.columns(2)
                    c4.metric("Total", fmt(inv['total']))
                    c5.metric("Balance Due", fmt(inv['total'] - inv['paid']))

                if inv['status'] == 'draft':
                    if st.button("🚀 Post Invoice", key=f"post_{inv_id}"):
                        _post_invoice(inv_id, user)
                        st.success("Invoice posted & inventory updated.")
                        st.rerun()
                if inv['status'] not in ('paid', 'cancelled'):
                    if st.button("❌ Cancel Invoice", key=f"cancel_{inv_id}"):
                        qrun("UPDATE invoices SET status='cancelled' WHERE id=?", (inv_id,))
                        audit(user, "CANCEL", "Invoice", inv_id, f"Cancelled {inv['number']}")
                        st.warning("Invoice cancelled.")
                        st.rerun()

    # ── TAB 2: NEW INVOICE ─────────────────────────────────────────────────────
    with tab2:
        customers = qdf("SELECT id, name FROM parties WHERE type IN ('Customer','Both') AND active=1 ORDER BY name")
        products  = qdf("SELECT id, name, sale_price, qty_on_hand, unit FROM products WHERE active=1 ORDER BY name")

        if customers.empty:
            st.warning("Add a Customer contact first.")
            return

        with st.form("new_invoice_form", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                cust_names = customers['name'].tolist()
                cust_sel   = st.selectbox("Customer *", cust_names)
                cust_id    = int(customers.loc[customers['name'] == cust_sel, 'id'].iloc[0])
            with c2:
                inv_date   = st.date_input("Invoice Date", value=date.today())
                due_date   = st.date_input("Due Date", value=date.today() + timedelta(days=30))
            with c3:
                notes = st.text_area("Notes", height=70)

            st.markdown("**Line Items**")
            if products.empty:
                st.warning("No products found. Add products in Inventory first.")
                submitted = st.form_submit_button("Save Invoice", disabled=True)
            else:
                prod_names = products['name'].tolist()
                n_lines = st.number_input("Number of line items", min_value=1, max_value=20, value=1)

                lines = []
                for i in range(int(n_lines)):
                    lc1, lc2, lc3 = st.columns([3, 1, 1])
                    with lc1:
                        pname = st.selectbox(f"Product {i+1}", prod_names, key=f"sp_{i}")
                        prod_row = products.loc[products['name'] == pname].iloc[0]
                    with lc2:
                        qty = st.number_input("Qty", min_value=0.001, value=1.0, key=f"sq_{i}", format="%.3f")
                    with lc3:
                        uprice = st.number_input("Unit Price", min_value=0.0,
                                                 value=float(prod_row['sale_price']), key=f"su_{i}")
                    lines.append((int(prod_row['id']), pname, qty, uprice, qty * uprice))

                total = sum(l[4] for l in lines)
                st.markdown(f"**Invoice Total: {fmt(total)}**")
                submitted = st.form_submit_button("💾 Save Invoice")

            if submitted and not products.empty:
                inv_number = next_number("INV-", "invoices")
                inv_id = qrun("""INSERT INTO invoices (number,date,due_date,party_id,party_name,status,notes,total,created_by)
                                 VALUES (?,?,?,?,?,?,?,?,?)""",
                              (inv_number, str(inv_date), str(due_date), cust_id, cust_sel,
                               'draft', notes, total, user))
                for pid, pname, qty, up, sub in lines:
                    qrun("""INSERT INTO invoice_lines (invoice_id,product_id,product_name,qty,unit_price,subtotal)
                            VALUES (?,?,?,?,?,?)""", (inv_id, pid, pname, qty, up, sub))
                audit(user, "CREATE", "Invoice", inv_id, f"Created {inv_number} for {cust_sel} — {fmt(total)}")
                st.success(f"✅ Invoice {inv_number} saved (Draft). Open the invoice to Post it.")
                st.rerun()

    # ── TAB 3: PAYMENT ─────────────────────────────────────────────────────────
    with tab3:
        unpaid = qdf("""SELECT id, number, party_name, (total-paid) as balance
                        FROM invoices WHERE status IN ('posted','partial') AND total > paid
                        ORDER BY id DESC""")
        if unpaid.empty:
            st.info("No outstanding invoices.")
            return

        with st.form("payment_form"):
            opts = {f"{r['number']} — {r['party_name']} (Due: {fmt(r['balance'])})": (r['id'], r['balance'])
                    for _, r in unpaid.iterrows()}
            sel     = st.selectbox("Invoice", list(opts.keys()))
            inv_id, balance = opts[sel]
            pdate   = st.date_input("Payment Date", value=date.today())
            amt     = st.number_input("Amount Received", min_value=0.01, max_value=float(balance), value=float(balance))
            acc     = st.selectbox("Received Into", ["Cash on Hand", "Bank Account"])
            if st.form_submit_button("✅ Record Payment"):
                inv = qdf("SELECT * FROM invoices WHERE id=?", (inv_id,)).iloc[0]
                new_paid = float(inv['paid']) + amt
                new_status = 'paid' if new_paid >= float(inv['total']) else 'partial'
                qrun("UPDATE invoices SET paid=?, status=? WHERE id=?", (new_paid, new_status, inv_id))

                # Journal: Dr Cash/Bank, Cr AR
                eid = post_journal_entry(str(pdate), "receipt", inv['number'],
                    f"Payment received from {inv['party_name']}",
                    [(acc, inv['party_name'], "Receipt", amt, 0),
                     ("Accounts Receivable", inv['party_name'], "Receipt", 0, amt)],
                    user)
                update_account_balance(acc, amt, 0)
                update_account_balance("Accounts Receivable", 0, amt)
                audit(user, "PAYMENT", "Invoice", inv_id,
                      f"Payment {fmt(amt)} on {inv['number']}")
                st.success(f"✅ Payment of {fmt(amt)} recorded.")
                st.rerun()

def _post_invoice(inv_id, user):
    inv   = qdf("SELECT * FROM invoices WHERE id=?", (inv_id,)).iloc[0]
    lines = qdf("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv_id,))

    # Journal: Dr AR, Cr Sales + COGS
    je_lines = [
        ("Accounts Receivable", inv['party_name'], f"Invoice {inv['number']}", float(inv['total']), 0),
        ("Sales Revenue", inv['party_name'], f"Invoice {inv['number']}", 0, float(inv['total'])),
    ]
    for _, line in lines.iterrows():
        prod = qdf("SELECT cost_price FROM products WHERE id=?", (int(line['product_id']),))
        if not prod.empty:
            cost = float(prod['cost_price'].iloc[0]) * float(line['qty'])
            je_lines.append(("Cost of Goods Sold", inv['party_name'], f"COGS {inv['number']}", cost, 0))
            je_lines.append(("Inventory", inv['party_name'], f"COGS {inv['number']}", 0, cost))
        # Reduce stock
        qrun("UPDATE products SET qty_on_hand = qty_on_hand - ? WHERE id=?",
             (float(line['qty']), int(line['product_id'])))
        qrun("""INSERT INTO stock_moves (date,product_id,product_name,move_type,qty,ref_type,ref_id,notes,created_by)
                VALUES (?,?,?,?,?,?,?,?,?)""",
             (inv['date'], int(line['product_id']), line['product_name'], 'out',
              float(line['qty']), 'invoice', inv_id, f"Sale {inv['number']}", user))

    post_journal_entry(inv['date'], "sale", inv['number'],
                       f"Sales invoice {inv['number']} — {inv['party_name']}", je_lines, user)
    update_account_balance("Accounts Receivable", float(inv['total']), 0)
    update_account_balance("Sales Revenue", 0, float(inv['total']))

    qrun("UPDATE invoices SET status='posted' WHERE id=?", (inv_id,))
    audit(user, "POST", "Invoice", inv_id, f"Posted {inv['number']} — {fmt(float(inv['total']))}")
