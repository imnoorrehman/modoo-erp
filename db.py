import sqlite3
import hashlib
import pandas as pd
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "modoo.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def qdf(query, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)

def qrun(query, params=()):
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return cur.lastrowid

def qmany(query, data):
    with get_conn() as conn:
        conn.executemany(query, data)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── AUDIT LOG ──────────────────────────────────────────────────────────────────
def audit(user, action, model, record_id=None, details=""):
    qrun("""INSERT INTO audit_log (ts, user, action, model, record_id, details)
            VALUES (?,?,?,?,?,?)""",
         (datetime.now().isoformat(timespec='seconds'), user, action, model, record_id, details))

# ── SCHEMA INIT ────────────────────────────────────────────────────────────────
def init_db():
    with get_conn() as conn:
        c = conn.cursor()

        # Users & Roles
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL DEFAULT 'viewer',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        # Audit log
        c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, user TEXT, action TEXT,
            model TEXT, record_id INTEGER, details TEXT
        )""")

        # Chart of Accounts
        c.execute("""CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,   -- Asset/Liability/Equity/Income/Expense
            account_type TEXT,        -- bank/cash/receivable/payable/etc
            balance REAL DEFAULT 0,
            active INTEGER DEFAULT 1
        )""")

        # Parties (Customers / Vendors / Both)
        c.execute("""CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,       -- Customer/Vendor/Both
            email TEXT, phone TEXT, address TEXT,
            tax_id TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        # Products
        c.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT,
            category TEXT,
            unit TEXT DEFAULT 'MT',
            sale_price REAL DEFAULT 0,
            cost_price REAL DEFAULT 0,
            qty_on_hand REAL DEFAULT 0,
            active INTEGER DEFAULT 1
        )""")

        # Sales Invoices
        c.execute("""CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE,
            date TEXT,
            due_date TEXT,
            party_id INTEGER REFERENCES parties(id),
            party_name TEXT,
            status TEXT DEFAULT 'draft',  -- draft/posted/paid/cancelled
            notes TEXT,
            total REAL DEFAULT 0,
            paid REAL DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS invoice_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            product_name TEXT,
            qty REAL, unit_price REAL, subtotal REAL
        )""")

        # Purchase Bills
        c.execute("""CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE,
            date TEXT,
            due_date TEXT,
            party_id INTEGER REFERENCES parties(id),
            party_name TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            total REAL DEFAULT 0,
            paid REAL DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS bill_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            product_name TEXT,
            qty REAL, unit_price REAL, subtotal REAL
        )""")

        # Journal Entries (Accounting)
        c.execute("""CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE,
            date TEXT,
            type TEXT,   -- manual/payment/receipt/sale/purchase
            reference TEXT,
            narration TEXT,
            status TEXT DEFAULT 'draft',  -- draft/posted
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER REFERENCES journal_entries(id) ON DELETE CASCADE,
            account_id INTEGER REFERENCES accounts(id),
            account_name TEXT,
            partner TEXT,
            narration TEXT,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0
        )""")

        # Inventory Movements
        c.execute("""CREATE TABLE IF NOT EXISTS stock_moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            product_id INTEGER REFERENCES products(id),
            product_name TEXT,
            move_type TEXT,  -- in/out/adjust
            qty REAL,
            ref_type TEXT,   -- invoice/bill/manual
            ref_id INTEGER,
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        # ── SEED DATA ──────────────────────────────────────────────────────────
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            c.execute("""INSERT INTO users (username,password,full_name,role)
                         VALUES (?,?,?,?)""",
                      ('admin', hash_pw('admin123'), 'Administrator', 'admin'))

        c.execute("SELECT COUNT(*) FROM accounts")
        if c.fetchone()[0] == 0:
            coa = [
                ('1010','Cash on Hand','Asset','cash'),
                ('1020','Bank Account','Asset','bank'),
                ('1100','Accounts Receivable','Asset','receivable'),
                ('1200','Inventory','Asset','inventory'),
                ('1300','Other Current Assets','Asset','current_asset'),
                ('2100','Accounts Payable','Liability','payable'),
                ('2200','Other Current Liabilities','Liability','current_liability'),
                ('3100','Owner Capital','Equity','equity'),
                ('3200','Retained Earnings','Equity','equity'),
                ('4100','Sales Revenue','Income','income'),
                ('5100','Cost of Goods Sold','Expense','cogs'),
                ('5200','Operating Expenses','Expense','expense'),
                ('5300','Bank Charges','Expense','expense'),
            ]
            for row in coa:
                c.execute("INSERT INTO accounts (code,name,category,account_type) VALUES (?,?,?,?)", row)

# ── SEQUENCE HELPERS ───────────────────────────────────────────────────────────
def next_number(prefix, table, col="number"):
    df = qdf(f"SELECT MAX(CAST(SUBSTR({col},?) AS INTEGER)) as mx FROM {table} WHERE {col} LIKE ?",
             (len(prefix)+1, f"{prefix}%"))
    mx = df['mx'].iloc[0]
    n = int(mx) + 1 if mx else 1
    return f"{prefix}{n:04d}"

# ── POSTING HELPERS ────────────────────────────────────────────────────────────
def post_journal_entry(date, jtype, ref, narration, lines, created_by, status="posted"):
    """lines = [(account_name, partner, narration, debit, credit), ...]"""
    number = next_number("JE-", "journal_entries")
    eid = qrun("""INSERT INTO journal_entries (number,date,type,reference,narration,status,created_by)
                  VALUES (?,?,?,?,?,?,?)""",
               (number, date, jtype, ref, narration, status, created_by))
    for acc_name, partner, nar, dr, cr in lines:
        acc = qdf("SELECT id FROM accounts WHERE name=?", (acc_name,))
        acc_id = int(acc['id'].iloc[0]) if not acc.empty else None
        qrun("""INSERT INTO journal_lines (entry_id,account_id,account_name,partner,narration,debit,credit)
                VALUES (?,?,?,?,?,?,?)""", (eid, acc_id, acc_name, partner, nar, dr, cr))
    return eid

def update_account_balance(account_name, debit, credit):
    """Assets/Expenses increase with debit; Liabilities/Equity/Income increase with credit"""
    acc = qdf("SELECT id, category FROM accounts WHERE name=?", (account_name,))
    if acc.empty:
        return
    cat = acc['category'].iloc[0]
    if cat in ('Asset', 'Expense'):
        delta = debit - credit
    else:
        delta = credit - debit
    qrun("UPDATE accounts SET balance = balance + ? WHERE name=?", (delta, account_name))
