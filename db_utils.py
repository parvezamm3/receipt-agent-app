"""Database helpers for the receipt‑processing pipeline.
   All functions **open and close** their *own* connection – this makes the
   module thread‑safe and avoids leaving connections open (the cause of most
   `WinError 32` locking problems on Windows).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

__all__ = [
    "init_schema",
    "receipt_exists",
    "insert_success_receipt",
    "insert_failed_receipt",
]

DB_PATH = Path(__file__).with_name("receipts.db")

# ──────────────────────────────────────────────────────────────────────────────
# Connection helper ─ a **context‑manager** that always closes the handle.
# ----------------------------------------------------------------------------

def _connect():
    """Return a connection with WAL mode enabled for concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)  # autocommit
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

# ──────────────────────────────────────────────────────────────────────────────
# Schema
# ----------------------------------------------------------------------------

def init_schema() -> None:
    """Create the tables once if they don’t yet exist."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS successful_receipts (
                generated_receipt_id TEXT PRIMARY KEY,
                original_pdf_filename TEXT NOT NULL,
                date TEXT,
                amount TEXT,
                tax TEXT,
                tax_rate TEXT,
                vendor_name TEXT,
                vendor_address TEXT,
                vendor_phone TEXT,
                registration_number TEXT,
                description TEXT,
                category TEXT,
                original_extracted_data TEXT,
                feedback TEXT,
                evaluation_score INTEGER,
                processed_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS failed_receipts (
                generated_receipt_id TEXT PRIMARY KEY,
                original_pdf_filename TEXT NOT NULL,
                date TEXT,
                amount TEXT,
                tax TEXT,
                tax_rate TEXT,
                vendor_name TEXT,
                vendor_address TEXT,
                vendor_phone TEXT,
                registration_number TEXT,
                description TEXT,
                category TEXT,
                error_message TEXT,
                original_extracted_data TEXT,
                feedback TEXT,
                evaluation_score INTEGER,
                processed_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

# Call once at import time so that other helpers can assume the schema exists.
init_schema()

# ──────────────────────────────────────────────────────────────────────────────
# ID helper
# ----------------------------------------------------------------------------

def _next_receipt_id(cur: sqlite3.Cursor, date_yymmdd: str, table: str) -> str:
    cur.execute(
        f"""SELECT generated_receipt_id FROM {table}
            WHERE generated_receipt_id LIKE ? ORDER BY 1 DESC LIMIT 1""",
        (f"{date_yymmdd}_%",),
    )
    last = cur.fetchone()
    next_counter = 1
    if last:
        try:
            next_counter = int(last[0].split("_")[-1]) + 1
        except (ValueError, IndexError):
            pass
    return f"{date_yymmdd}_{next_counter:03d}"

# ──────────────────────────────────────────────────────────────────────────────
# Public helpers
# ----------------------------------------------------------------------------

def receipt_exists(pdf_name: str) -> bool:
    """Return *True* if we have already processed *pdf_name* successfully."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM successful_receipts WHERE original_pdf_filename = ? LIMIT 1",
            (pdf_name,),
        )
        return cur.fetchone() is not None

def insert_success_receipt(pdf_name: str, extracted: Dict[str, Any], feedback: str, score: int) -> str:
    """Insert a successfully processed receipt and return its generated ID."""
    date_raw = extracted.get("日付")
    try:
        date_yymmdd = datetime.strptime(date_raw, "%Y%m%d").strftime("%y%m%d") if date_raw else datetime.now().strftime("%y%m%d")
    except Exception:
        date_yymmdd = datetime.now().strftime("%y%m%d")

    with _connect() as conn:
        cur = conn.cursor()
        gen_id = _next_receipt_id(cur, date_yymmdd, "successful_receipts")
        cur.execute(
            """INSERT INTO successful_receipts (
                generated_receipt_id, original_pdf_filename, date, amount, tax, tax_rate, 
                vendor_name, vendor_address, vendor_phone, registration_number, description,
                category, original_extracted_data, feedback, evaluation_score
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                gen_id,
                pdf_name,
                extracted.get("日付"),
                extracted.get("金額"),
                extracted.get("消費税"),
                extracted.get("消費税率"),
                (extracted.get("相手先") or {}).get("名前"),
                (extracted.get("相手先") or {}).get("住所"),
                (extracted.get("相手先") or {}).get("電話番号"),
                extracted.get("登録番号"),
                json_dumps(extracted.get("摘要")),
                extracted.get("カテゴリ"),
                json_dumps(extracted, ensure_ascii=False),
                feedback,
                score,
            ),
        )
        return gen_id

def insert_failed_receipt(pdf_name: str, error_msg: str, extracted: Dict[str, Any], feedback: str | None, score: int | None) -> str:
    date_raw = extracted.get("日付")
    try:
        date_yymmdd = datetime.strptime(date_raw, "%Y%m%d").strftime("%y%m%d") if date_raw else datetime.now().strftime("%y%m%d")
    except Exception:
        date_yymmdd = datetime.now().strftime("%y%m%d")
    with _connect() as conn:
        cur = conn.cursor()
        gen_id = _next_receipt_id(cur, date_yymmdd, "failed_receipts")
        cur.execute(
            """INSERT INTO failed_receipts (
                generated_receipt_id, original_pdf_filename, error_message,
                date, amount, tax, tax_rate, 
                vendor_name, vendor_address, vendor_phone, registration_number, description,
                category, original_extracted_data, feedback, evaluation_score
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                gen_id, 
                pdf_name, 
                error_msg, 
                extracted.get("日付", ''),
                extracted.get("金額", ''),
                extracted.get("消費税", ''),
                extracted.get("消費税率", ''),
                (extracted.get("相手先") or {}).get("名前", ''),
                (extracted.get("相手先") or {}).get("住所", ''),
                (extracted.get("相手先") or {}).get("電話番号", ''),
                extracted.get("登録番号", ''),
                json_dumps(extracted.get("摘要", '')),
                extracted.get("カテゴリ", ''),
                json_dumps(extracted, ensure_ascii=False),
                feedback, 
                score
            ),
        )
        return gen_id

# local helper because we can’t import json at top (circular in tools)
import json
json_dumps = json.dumps