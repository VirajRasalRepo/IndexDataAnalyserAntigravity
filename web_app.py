from flask import Flask, render_template, jsonify, send_file
import mysql.connector
import datetime
import pandas as pd
import io

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "qwerty123456",
    "database": "analyzer_db"
}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/get_data')
def get_data_api():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
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

        cursor.close()
        conn.close()
        return jsonify({"data": processed_rows, "last_updated": datetime.datetime.now().strftime("%H:%M:%S")})
    except Exception as e:
        return jsonify({"data": [], "error": str(e)})


@app.route('/export_excel')
def export_excel():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Fetch data
        query = "SELECT * FROM NIFTY_OC_HISTORICAL ORDER BY Date DESC, Time DESC"
        cursor.execute(query)
        rows = cursor.fetchall()

        # Close connection immediately
        cursor.close()
        conn.close()

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
    except Exception as e:
        print(f"Export Error: {e}")
        return f"Error generating Excel: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)


if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)