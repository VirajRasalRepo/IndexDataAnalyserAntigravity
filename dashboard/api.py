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

# Indian Market Hours (IST)
MARKET_OPEN_TIME = 33300   # 9:15 AM in seconds (9*3600 + 15*60)
MARKET_CLOSE_TIME = 55800  # 3:30 PM in seconds (15*3600 + 30*60)
INTERVAL_SECONDS = 180     # 3 minutes


def is_trading_day(date_obj):
    """Check if a date is a trading day (Monday-Friday, excluding holidays)."""
    if isinstance(date_obj, str):
        date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
    elif isinstance(date_obj, datetime):
        date_obj = date_obj.date()

    # Check if weekend (Saturday=5, Sunday=6)
    if date_obj.weekday() >= 5:
        return False

    # TODO: Add Indian market holiday calendar check here if needed
    return True


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
                        SELECT india_vix_close, india_vix_ltp
                        FROM market_feed_realtime
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """)
                    vix_result = cursor.fetchone()
                    if vix_result and vix_result[0]:
                        vix_close = decimal_to_float(vix_result[0])
                        vix_ltp = decimal_to_float(vix_result[1]) if vix_result[1] else vix_close

                        # Calculate change percentage
                        change_pct = 0.0
                        if vix_close and vix_close > 0:
                            change_pct = ((vix_ltp - vix_close) / vix_close) * 100

                        vix_data = {
                            'value': vix_ltp,
                            'change_pct': round(change_pct, 2)
                        }
                except Exception as e:
                    # VIX data not available in database
                    logger.debug(f"VIX data not available: {e}")
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
            # Get option chain data - using subquery to get latest timestamp from market hours
            cursor.execute(f"""
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
                    WHERE TIME_TO_SEC(Time) >= {MARKET_OPEN_TIME} AND TIME_TO_SEC(Time) <= {MARKET_CLOSE_TIME}
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
        requested_date = request.args.get('date', None)  # Optional date parameter (YYYY-MM-DD)

        with DatabaseManager.get_cursor() as cursor:
            # Get date to use (either requested or latest)
            if requested_date:
                # Use requested date
                selected_date = requested_date
                logger.info(f"Using requested date: {selected_date}")
            else:
                # Get latest date with market hours data (9:15 AM - 3:30 PM IST)
                cursor.execute(f"""
                    SELECT DISTINCT Date
                    FROM nifty_oc_historical
                    WHERE TIME_TO_SEC(Time) >= {MARKET_OPEN_TIME} AND TIME_TO_SEC(Time) <= {MARKET_CLOSE_TIME}
                    ORDER BY Date DESC
                    LIMIT 1
                """)

                latest_date_row = cursor.fetchone()
                if not latest_date_row:
                    return jsonify({'error': 'No data available'}), 404

                selected_date = latest_date_row[0]

            latest_date = selected_date

            # Find timestamps closest to 9:15, 9:18, 9:21, etc. (3-minute intervals from 9:15 AM IST)
            # Using a single query with CASE statements for efficiency
            cursor.execute(f"""
                WITH target_times AS (
                    SELECT DISTINCT
                        FLOOR((TIME_TO_SEC(Time) - {MARKET_OPEN_TIME}) / {INTERVAL_SECONDS}) * {INTERVAL_SECONDS} + {MARKET_OPEN_TIME} as target_sec
                    FROM nifty_oc_historical
                    WHERE Date = %s
                        AND TIME_TO_SEC(Time) >= {MARKET_OPEN_TIME}
                        AND TIME_TO_SEC(Time) <= {MARKET_CLOSE_TIME}
                ),
                closest_times AS (
                    SELECT
                        t.target_sec,
                        (
                            SELECT TIME_TO_SEC(h.Time)
                            FROM nifty_oc_historical h
                            WHERE h.Date = %s
                                AND TIME_TO_SEC(h.Time) >= t.target_sec - 90
                                AND TIME_TO_SEC(h.Time) <= t.target_sec + 90
                            ORDER BY ABS(TIME_TO_SEC(h.Time) - t.target_sec) ASC
                            LIMIT 1
                        ) as actual_sec,
                        %s as date
                    FROM target_times t
                )
                SELECT target_sec, actual_sec, date
                FROM closest_times
                WHERE actual_sec IS NOT NULL
                ORDER BY target_sec ASC
            """, (latest_date, latest_date, latest_date))

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

            for target_sec, actual_time_sec, date in time_intervals:
                # Get data for the exact timestamp closest to target
                cursor.execute("""
                    SELECT
                        Strike_price,
                        ce_oi, ce_volume,
                        pe_oi, pe_volume
                    FROM nifty_oc_historical
                    WHERE Date = %s
                        AND TIME_TO_SEC(Time) = %s
                        AND Strike_price >= %s
                        AND Strike_price <= %s
                    ORDER BY Strike_price ASC
                """, (date, actual_time_sec, min_strike, max_strike))

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
                    'timestamp': format_time_delta(target_sec),
                    'actual_timestamp': format_time_delta(actual_time_sec),
                    'target_seconds': target_sec,
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


@app.route('/api/historical-data', methods=['GET'])
def get_historical_data():
    """Get historical option chain data for a specific date and time."""
    try:
        # Get query parameters
        date_str = request.args.get('date')  # Format: YYYY-MM-DD
        time_str = request.args.get('time')  # Format: HH:MM or HH:MM:SS
        strike_step = int(request.args.get('strike_step', 50))

        if not date_str or not time_str:
            return jsonify({'error': 'Date and time parameters required'}), 400

        # Check if trading day
        if not is_trading_day(date_str):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            return jsonify({
                'error': f'{date_obj.strftime("%A")} - Market closed (Weekend/Holiday)',
                'is_trading_day': False
            }), 400

        # Ensure time has seconds
        if len(time_str.split(':')) == 2:
            time_str += ':00'

        with DatabaseManager.get_cursor() as cursor:
            # Get data for the specific date and time
            cursor.execute("""
                SELECT
                    Strike_price,
                    Spot_price,
                    ce_oi, ce_volume, ce_IV, ce_delta, ce_gamma, ce_theta, ce_price, ce_vega, ce_signal,
                    pe_oi, pe_volume, pe_IV, pe_delta, pe_gamma, pe_theta, pe_price, pe_vega, pe_signal,
                    OI_Diff,
                    Date, Time
                FROM nifty_oc_historical
                WHERE Date = %s AND Time = %s
                ORDER BY Strike_price ASC
            """, (date_str, time_str))

            rows = cursor.fetchall()

            if not rows:
                return jsonify({'error': f'No data found for {date_str} at {time_str}'}), 404

            # Process data
            option_data = []
            spot_price = None
            latest_date = None
            latest_time = None

            for row in rows:
                # Get timestamp from first row
                if latest_date is None:
                    latest_date = row[21]  # Date column
                    latest_time = row[22]  # Time column
                if spot_price is None:
                    spot_price = decimal_to_float(row[1])

                strike = decimal_to_float(row[0])

                # Get OI change from previous record
                ce_oi_change = 0
                pe_oi_change = 0

                option_data.append({
                    'strike': strike,
                    'ce': {
                        'signal': row[10] or 'NEUTRAL',
                        'oi': decimal_to_float(row[2]) / 100000 if row[2] else 0,  # Lakhs
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
                        'oi': decimal_to_float(row[11]) / 100000 if row[11] else 0,  # Lakhs
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
                'date': decimal_to_float(latest_date),
                'time': format_time_delta(latest_time),
                'data': option_data
            })

    except Exception as e:
        logger.error(f"Error fetching historical data: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-full-day', methods=['GET'])
def export_full_day():
    """Export full day data as CSV."""
    try:
        date_str = request.args.get('date')  # Format: YYYY-MM-DD

        if not date_str:
            return jsonify({'error': 'Date parameter required'}), 400

        # Check if trading day
        if not is_trading_day(date_str):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            return jsonify({
                'error': f'{date_obj.strftime("%A")} - Market closed (Weekend/Holiday)'
            }), 400

        with DatabaseManager.get_cursor() as cursor:
            # Get all data for the day with 3-minute intervals (9:15 AM - 3:30 PM IST)
            cursor.execute(f"""
                WITH target_times AS (
                    SELECT DISTINCT
                        FLOOR((TIME_TO_SEC(Time) - {MARKET_OPEN_TIME}) / {INTERVAL_SECONDS}) * {INTERVAL_SECONDS} + {MARKET_OPEN_TIME} as target_sec
                    FROM nifty_oc_historical
                    WHERE Date = %s
                        AND TIME_TO_SEC(Time) >= {MARKET_OPEN_TIME}
                        AND TIME_TO_SEC(Time) <= {MARKET_CLOSE_TIME}
                ),
                closest_times AS (
                    SELECT
                        t.target_sec,
                        (
                            SELECT TIME_TO_SEC(h.Time)
                            FROM nifty_oc_historical h
                            WHERE h.Date = %s
                                AND TIME_TO_SEC(h.Time) >= t.target_sec - 90
                                AND TIME_TO_SEC(h.Time) <= t.target_sec + 90
                            ORDER BY ABS(TIME_TO_SEC(h.Time) - t.target_sec) ASC
                            LIMIT 1
                        ) as actual_sec
                    FROM target_times t
                )
                SELECT
                    h.Time,
                    h.Strike_price,
                    h.ce_oi, h.ce_volume, h.ce_IV, h.ce_delta, h.ce_price,
                    h.pe_oi, h.pe_volume, h.pe_IV, h.pe_delta, h.pe_price
                FROM nifty_oc_historical h
                INNER JOIN closest_times ct ON TIME_TO_SEC(h.Time) = ct.actual_sec
                WHERE h.Date = %s
                ORDER BY h.Time ASC, h.Strike_price ASC
            """, (date_str, date_str, date_str))

            rows = cursor.fetchall()

            if not rows:
                return jsonify({'error': 'No data found for this date'}), 404

            # Build CSV response
            csv_lines = []
            csv_lines.append('Time,Strike,CE_OI(L),CE_Volume(K),CE_IV,CE_Delta,CE_LTP,PE_LTP,PE_Delta,PE_IV,PE_Volume(K),PE_OI(L)')

            for row in rows:
                time = format_time_delta(decimal_to_float(row[0]))
                strike = decimal_to_float(row[1])
                ce_oi = decimal_to_float(row[2]) / 100000 if row[2] else 0  # Lakhs
                ce_vol = decimal_to_float(row[3]) / 1000 if row[3] else 0  # Thousands
                ce_iv = decimal_to_float(row[4]) if row[4] else 0
                ce_delta = decimal_to_float(row[5]) if row[5] else 0
                ce_ltp = decimal_to_float(row[6]) if row[6] else 0
                pe_oi = decimal_to_float(row[7]) / 100000 if row[7] else 0  # Lakhs
                pe_vol = decimal_to_float(row[8]) / 1000 if row[8] else 0  # Thousands
                pe_iv = decimal_to_float(row[9]) if row[9] else 0
                pe_delta = decimal_to_float(row[10]) if row[10] else 0
                pe_ltp = decimal_to_float(row[11]) if row[11] else 0

                csv_lines.append(f'{time},{strike:.0f},{ce_oi:.2f},{ce_vol:.0f},{ce_iv:.2f},{ce_delta:.2f},{ce_ltp:.2f},{pe_ltp:.2f},{pe_delta:.2f},{pe_iv:.2f},{pe_vol:.0f},{pe_oi:.2f}')

            csv_content = '\n'.join(csv_lines)

            # Return as downloadable CSV
            from flask import make_response
            response = make_response(csv_content)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=OI_FullDay_{date_str}.csv'
            return response

    except Exception as e:
        logger.error(f"Error exporting full day: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/available-dates', methods=['GET'])
def get_available_dates():
    """Get list of dates with available data."""
    try:
        with DatabaseManager.get_cursor() as cursor:
            # Get distinct dates with market hours data
            cursor.execute(f"""
                SELECT DISTINCT Date
                FROM nifty_oc_historical
                WHERE TIME_TO_SEC(Time) >= {MARKET_OPEN_TIME}
                  AND TIME_TO_SEC(Time) <= {MARKET_CLOSE_TIME}
                ORDER BY Date DESC
                LIMIT 30
            """)

            dates = [str(row[0]) for row in cursor.fetchall()]
            return jsonify(dates)

    except Exception as e:
        logger.error(f"Error fetching available dates: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/is-trading-day', methods=['GET'])
def check_trading_day():
    """Check if a specific date is a trading day."""
    try:
        date_str = request.args.get('date')  # Format: YYYY-MM-DD

        if not date_str:
            return jsonify({'error': 'Date parameter required'}), 400

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        is_trading = is_trading_day(date_obj)

        return jsonify({
            'date': date_str,
            'is_trading_day': is_trading,
            'day_of_week': date_obj.strftime('%A'),
            'message': 'Trading day' if is_trading else 'Weekend/Holiday - Market closed'
        })

    except Exception as e:
        logger.error(f"Error checking trading day: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/available-times', methods=['GET'])
def get_available_times():
    """Get available timestamps for a specific date with 3-minute intervals (same as index.html)."""
    try:
        date_str = request.args.get('date')  # Format: YYYY-MM-DD

        if not date_str:
            return jsonify({'error': 'Date parameter required'}), 400

        # Check if trading day
        if not is_trading_day(date_str):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            return jsonify({
                'warning': f'{date_obj.strftime("%A")} - Market closed (Weekend/Holiday)',
                'times': []
            })

        with DatabaseManager.get_cursor() as cursor:
            # Get 3-minute interval timestamps (same logic as /api/oi-difference-live)
            # 9:15 AM - 3:30 PM IST
            cursor.execute(f"""
                WITH target_times AS (
                    SELECT DISTINCT
                        FLOOR((TIME_TO_SEC(Time) - {MARKET_OPEN_TIME}) / {INTERVAL_SECONDS}) * {INTERVAL_SECONDS} + {MARKET_OPEN_TIME} as target_sec
                    FROM nifty_oc_historical
                    WHERE Date = %s
                        AND TIME_TO_SEC(Time) >= {MARKET_OPEN_TIME}
                        AND TIME_TO_SEC(Time) <= {MARKET_CLOSE_TIME}
                ),
                closest_times AS (
                    SELECT
                        t.target_sec,
                        (
                            SELECT TIME_TO_SEC(h.Time)
                            FROM nifty_oc_historical h
                            WHERE h.Date = %s
                                AND TIME_TO_SEC(h.Time) >= t.target_sec - 90
                                AND TIME_TO_SEC(h.Time) <= t.target_sec + 90
                            ORDER BY ABS(TIME_TO_SEC(h.Time) - t.target_sec) ASC
                            LIMIT 1
                        ) as actual_sec
                    FROM target_times t
                )
                SELECT actual_sec
                FROM closest_times
                WHERE actual_sec IS NOT NULL
                ORDER BY actual_sec ASC
            """, (date_str, date_str))

            times = [format_time_delta(row[0]) for row in cursor.fetchall()]
            return jsonify(times)

    except Exception as e:
        logger.error(f"Error fetching available times: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    logger.info("Starting OI Dashboard API server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
