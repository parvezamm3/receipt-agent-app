from flask import Flask, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import sqlite3, os, time

app = Flask(__name__)
CORS(app)

BASE = os.path.dirname(__file__)                  # Currently backend/api
ROOT = os.path.abspath(os.path.join(BASE, os.pardir, os.pardir))
DB = os.path.join(ROOT, 'receipts.db')
SUCC_DIR = os.path.join(ROOT, 'success_pdfs')
FAIL_DIR = os.path.join(ROOT, 'error_pdfs')


def query_db(q, args=()):
    con = sqlite3.connect(os.path.abspath(DB)); cur = con.cursor()
    cur.execute(q, args); rows = cur.fetchall(); con.close()
    return rows

def table_exists(con, name: str) -> bool:
    cur = con.cursor()
    cur.execute(
        "SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    exists = cur.fetchone()[0] == 1
    cur.close()
    return exists

@app.route("/api/stream")
def stream():
    """EventSource endpoint – emits 'update' whenever the DB changes."""
    @stream_with_context
    def event_stream():
        conn = sqlite3.connect(os.path.abspath(DB))
        cur  = conn.cursor()
        cur.execute("PRAGMA data_version")
        last_version = cur.fetchone()[0]

        while True:
            time.sleep(2)                            # poll every 2 s
            cur.execute("PRAGMA data_version")
            ver = cur.fetchone()[0]
            if ver != last_version:
                last_version = ver
                yield "event: update\ndata: {}\n\n"  # empty JSON payload

            # keep‑alive every 30 s so proxies don’t close idle stream
            if int(time.time()) % 30 == 0:
                yield ": keep-alive\n\n"

    # correct SSE MIME type
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/api/receipts')
def list_receipts():
    con = sqlite3.connect(DB)
    success_list = []
    failed_list = []

    # check for successful_receipts table
    if table_exists(con, "successful_receipts"):
        rows = con.execute(
            "SELECT generated_receipt_id, date, amount, vendor_name, category, evaluation_score "
            "FROM successful_receipts"
        ).fetchall()
        success_list = [
            {"id": r[0], "date": r[1], "amount":r[2], "vendor_name":r[3], "category":r[4], "score": r[5]}
            for r in rows
        ]

    # check for failed_receipts table
    if table_exists(con, "failed_receipts"):
        rows = con.execute(
            "SELECT generated_receipt_id, original_pdf_filename, error_message, evaluation_score "
            "FROM failed_receipts"
        ).fetchall()
        failed_list = [
            {"id": r[0], "filename": r[1], "error": r[2], "score": r[3]}
            for r in rows
        ]

    con.close()
    return jsonify({
        "successful": success_list,
        "failed": failed_list,
    })

@app.route('/api/receipt/<rid>')
def receipt_detail(rid):
    row = query_db("SELECT *, generated_receipt_id FROM successful_receipts WHERE generated_receipt_id=?", (rid,))
    folder = SUCC_DIR
    if not row:
        row = query_db("SELECT *, generated_receipt_id FROM failed_receipts WHERE generated_receipt_id=?", (rid,))
        folder = FAIL_DIR
    if not row:
        return jsonify({'error': 'not found'}), 404

    conn = sqlite3.connect(os.path.abspath(DB))
    cur = conn.cursor()
    cols_info = cur.execute(
        'PRAGMA table_info(successful_receipts)' if folder == SUCC_DIR else
        'PRAGMA table_info(failed_receipts)'
    ).fetchall()
    cols = [d[1] for d in cols_info]
    record = dict(zip(cols, row[0]))
    return jsonify({
      **record,
      'pdf_url': f'/api/receipt-file/{rid}/{ "success" if folder==SUCC_DIR else "failed"}'
    })

@app.route('/api/receipt-file/<rid>/<typ>')
def receipt_file(rid, typ):
    folder = SUCC_DIR if typ=='success' else FAIL_DIR
    return send_from_directory(folder, f"{rid}.pdf")


@app.route('/api/debug')
def debug_db():
    import sqlite3, os
    # DB = os.path.join(os.path.dirname(__file__), '../receipts.db')
    exists = os.path.isfile(DB)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return jsonify({"db_path": DB, "exists": exists, "tables": tables})
