import streamlit as st
import pandas as pd
from datetime import date
from db import qdf
from ui import page_header

def fmt(n):
    if n is None or (isinstance(n, float) and pd.isna(n)):
        n = 0
    return f"Rs. {n:,.0f}"

def render():
    page_header("Reports", "Financial statements & analytics")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 P&L Statement",
        "⚖️ Balance Sheet",
        "📋 Trial Balance",
        "📅 AR Aging",
        "📅 AP Aging",
    ])

    # ── TAB 1: P&L ─────────────────────────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            from_d = st.date_input("From", value=date(date.today().year, 1, 1), key="pl_from")
        with col2:
            to_d = st.date_input("To", value=date.today(), key="pl_to")

        # Revenue from journal entries in period
        rev = qdf("""SELECT jl.account_name, SUM(jl.credit - jl.debit) as amount
                     FROM journal_lines jl
                     JOIN journal_entries je ON jl.entry_id = je.id
                     JOIN accounts a ON jl.account_name = a.name
                     WHERE a.category='Income' AND je.date BETWEEN ? AND ?
                     GROUP BY jl.account_name""", (str(from_d), str(to_d)))

        exp = qdf("""SELECT jl.account_name, SUM(jl.debit - jl.credit) as amount
                     FROM journal_lines jl
                     JOIN journal_entries je ON jl.entry_id = je.id
                     JOIN accounts a ON jl.account_name = a.name
                     WHERE a.category='Expense' AND je.date BETWEEN ? AND ?
                     GROUP BY jl.account_name""", (str(from_d), str(to_d)))

        total_rev = rev['amount'].sum() if not rev.empty else 0
        total_exp = exp['amount'].sum() if not exp.empty else 0
        net = total_rev - total_exp

        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Revenue",  fmt(total_rev))
        c2.metric("Total Expenses", fmt(total_exp))
        c3.metric("Net Profit" if net >= 0 else "Net Loss", fmt(abs(net)),
                  delta=f"{'Profit' if net >= 0 else 'Loss'}",
                  delta_color="normal" if net >= 0 else "inverse")

        col_r, col_e = st.columns(2)
        with col_r:
            st.markdown("##### Revenue")
            if rev.empty:
                st.info("No revenue in period.")
            else:
                rev['amount'] = rev['amount'].apply(fmt)
                st.dataframe(rev.rename(columns={'account_name':'Account','amount':'Amount'}),
                             use_container_width=True, hide_index=True)
        with col_e:
            st.markdown("##### Expenses")
            if exp.empty:
                st.info("No expenses in period.")
            else:
                exp['amount'] = exp['amount'].apply(fmt)
                st.dataframe(exp.rename(columns={'account_name':'Account','amount':'Amount'}),
                             use_container_width=True, hide_index=True)

    # ── TAB 2: BALANCE SHEET ───────────────────────────────────────────────────
    with tab2:
        df = qdf("SELECT code, name, category, balance FROM accounts WHERE active=1 ORDER BY code")

        assets      = df[df['category'] == 'Asset']
        liabilities = df[df['category'] == 'Liability']
        equity      = df[df['category'] == 'Equity']

        total_assets   = assets['balance'].sum()
        total_liab     = liabilities['balance'].sum()
        total_equity   = equity['balance'].sum()
        retained       = total_assets - total_liab - total_equity

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Assets")
            for _, row in assets.iterrows():
                st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #eee'>"
                            f"<span style='color:#344054'>{row['name']}</span>"
                            f"<span style='font-weight:600'>{fmt(row['balance'])}</span></div>",
                            unsafe_allow_html=True)
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:8px 0;font-weight:700;color:#101828;border-top:2px solid #344054;margin-top:4px'>"
                        f"<span>Total Assets</span><span>{fmt(total_assets)}</span></div>",
                        unsafe_allow_html=True)

        with c2:
            st.markdown("##### Liabilities")
            for _, row in liabilities.iterrows():
                st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #eee'>"
                            f"<span style='color:#344054'>{row['name']}</span>"
                            f"<span style='font-weight:600'>{fmt(row['balance'])}</span></div>",
                            unsafe_allow_html=True)
            st.markdown("##### Equity")
            for _, row in equity.iterrows():
                st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #eee'>"
                            f"<span style='color:#344054'>{row['name']}</span>"
                            f"<span style='font-weight:600'>{fmt(row['balance'])}</span></div>",
                            unsafe_allow_html=True)
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #eee'>"
                        f"<span style='color:#344054'>Retained Earnings</span>"
                        f"<span style='font-weight:600'>{fmt(retained)}</span></div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:8px 0;font-weight:700;color:#101828;border-top:2px solid #344054;margin-top:4px'>"
                        f"<span>Total Liabilities & Equity</span><span>{fmt(total_liab+total_equity+retained)}</span></div>",
                        unsafe_allow_html=True)

    # ── TAB 3: TRIAL BALANCE ───────────────────────────────────────────────────
    with tab3:
        df = qdf("""SELECT code, name, category,
                           CASE WHEN category IN ('Asset','Expense') AND balance>=0 THEN balance ELSE 0 END as debit,
                           CASE WHEN category IN ('Liability','Equity','Income') AND balance>=0 THEN balance
                                WHEN category IN ('Asset','Expense') AND balance<0 THEN -balance ELSE 0 END as credit
                    FROM accounts WHERE active=1 ORDER BY code""")

        total_dr = df['debit'].sum()
        total_cr = df['credit'].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Debits",  fmt(total_dr))
        c2.metric("Total Credits", fmt(total_cr))
        diff = abs(total_dr - total_cr)
        if diff < 0.01:
            c3.success("✅ Books are balanced")
        else:
            c3.error(f"❌ Difference: {fmt(diff)}")

        df['debit']  = df['debit'].apply(fmt)
        df['credit'] = df['credit'].apply(fmt)
        st.dataframe(df.rename(columns={
            'code':'Code','name':'Account','category':'Category',
            'debit':'Debit','credit':'Credit'
        }), use_container_width=True, hide_index=True)

    # ── TAB 4: AR AGING ────────────────────────────────────────────────────────
    with tab4:
        st.markdown("#### Accounts Receivable Aging")
        today = date.today()
        df = qdf("""SELECT party_name, number, date, due_date, (total-paid) as balance
                    FROM invoices WHERE status IN ('posted','partial') AND total > paid
                    ORDER BY due_date""")
        if df.empty:
            st.info("No outstanding receivables.")
        else:
            df['due_date'] = pd.to_datetime(df['due_date'])
            df['days_overdue'] = (pd.Timestamp(today) - df['due_date']).dt.days

            def bucket(d):
                if d <= 0:   return "Current"
                if d <= 30:  return "1-30 days"
                if d <= 60:  return "31-60 days"
                if d <= 90:  return "61-90 days"
                return "90+ days"

            df['aging_bucket'] = df['days_overdue'].apply(bucket)

            # Summary
            pivot = df.groupby('aging_bucket')['balance'].sum().reset_index()
            pivot['balance'] = pivot['balance'].apply(fmt)
            c1, c2 = st.columns(2)
            with c1:
                st.dataframe(pivot.rename(columns={'aging_bucket':'Bucket','balance':'Amount'}),
                             use_container_width=True, hide_index=True)
            with c2:
                st.metric("Total Outstanding", fmt(df['balance'].sum()))

            df['balance'] = df['balance'].apply(fmt)
            st.dataframe(df[['party_name','number','due_date','aging_bucket','days_overdue','balance']].rename(columns={
                'party_name':'Customer','number':'Invoice #','due_date':'Due Date',
                'aging_bucket':'Bucket','days_overdue':'Days','balance':'Balance'
            }), use_container_width=True, hide_index=True)

    # ── TAB 5: AP AGING ────────────────────────────────────────────────────────
    with tab5:
        st.markdown("#### Accounts Payable Aging")
        df = qdf("""SELECT party_name, number, date, due_date, (total-paid) as balance
                    FROM bills WHERE status IN ('posted','partial') AND total > paid
                    ORDER BY due_date""")
        if df.empty:
            st.info("No outstanding payables.")
        else:
            df['due_date'] = pd.to_datetime(df['due_date'])
            df['days_overdue'] = (pd.Timestamp(date.today()) - df['due_date']).dt.days

            def bucket(d):
                if d <= 0:   return "Current"
                if d <= 30:  return "1-30 days"
                if d <= 60:  return "31-60 days"
                if d <= 90:  return "61-90 days"
                return "90+ days"

            df['aging_bucket'] = df['days_overdue'].apply(bucket)
            pivot = df.groupby('aging_bucket')['balance'].sum().reset_index()
            pivot['balance'] = pivot['balance'].apply(fmt)

            c1, c2 = st.columns(2)
            with c1:
                st.dataframe(pivot.rename(columns={'aging_bucket':'Bucket','balance':'Amount'}),
                             use_container_width=True, hide_index=True)
            with c2:
                st.metric("Total Outstanding", fmt(df['balance'].sum()))

            df['balance'] = df['balance'].apply(fmt)
            st.dataframe(df[['party_name','number','due_date','aging_bucket','days_overdue','balance']].rename(columns={
                'party_name':'Vendor','number':'Bill #','due_date':'Due Date',
                'aging_bucket':'Bucket','days_overdue':'Days','balance':'Balance'
            }), use_container_width=True, hide_index=True)
