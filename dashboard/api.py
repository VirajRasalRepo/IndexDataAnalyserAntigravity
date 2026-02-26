"""
OI Data Dashboard API
Provides REST endpoints for fetching live Option Chain data from the database.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, date, time as dt_time
from decimal import Decimal
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import DatabaseManager
from core.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Initialize database pool
DatabaseManager.initialize_pool(pool_size=5)


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, dt_time):
        return obj.strftime('%H:%M:%S')
    return obj


def format_time_delta(td):
    """Format timedelta as HH:MM:SS."""
    if isinstance(td, int):
        # Already seconds
        total_seconds = td
    else:
        # timedelta object
        total_seconds = int(td.total_seconds())

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/api/spot-price', methods=['GET'])
def get_spot_price():
    """Get current NIFTY spot price and VIX."""
    try:
        with DatabaseManager.get_cursor() as cursor:
            # Get latest spot price from option chain data
            cursor.execute("""
                SELECT Spot_price, Date, Time
                FROM nifty_oc_historical
                ORDER BY Date DESC, Time DESC
                LIMIT 1
            """)

            result = cursor.fetchone()
            if result:
                spot_price = decimal_to_float(result[0])
                data_date = decimal_to_float(result[1])
                data_time = decimal_to_float(result[2])

                # Calculate percentage change from previous day's close
                cursor.execute("""
                    SELECT Spot_price
                    FROM nifty_oc_historical
                    WHERE Date < %s
                    ORDER BY Date DESC, Time DESC
                    LIMIT 1
                """, (result[1],))

                prev_result = cursor.fetchone()
                pct_change = 0.0
                if prev_result and prev_result[0]:
                    prev_close = decimal_to_float(prev_result[0])
                    pct_change = ((spot_price - prev_close) / prev_close) * 100

                # Try to fetch VIX from market_feed_realtime table
                vix_data = None
                try:
                    cursor.execute("""
                        SELECT close_price
                        FROM market_feed_realtime
                        WHERE symbol = 'INDIA VIX'
                        ORDER BY last_update_time DESC
                        LIMIT 1
                    """)
                    vix_result = cursor.fetchone()
                    if vix_result and vix_result[0]:
                        vix_value = decimal_to_float(vix_result[0])
                        vix_data = {
                            'value': vix_value,
                            'change_pct': 0.0  # Can be calculated if historical VIX data exists
                        }
                except Exception:
                    # VIX data not available in database
                    pass

                response = {
                    'nifty': {
                        'value': spot_price,
                        'change_pct': round(pct_change, 2),
                        'timestamp': f"{data_date} {format_time_delta(data_time)}"
                    }
                }

                if vix_data:
                    response['vix'] = vix_data

                return jsonify(response)
            else:
                return jsonify({'error': 'No data available'}), 404

    except Exception as e:
        logger.error(f"Error fetching spot price: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/option-chain', methods=['GET'])
def get_option_chain():
    """Get option chain data with filters."""
    try:
        # Get query parameters
        symbol = request.args.get('symbol', 'NIFTY')
        expiry_date = request.args.get('expiry', None)
        strike_step = int(request.args.get('strike_step', 50))

        with DatabaseManager.get_cursor() as cursor:
            # Get option chain data - using subquery to get latest timestamp
            cursor.execute("""
                SELECT
                    Strike_price,
                    Spot_price,
                    ce_oi, ce_volume, ce_IV, ce_delta, ce_gamma, ce_theta, ce_price, ce_vega, ce_signal,
                    pe_oi, pe_volume, pe_IV, pe_delta, pe_gamma, pe_theta, pe_price, pe_vega, pe_signal,
                    OI_Diff,
                    Date, Time
                FROM nifty_oc_historical
                WHERE (Date, Time) = (
                    SELECT Date, Time
                    FROM nifty_oc_historical
                    ORDER BY Date DESC, Time DESC
                    LIMIT 1
                )
                ORDER BY Strike_price ASC
            """)

            rows = cursor.fetchall()

            if not rows:
                return jsonify({'error': 'No data for latest timestamp'}), 404

            # Process data
            option_data = []
            spot_price = None
            latest_date = None
            latest_time = None

            for row in rows:
                # Get timestamp from first row
                if latest_date is None:
                    latest_date = row[21]  # Date column (index 21)
                    latest_time = row[22]  # Time column (index 22)
                if spot_price is None:
                    spot_price = decimal_to_float(row[1])

                strike = decimal_to_float(row[0])

                # Calculate OI change (difference from previous record)
                # TODO: Implement proper OI change calculation
                ce_oi_change = 0
                pe_oi_change = 0

                option_data.append({
                    'strike': strike,
                    'ce': {
                        'signal': row[10] or 'NEUTRAL',
                        'oi': decimal_to_float(row[2]) / 100000 if row[2] else 0,  # Convert to lakhs
                        'oi_change': ce_oi_change,
                        'iv': decimal_to_float(row[4]) if row[4] else 0,
                        'ltp': decimal_to_float(row[8]) if row[8] else 0,
                        'delta': decimal_to_float(row[5]) if row[5] else 0,
                        'volume': decimal_to_float(row[3]) if row[3] else 0,
                        'gamma': decimal_to_float(row[6]) if row[6] else 0,
                        'theta': decimal_to_float(row[7]) if row[7] else 0,
                        'vega': decimal_to_float(row[9]) if row[9] else 0
                    },
                    'pe': {
                        'signal': row[19] or 'NEUTRAL',
                        'oi': decimal_to_float(row[11]) / 100000 if row[11] else 0,  # Convert to lakhs
                        'oi_change': pe_oi_change,
                        'iv': decimal_to_float(row[13]) if row[13] else 0,
                        'ltp': decimal_to_float(row[17]) if row[17] else 0,
                        'delta': decimal_to_float(row[14]) if row[14] else 0,
                        'volume': decimal_to_float(row[12]) if row[12] else 0,
                        'gamma': decimal_to_float(row[15]) if row[15] else 0,
                        'theta': decimal_to_float(row[16]) if row[16] else 0,
                        'vega': decimal_to_float(row[18]) if row[18] else 0
                    },
                    'is_atm': abs(strike - spot_price) < (strike_step / 2) if spot_price else False
                })

            return jsonify({
                'spot_price': spot_price,
                'timestamp': f"{decimal_to_float(latest_date)} {format_time_delta(latest_time)}",
                'data': option_data
            })

    except Exception as e:
        logger.error(f"Error fetching option chain: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/expiry-dates', methods=['GET'])
def get_expiry_dates():
    """Get available expiry dates from database."""
    try:
        with DatabaseManager.get_cursor() as cursor:
            # Get unique dates from the database
            cursor.execute("""
                SELECT DISTINCT Date
                FROM nifty_oc_historical
                ORDER BY Date DESC
                LIMIT 10
            """)

            dates = [decimal_to_float(row[0]) for row in cursor.fetchall()]
            return jsonify(dates)

    except Exception as e:
        logger.error(f"Error fetching expiry dates: {e}", exc_info=True)
        return jsonify([])  # Return empty array on error


@app.route('/api/oi-difference-live', methods=['GET'])
def get_oi_difference_live():
    """Get OI difference time-series data for entire day with 3-minute intervals."""
    try:
        # Get query parameters
        strike_count = int(request.args.get('strike_count', 10))
        interval_minutes = 3  # Fixed 3-minute intervals

        with DatabaseManager.get_cursor() as cursor:
            # Get all timestamps for today, grouped by 3-minute intervals
            cursor.execute("""
                SELECT DISTINCT Date
                FROM nifty_oc_historical
                ORDER BY Date DESC
                LIMIT 1
            """)

            latest_date_row = cursor.fetchone()
            if not latest_date_row:
                return jsonify({'error': 'No data available'}), 404

            latest_date = latest_date_row[0]

            # Get unique timestamps for the day, rounded to 3-minute intervals
            cursor.execute("""
                SELECT DISTINCT
                    FLOOR(TIME_TO_SEC(Time) / 180) * 180 as interval_seconds,
                    Date
                FROM nifty_oc_historical
                WHERE Date = %s
                ORDER BY interval_seconds ASC
            """, (latest_date,))

            time_intervals = cursor.fetchall()

            if not time_intervals:
                return jsonify({'error': 'No data for today'}), 404

            # Get spot price from latest data
            cursor.execute("""
                SELECT Spot_price
                FROM nifty_oc_historical
                WHERE Date = %s
                ORDER BY Time DESC
                LIMIT 1
            """, (latest_date,))

            spot_price = decimal_to_float(cursor.fetchone()[0])

            # Get strike prices around ATM
            strike_step = 50
            atm_strike = (spot_price // strike_step) * strike_step
            min_strike = atm_strike - (strike_count // 2) * strike_step
            max_strike = atm_strike + (strike_count // 2) * strike_step

            # Fetch time-series data for all intervals
            time_series_data = []

            for interval_sec, date in time_intervals:
                # Get data for this specific interval
                # Find the latest record within this 3-minute window
                interval_start = interval_sec
                interval_end = interval_sec + 180

                cursor.execute("""
                    SELECT
                        h1.Strike_price,
                        h1.ce_oi, h1.ce_volume,
                        h1.pe_oi, h1.pe_volume
                    FROM nifty_oc_historical h1
                    INNER JOIN (
                        SELECT Strike_price, MAX(Time) as max_time
                        FROM nifty_oc_historical
                        WHERE Date = %s
                            AND TIME_TO_SEC(Time) >= %s
                            AND TIME_TO_SEC(Time) < %s
                            AND Strike_price >= %s
                            AND Strike_price <= %s
                        GROUP BY Strike_price
                    ) h2 ON h1.Strike_price = h2.Strike_price AND h1.Time = h2.max_time
                    WHERE h1.Date = %s
                    ORDER BY h1.Strike_price ASC
                """, (date, interval_start, interval_end, min_strike, max_strike, date))

                interval_data = {}
                for row in cursor.fetchall():
                    strike = decimal_to_float(row[0])
                    interval_data[strike] = {
                        'ce_oi': decimal_to_float(row[1]) if row[1] else 0,
                        'ce_vol': decimal_to_float(row[2]) if row[2] else 0,
                        'pe_oi': decimal_to_float(row[3]) if row[3] else 0,
                        'pe_vol': decimal_to_float(row[4]) if row[4] else 0,
                    }

                time_series_data.append({
                    'timestamp': format_time_delta(interval_sec),
                    'data': interval_data
                })

            # Calculate differences
            for i in range(len(time_series_data)):
                if i == 0:
                    # First interval - no previous data
                    for strike in time_series_data[i]['data']:
                        time_series_data[i]['data'][strike]['ce_oi_diff'] = 0
                        time_series_data[i]['data'][strike]['ce_vol_diff'] = 0
                        time_series_data[i]['data'][strike]['pe_oi_diff'] = 0
                        time_series_data[i]['data'][strike]['pe_vol_diff'] = 0
                else:
                    # Calculate difference from previous interval
                    prev_data = time_series_data[i-1]['data']
                    curr_data = time_series_data[i]['data']

                    for strike in curr_data:
                        if strike in prev_data:
                            curr_data[strike]['ce_oi_diff'] = curr_data[strike]['ce_oi'] - prev_data[strike]['ce_oi']
                            curr_data[strike]['ce_vol_diff'] = curr_data[strike]['ce_vol'] - prev_data[strike]['ce_vol']
                            curr_data[strike]['pe_oi_diff'] = curr_data[strike]['pe_oi'] - prev_data[strike]['pe_oi']
                            curr_data[strike]['pe_vol_diff'] = curr_data[strike]['pe_vol'] - prev_data[strike]['pe_vol']
                        else:
                            curr_data[strike]['ce_oi_diff'] = 0
                            curr_data[strike]['ce_vol_diff'] = 0
                            curr_data[strike]['pe_oi_diff'] = 0
                            curr_data[strike]['pe_vol_diff'] = 0

            # Get list of strikes
            strikes = sorted([s for s in time_series_data[0]['data'].keys()]) if time_series_data else []

            return jsonify({
                'spot_price': spot_price,
                'atm_strike': atm_strike,
                'strikes': strikes,
                'time_series': time_series_data,
                'date': decimal_to_float(latest_date)
            })

    except Exception as e:
        logger.error(f"Error fetching OI difference live: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    logger.info("Starting OI Dashboard API server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
