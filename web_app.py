from flask import Flask, render_template, jsonify, send_file
import mysql.connector
import datetime
import logging
from contextlib import contextmanager
import pandas as pd
import io

from core.config import Config

app = Flask(__name__)

# DB credentials loaded from .env via core.config (no hardcoded secrets)
DB_CONFIG = Config.get_db_config()

logger = logging.getLogger(__name__)


@contextmanager
def get_db_cursor(dictionary=True):
    """Context manager that guarantees connection + cursor cleanup on any exit path."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
    finally:
        try:
            cursor.close()
        finally:
            conn.close()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/get_data')
def get_data_api():
    try:
        with get_db_cursor() as cursor:
            # Fetch latest data for UI
            query = "SELECT * FROM NIFTY_OC_HISTORICAL ORDER BY Date DESC, Time DESC, Strike_price DESC LIMIT 2000"
            cursor.execute(query)
            rows = cursor.fetchall()

        processed_rows = []
        for row in rows:
            new_row = {}
            for key, value in row.items():
                clean_key = key.lower()
                # Ensure date/time objects are strings for JSON
                if isinstance(value, (datetime.timedelta, datetime.date)):
                    new_row[clean_key] = str(value)
                else:
                    new_row[clean_key] = value
            processed_rows.append(new_row)

        return jsonify({"data": processed_rows, "last_updated": datetime.datetime.now().strftime("%H:%M:%S")})
    except Exception:
        logger.exception("get_data_api failed")
        return jsonify({"data": [], "error": "Failed to load data"}), 500


@app.route('/export_excel')
def export_excel():
    try:
        with get_db_cursor() as cursor:
            # Fetch data
            query = "SELECT * FROM NIFTY_OC_HISTORICAL ORDER BY Date DESC, Time DESC"
            cursor.execute(query)
            rows = cursor.fetchall()

        if not rows:
            return "No data found to export", 404

        # Create DataFrame from the list of dictionaries
        df = pd.DataFrame(rows)

        # Create Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='NiftyData')

        output.seek(0)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"Nifty_Data_{timestamp}.xlsx"
        )
    except Exception:
        logger.exception("export_excel failed")
        return "Error generating Excel", 500


if __name__ == '__main__':
    # debug driven by Config.DEBUG (.env) — never hardcode True (Werkzeug debugger = RCE risk)
    app.run(debug=Config.DEBUG, port=5000, use_reloader=False)