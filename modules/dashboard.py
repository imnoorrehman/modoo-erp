import streamlit as st
import pandas as pd
from db import qdf, audit
from ui import page_header, kpi_row, badge

def fmt(n):
    if n is None or (isinstance(n, float) and pd.isna(n)):
        n = 0
    return f"Rs. {n:,.0f}"

def render():
    page_header("Dashboard", "Business at a glance")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    inv_total = qdf("SELECT COALESCE(SUM(total),0) as v FROM invoices WHERE status != 'cancelled'")['v'].iloc[0]
    inv_paid  = qdf("SELECT COALESCE(SUM(paid),0)  as v FROM invoices WHERE status != 'cancelled'")['v'].iloc[0]
    inv_due   = inv_total - inv_paid

    bill_total = qdf("SELECT COALESCE(SUM(total),0) as v FROM bills WHERE status != 'cancelled'")['v'].iloc[0]
    bill_paid  = qdf("SELECT COALESCE(SUM(paid),0)  as v FROM bills WHERE status != 'cancelled'")['v'].iloc[0]
    bill_due   = bill_total - bill_paid

    cash = qdf("SELECT COALESCE(SUM(balance),0) as v FROM accounts WHERE account_type IN ('cash','bank')")['v'].iloc[0]
    inv_count = qdf("SELECT COUNT(*) as v FROM products WHERE qty_on_hand > 0")['v'].iloc[0]

    kpi_row([
        ("Total Receivable",  fmt(inv_due),   f"of {fmt(inv_total)} invoiced"),
        ("Total Payable",     fmt(bill_due),  f"of {fmt(bill_total)} billed"),
        ("Cash & Bank",       fmt(cash),      "Current liquid position"),
        ("Active Products",   str(int(inv_count)), "with stock on hand"),
    ])

    # ── Two-column layout ──────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🧾 Recent Invoices")
        df = qdf("""SELECT number, party_name, date, total, status
                    FROM invoices ORDER BY id DESC LIMIT 8""")
        if df.empty:
            st.info("No invoices yet.")
        else:
            df['Status'] = df['status'].apply(lambda s: badge(s))
            df['total'] = df['total'].apply(fmt)
            df = df.rename(columns={'number':'#','party_name':'Customer','date':'Date','total':'Total'})
            st.write(df[['#','Customer','Date','Total','Status']].to_html(escape=False, index=False), unsafe_allow_html=True)

    with col2:
        st.markdown("#### 🛒 Recent Bills")
        df = qdf("""SELECT number, party_name, date, total, status
                    FROM bills ORDER BY id DESC LIMIT 8""")
        if df.empty:
            st.info("No bills yet.")
        else:
            df['Status'] = df['status'].apply(lambda s: badge(s))
            df['total'] = df['total'].apply(fmt)
            df = df.rename(columns={'number':'#','party_name':'Vendor','date':'Date','total':'Total'})
            st.write(df[['#','Vendor','Date','Total','Status']].to_html(escape=False, index=False), unsafe_allow_html=True)

    st.markdown("---")

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("#### 📦 Low Stock Alerts")
        df = qdf("SELECT name, qty_on_hand, unit FROM products WHERE qty_on_hand <= 10 AND active=1 ORDER BY qty_on_hand")
        if df.empty:
            st.success("All products have sufficient stock.")
        else:
            st.warning(f"{len(df)} product(s) need restocking")
            st.dataframe(df.rename(columns={'name':'Product','qty_on_hand':'Qty','unit':'Unit'}),
                         use_container_width=True, hide_index=True)

    with col4:
        st.markdown("#### 📋 Recent Activity")
        df = qdf("SELECT ts, user, action, model, details FROM audit_log ORDER BY id DESC LIMIT 10")
        if df.empty:
            st.info("No activity recorded yet.")
        else:
            st.dataframe(df.rename(columns={'ts':'Time','user':'User','action':'Action','model':'Module','details':'Details'}),
                         use_container_width=True, hide_index=True)
