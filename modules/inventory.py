import streamlit as st
import pandas as pd
from datetime import date
from db import qdf, qrun, audit
from ui import page_header

def fmt(n):
    if n is None or (isinstance(n, float) and pd.isna(n)):
        n = 0
    return f"Rs. {n:,.0f}"

def render():
    page_header("Inventory", "Products, stock levels & movements")
    user = st.session_state.get('username', '')

    tab1, tab2, tab3, tab4 = st.tabs(["📦 Products", "➕ Add Product", "🔄 Stock Movements", "✏️ Adjust Stock"])

    # ── TAB 1: PRODUCTS ────────────────────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("Search products", placeholder="Name, code, category…", label_visibility="collapsed")
        with col2:
            low_stock = st.checkbox("Low stock only", value=False)

        q = "SELECT id, code, name, category, unit, qty_on_hand, sale_price, cost_price FROM products WHERE active=1"
        params = []
        if search:
            q += " AND (name LIKE ? OR code LIKE ? OR category LIKE ?)"
            params += [f"%{search}%"] * 3
        if low_stock:
            q += " AND qty_on_hand <= 10"
        q += " ORDER BY name"

        df = qdf(q, tuple(params))
        if df.empty:
            st.info("No products found.")
        else:
            df['sale_price']  = df['sale_price'].apply(fmt)
            df['cost_price']  = df['cost_price'].apply(fmt)
            df['qty_on_hand'] = df['qty_on_hand'].apply(lambda x: f"{x:,.3f}")
            st.dataframe(df.rename(columns={
                'id':'ID','code':'Code','name':'Product','category':'Category',
                'unit':'Unit','qty_on_hand':'On Hand','sale_price':'Sale Price','cost_price':'Cost Price'
            }), use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} product(s)")

        # Edit product
        st.markdown("---")
        st.markdown("#### Edit Product")
        prods = qdf("SELECT id, name FROM products WHERE active=1 ORDER BY name")
        if not prods.empty:
            opts = {r['name']: r['id'] for _, r in prods.iterrows()}
            sel  = st.selectbox("Select product to edit", list(opts.keys()), key="edit_prod_sel")
            if sel:
                pid = opts[sel]
                p   = qdf("SELECT * FROM products WHERE id=?", (pid,)).iloc[0]
                with st.form("edit_prod_form"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        en   = st.text_input("Name", value=p['name'])
                        ec   = st.text_input("Code", value=p['code'] or "")
                        ecat = st.text_input("Category", value=p['category'] or "")
                    with c2:
                        eu  = st.selectbox("Unit", ["MT","KG","TON","PCS","L","M","SET"],
                                           index=["MT","KG","TON","PCS","L","M","SET"].index(p['unit']) if p['unit'] in ["MT","KG","TON","PCS","L","M","SET"] else 0)
                        esp = st.number_input("Sale Price", value=float(p['sale_price']), min_value=0.0)
                        ecp = st.number_input("Cost Price", value=float(p['cost_price']), min_value=0.0)
                    with c3:
                        st.metric("Current Stock", f"{p['qty_on_hand']:,.3f} {p['unit']}")
                    c_save, c_del = st.columns([3, 1])
                    with c_save:
                        save = st.form_submit_button("💾 Update Product")
                    with c_del:
                        deact = st.form_submit_button("🗑 Remove")
                    if save:
                        qrun("UPDATE products SET name=?,code=?,category=?,unit=?,sale_price=?,cost_price=? WHERE id=?",
                             (en, ec, ecat, eu, esp, ecp, pid))
                        audit(user, "UPDATE", "Product", pid, f"Updated: {en}")
                        st.success("Product updated.")
                        st.rerun()
                    if deact:
                        qrun("UPDATE products SET active=0 WHERE id=?", (pid,))
                        audit(user, "DELETE", "Product", pid, f"Removed: {p['name']}")
                        st.warning("Product removed.")
                        st.rerun()

    # ── TAB 2: ADD PRODUCT ─────────────────────────────────────────────────────
    with tab2:
        with st.form("add_prod_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                name  = st.text_input("Product Name *")
                code  = st.text_input("Product Code")
                cat   = st.text_input("Category")
            with c2:
                unit  = st.selectbox("Unit", ["MT","KG","TON","PCS","L","M","SET"])
                sp    = st.number_input("Sale Price", min_value=0.0, value=0.0)
                cp    = st.number_input("Cost Price", min_value=0.0, value=0.0)
            with c3:
                qty   = st.number_input("Opening Stock", min_value=0.0, value=0.0, format="%.3f")
                st.markdown("<br>", unsafe_allow_html=True)
                st.info("Opening stock will be recorded as an adjustment.")

            if st.form_submit_button("💾 Add Product"):
                if not name.strip():
                    st.error("Product name is required.")
                else:
                    pid = qrun("INSERT INTO products (name,code,category,unit,sale_price,cost_price,qty_on_hand) VALUES (?,?,?,?,?,?,?)",
                               (name.strip(), code, cat, unit, sp, cp, qty))
                    if qty > 0:
                        qrun("""INSERT INTO stock_moves (date,product_id,product_name,move_type,qty,ref_type,notes,created_by)
                                VALUES (?,?,?,?,?,?,?,?)""",
                             (str(date.today()), pid, name, 'adjust', qty, 'manual', 'Opening stock', user))
                    audit(user, "CREATE", "Product", pid, f"Added: {name} | Stock: {qty} {unit}")
                    st.success(f"✅ Product '{name}' added.")
                    st.rerun()

    # ── TAB 3: MOVEMENTS ──────────────────────────────────────────────────────
    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            prods_filter = qdf("SELECT id, name FROM products WHERE active=1 ORDER BY name")
            if not prods_filter.empty:
                prod_opts = ["All"] + prods_filter['name'].tolist()
                sel_prod  = st.selectbox("Filter by Product", prod_opts)
        with col2:
            move_type = st.selectbox("Movement Type", ["All", "in", "out", "adjust"])

        q = """SELECT sm.date, p.name as product, sm.move_type as type, sm.qty,
                      sm.ref_type as source, sm.notes, sm.created_by as user
               FROM stock_moves sm
               JOIN products p ON sm.product_id = p.id
               WHERE 1=1"""
        params = []
        if sel_prod != "All":
            q += " AND p.name=?"
            params.append(sel_prod)
        if move_type != "All":
            q += " AND sm.move_type=?"
            params.append(move_type)
        q += " ORDER BY sm.id DESC LIMIT 200"

        df = qdf(q, tuple(params))
        if df.empty:
            st.info("No stock movements found.")
        else:
            df['qty'] = df['qty'].apply(lambda x: f"{x:,.3f}")
            st.dataframe(df.rename(columns={
                'date':'Date','product':'Product','type':'Type',
                'qty':'Qty','source':'Source','notes':'Notes','user':'By'
            }), use_container_width=True, hide_index=True)

    # ── TAB 4: STOCK ADJUSTMENT ────────────────────────────────────────────────
    with tab4:
        st.info("Use this to correct stock counts (physical verification, damages, etc.)")
        prods = qdf("SELECT id, name, qty_on_hand, unit FROM products WHERE active=1 ORDER BY name")
        if prods.empty:
            st.warning("No products found.")
            return

        with st.form("adjust_form"):
            opts = {f"{r['name']} (Current: {r['qty_on_hand']:,.3f} {r['unit']})": (r['id'], r['qty_on_hand'])
                    for _, r in prods.iterrows()}
            sel        = st.selectbox("Product", list(opts.keys()))
            pid, cur   = opts[sel]
            new_qty    = st.number_input("New Quantity (physical count)", min_value=0.0,
                                         value=float(cur), format="%.3f")
            adj_note   = st.text_input("Reason for adjustment")
            if st.form_submit_button("✅ Confirm Adjustment"):
                diff = new_qty - float(cur)
                qrun("UPDATE products SET qty_on_hand=? WHERE id=?", (new_qty, pid))
                prod_name = prods.loc[prods['id'] == pid, 'name'].iloc[0]
                mtype = 'adjust'
                qrun("""INSERT INTO stock_moves (date,product_id,product_name,move_type,qty,ref_type,notes,created_by)
                        VALUES (?,?,?,?,?,?,?,?)""",
                     (str(date.today()), pid, prod_name, mtype, abs(diff), 'manual',
                      f"Adjustment ({'+' if diff>=0 else ''}{diff:,.3f}): {adj_note}", user))
                audit(user, "ADJUST", "Inventory", pid,
                      f"{prod_name}: {cur} → {new_qty} ({adj_note})")
                st.success(f"Stock adjusted. New quantity: {new_qty:,.3f}")
                st.rerun()
