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
from core.greeks_processor import process_greeks_from_db, calc_iv_rank

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

    # Check if market holiday
    date_str = date_obj.strftime('%Y-%m-%d')
    if date_str in Config.MARKET_HOLIDAYS:
        return False

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
    """Get list of dates with available data (only trading days with data in market hours)."""
    try:
        with DatabaseManager.get_cursor() as cursor:
            # Get distinct dates with data in market hours only
            cursor.execute(f"""
                SELECT DISTINCT Date
                FROM nifty_oc_historical
                WHERE ce_oi IS NOT NULL
                  AND TIME_TO_SEC(Time) >= {MARKET_OPEN_TIME}
                  AND TIME_TO_SEC(Time) <= {MARKET_CLOSE_TIME}
                ORDER BY Date DESC
                LIMIT 90
            """)

            all_dates = [str(row[0]) for row in cursor.fetchall()]

            # Filter to only include trading days (exclude weekends and holidays)
            trading_dates = [date_str for date_str in all_dates if is_trading_day(date_str)]

            return jsonify({
                'status': 'success',
                'dates': trading_dates,
                'count': len(trading_dates)
            })

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

        # Handle missing or invalid date parameter
        if not date_str or date_str == 'null' or date_str == 'undefined':
            return jsonify({'error': 'Valid date parameter required'}), 400

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


@app.route('/api/credentials', methods=['GET'])
def get_credentials():
    """Get current API credentials from .env file."""
    try:
        env_path = Path(__file__).parent.parent / '.env'

        if not env_path.exists():
            return jsonify({
                'client_id': '',
                'access_token': ''
            })

        # Read .env file
        with open(env_path, 'r') as f:
            lines = f.readlines()

        client_id = ''
        access_token = ''

        for line in lines:
            line = line.strip()
            if line.startswith('DHAN_CLIENT_ID='):
                client_id = line.split('=', 1)[1]
            elif line.startswith('DHAN_ACCESS_TOKEN='):
                access_token = line.split('=', 1)[1]

        return jsonify({
            'client_id': client_id,
            'access_token': access_token
        })

    except Exception as e:
        logger.error(f"Error reading credentials: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/credentials', methods=['POST'])
def update_credentials():
    """Update API credentials in .env file."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        client_id = data.get('client_id', '').strip()
        access_token = data.get('access_token', '').strip()

        if not client_id or not access_token:
            return jsonify({'error': 'Both client_id and access_token are required'}), 400

        env_path = Path(__file__).parent.parent / '.env'

        # Read existing .env file
        if env_path.exists():
            with open(env_path, 'r') as f:
                lines = f.readlines()
        else:
            lines = []

        # Update credentials
        updated_lines = []
        client_id_updated = False
        access_token_updated = False

        for line in lines:
            if line.strip().startswith('DHAN_CLIENT_ID='):
                updated_lines.append(f'DHAN_CLIENT_ID={client_id}\n')
                client_id_updated = True
            elif line.strip().startswith('DHAN_ACCESS_TOKEN='):
                updated_lines.append(f'DHAN_ACCESS_TOKEN={access_token}\n')
                access_token_updated = True
            else:
                updated_lines.append(line)

        # Add credentials if they don't exist
        if not client_id_updated:
            updated_lines.insert(0, f'DHAN_CLIENT_ID={client_id}\n')
        if not access_token_updated:
            updated_lines.insert(1, f'DHAN_ACCESS_TOKEN={access_token}\n')

        # Write back to .env file
        with open(env_path, 'w') as f:
            f.writelines(updated_lines)

        logger.info("API credentials updated successfully")

        return jsonify({
            'success': True,
            'message': 'Credentials updated successfully. Please restart main.py to apply changes.'
        })

    except Exception as e:
        logger.error(f"Error updating credentials: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# GREEKS ANALYTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

# In-memory cache for Greeks data
_greeks_cache = {
    'data': None,
    'timestamp': None,
    'prev_snapshot': {}  # For velocity calculation
}


@app.route('/api/greeks-pro', methods=['GET'])
def greeks_pro():
    """
    Main Greeks endpoint - returns comprehensive Greeks analytics.

    Query Parameters:
        date (optional): Date in YYYY-MM-DD format (default: today)
        time (optional): Time in HH:MM:SS format (default: latest for date)

    Returns:
        JSON with:
        - spot, dte, vix, vix_change_pct, expiry
        - trend_intensity (market bias, delta flows)
        - pcr_divergence
        - ce_top5, pe_top5 (best efficiency strikes)
        - ce_all, pe_all (top 10 each)
        - lotto_strikes (Scalp + Gamma Blast)
        - alerts (Theta Trap, Gamma Blast, etc.)
        - entry_signals (ENTRY/EXIT/CAUTION)
        - portfolio (net delta from User_ table)
        - iv_rank
    """
    try:
        # Get date and time parameters
        target_date = request.args.get('date', None)
        target_time = request.args.get('time', None)

        with DatabaseManager.get_cursor() as cursor:
            # Build query based on parameters
            if target_date and target_time:
                # Specific date and time
                query = """
                    SELECT *
                    FROM nifty_oc_historical
                    WHERE Date = %s AND Time = %s
                """
                cursor.execute(query, (target_date, target_time))
            elif target_date:
                # Latest time for specific date
                query = """
                    SELECT *
                    FROM nifty_oc_historical
                    WHERE Date = %s AND Time = (
                        SELECT MAX(Time) FROM nifty_oc_historical WHERE Date = %s
                    )
                """
                cursor.execute(query, (target_date, target_date))
            else:
                # Latest data for today (default)
                query = """
                    SELECT *
                    FROM nifty_oc_historical
                    WHERE Date = CURDATE() AND Time = (
                        SELECT MAX(Time) FROM nifty_oc_historical WHERE Date = CURDATE()
                    )
                """
                cursor.execute(query)

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            if not rows:
                date_msg = f" for {target_date}" if target_date else " for today"
                return jsonify({'status': 'error', 'message': f'No data available{date_msg}'}), 404

            db_rows = [dict(zip(columns, row)) for row in rows]

            # Get spot price
            spot = decimal_to_float(db_rows[0].get('Spot_price', 24500.0))

            # Get VIX (current and previous)
            cursor.execute("""
                SELECT india_vix_ltp
                FROM market_feed_realtime
                ORDER BY timestamp DESC LIMIT 2
            """)
            vix_rows = cursor.fetchall()
            vix_current = decimal_to_float(vix_rows[0][0]) if vix_rows else 14.0
            vix_prev = decimal_to_float(vix_rows[1][0]) if len(vix_rows) > 1 else vix_current

            # Calculate PCR
            cursor.execute("""
                SELECT
                    SUM(pe_oi) as pe_oi_total,
                    SUM(ce_oi) as ce_oi_total
                FROM nifty_oc_historical
                WHERE Date = CURDATE() AND Time = (
                    SELECT MAX(Time) FROM nifty_oc_historical WHERE Date = CURDATE()
                )
            """)
            pcr_row = cursor.fetchone()
            pe_oi = decimal_to_float(pcr_row[0] or 1)
            ce_oi = decimal_to_float(pcr_row[1] or 1)
            pcr = pe_oi / ce_oi if ce_oi > 0 else 1.0

            # Get IV Rank (52-week VIX range)
            cursor.execute("""
                SELECT MIN(india_vix_ltp) as iv_low, MAX(india_vix_ltp) as iv_high
                FROM market_feed_realtime
                WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 365 DAY)
            """)
            iv_row = cursor.fetchone()
            iv_rank = calc_iv_rank(
                vix_current,
                decimal_to_float(iv_row[1] or 20),
                decimal_to_float(iv_row[0] or 10)
            ) or 50.0

        # Get expiry date from Dhan API (auto-detect next Tuesday)
        from datetime import datetime as dt
        from dhanhq import dhanhq
        from core import Utilities

        # Initialize Dhan client
        dhan = dhanhq(Config.DHAN_CLIENT_ID, Config.DHAN_ACCESS_TOKEN)
        expiry_data = Utilities.get_expiry_list(dhan)
        expiry_str = expiry_data[0] if isinstance(expiry_data, list) and len(expiry_data) > 0 else expiry_data
        expiry_date = dt.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else dt.now().date()

        # Process Greeks
        processed = process_greeks_from_db(
            db_rows=db_rows,
            spot=spot,
            expiry_date=expiry_date,
            vix_current=vix_current,
            vix_prev=vix_prev,
            pcr=pcr,
            prev_minute_greeks=_greeks_cache['prev_snapshot']
        )

        # Update cache for next velocity calculation
        _greeks_cache['prev_snapshot'] = {
            f"{r['strike_price']}_{r['option_type']}": r
            for r in processed['ce_ranked'] + processed['pe_ranked']
        }
        _greeks_cache['data'] = processed
        _greeks_cache['timestamp'] = datetime.now()

        # Get portfolio net delta
        portfolio = get_portfolio_net_delta()

        # Generate entry signals
        from core.greeks_processor import generate_entry_signals
        signals = generate_entry_signals(processed, iv_rank)

        # Lotto strikes (Scalp + Gamma Blast)
        lotto = [r for r in processed['ce_ranked'] + processed['pe_ranked']
                 if r.get('lotto_flag')]

        # Calculate new analytics
        from core.greeks_processor import calc_put_call_skew, calc_max_pain, calc_straddle_premium

        # Find ATM strikes
        spot = processed['spot']
        atm_ce = min(processed['ce_ranked'], key=lambda x: abs(x['strike_price'] - spot)) if processed['ce_ranked'] else {}
        atm_pe = min(processed['pe_ranked'], key=lambda x: abs(x['strike_price'] - spot)) if processed['pe_ranked'] else {}

        # Put-Call Skew
        put_call_skew = calc_put_call_skew(
            atm_ce_iv=atm_ce.get('iv', 0) * 100,
            atm_pe_iv=atm_pe.get('iv', 0) * 100
        )

        # Max Pain
        all_strikes_for_max_pain = [{
            'strike_price': r['strike_price'],
            'ce_oi': next((c['oi'] for c in processed['ce_ranked'] if c['strike_price'] == r['strike_price']), 0),
            'pe_oi': r['oi']
        } for r in processed['pe_ranked']]
        max_pain = calc_max_pain(all_strikes_for_max_pain)

        # Straddle Premium
        straddle_premium = calc_straddle_premium(
            atm_ce_ltp=atm_ce.get('ltp', 0),
            atm_pe_ltp=atm_pe.get('ltp', 0),
            spot=spot
        )

        # Build response
        response = {
            'status': 'ok',
            'timestamp': processed['timestamp'],
            'spot': processed['spot'],
            'dte': processed['dte'],
            'vix': processed['vix'],
            'vix_change_pct': processed['vix_change_pct'],
            'expiry': expiry_date.strftime('%Y-%m-%d'),
            'trend_intensity': processed['trend_intensity'],
            'pcr_divergence': processed['pcr_divergence'],
            'put_call_skew': put_call_skew,
            'max_pain': max_pain,
            'straddle_premium': straddle_premium,
            'ce_top5': processed['ce_ranked'][:5],
            'pe_top5': processed['pe_ranked'][:5],
            'ce_all': processed['ce_ranked'][:10],
            'pe_all': processed['pe_ranked'][:10],
            'lotto_strikes': lotto,
            'alerts': processed['alerts'],
            'entry_signals': signals,
            'portfolio': portfolio,
            'iv_rank': iv_rank,
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"/api/greeks-pro error: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/greeks/portfolio', methods=['GET'])
def greeks_portfolio():
    """Get portfolio net delta from User_ table."""
    try:
        portfolio = get_portfolio_net_delta()
        return jsonify(portfolio)
    except Exception as e:
        logger.error(f"/api/greeks/portfolio error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def get_portfolio_net_delta():
    """
    Calculate portfolio net delta from User_ table.

    Returns:
        Dict with total_delta, delta_bias, pnl_estimate, open_trades, trades
    """
    try:
        with DatabaseManager.get_cursor() as cursor:
            cursor.execute("""
                SELECT u.trade_id, u.strike_price, u.option_type,
                       u.quantity, u.entry_price,
                       CASE
                           WHEN u.option_type = 'CE' THEN h.ce_delta
                           WHEN u.option_type = 'PE' THEN h.pe_delta
                       END as delta,
                       CASE
                           WHEN u.option_type = 'CE' THEN h.ce_theta
                           WHEN u.option_type = 'PE' THEN h.pe_theta
                       END as theta,
                       CASE
                           WHEN u.option_type = 'CE' THEN h.ce_gamma
                           WHEN u.option_type = 'PE' THEN h.pe_gamma
                       END as gamma,
                       CASE
                           WHEN u.option_type = 'CE' THEN h.ce_price
                           WHEN u.option_type = 'PE' THEN h.pe_price
                       END as current_ltp,
                       CASE
                           WHEN u.option_type = 'CE' THEN h.ce_alert_theta_trap
                           WHEN u.option_type = 'PE' THEN h.pe_alert_theta_trap
                       END as alert_theta_trap,
                       CASE
                           WHEN u.option_type = 'CE' THEN h.ce_alert_gamma_blast
                           WHEN u.option_type = 'PE' THEN h.pe_alert_gamma_blast
                       END as alert_gamma_blast
                FROM User_ u
                LEFT JOIN (
                    SELECT strike_price,
                           ce_delta, ce_theta, ce_gamma, ce_price,
                           ce_alert_theta_trap, ce_alert_gamma_blast,
                           pe_delta, pe_theta, pe_gamma, pe_price,
                           pe_alert_theta_trap, pe_alert_gamma_blast
                    FROM nifty_oc_historical
                    WHERE Date = CURDATE() AND Time = (
                        SELECT MAX(Time) FROM nifty_oc_historical WHERE Date = CURDATE()
                    )
                ) h ON h.strike_price = u.strike_price
                WHERE u.status = 'OPEN'
            """)

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            trades = [dict(zip(columns, row)) for row in rows]

        # Calculate totals
        total_delta = sum(
            decimal_to_float(t.get('delta', 0)) * decimal_to_float(t.get('quantity', 0))
            for t in trades
        )

        pnl = sum(
            (decimal_to_float(t.get('current_ltp', 0)) - decimal_to_float(t.get('entry_price', 0)))
            * decimal_to_float(t.get('quantity', 0))
            for t in trades
        )

        bias = ("NET LONG" if total_delta > 0.5 else
                "NET SHORT" if total_delta < -0.5 else "NEAR NEUTRAL")

        return {
            'total_delta': round(total_delta, 4),
            'delta_bias': bias,
            'pnl_estimate': round(pnl, 2),
            'open_trades': len(trades),
            'trades': trades,
        }

    except Exception as e:
        logger.error(f"get_portfolio_net_delta error: {e}")
        return {
            'error': str(e),
            'total_delta': 0.0,
            'trades': []
        }


@app.route('/api/greeks/signals', methods=['GET'])
def greeks_signals():
    """Get latest entry/exit signals."""
    try:
        if _greeks_cache['data'] is None:
            return jsonify({'error': 'No Greeks data available. Call /api/greeks-pro first'}), 404

        from core.greeks_processor import generate_entry_signals

        # Get IV rank
        with DatabaseManager.get_cursor() as cursor:
            cursor.execute("""
                SELECT MIN(india_vix_ltp) as iv_low, MAX(india_vix_ltp) as iv_high
                FROM market_feed_realtime
                WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 365 DAY)
            """)
            iv_row = cursor.fetchone()
            cursor.execute("""
                SELECT india_vix_ltp FROM market_feed_realtime
                ORDER BY timestamp DESC LIMIT 1
            """)
            vix_current = decimal_to_float(cursor.fetchone()[0]) if cursor.rowcount > 0 else 14.0

        iv_rank = calc_iv_rank(
            vix_current,
            decimal_to_float(iv_row[1] or 20),
            decimal_to_float(iv_row[0] or 10)
        ) or 50.0

        signals = generate_entry_signals(_greeks_cache['data'], iv_rank)

        return jsonify({'signals': signals})

    except Exception as e:
        logger.error(f"/api/greeks/signals error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/available-times', methods=['GET'])
def available_times():
    """
    Get list of available times for a specific date.

    Query Parameters:
        date: Date in YYYY-MM-DD format (required)

    Returns:
        JSON with list of times in HH:MM:SS format
    """
    try:
        target_date = request.args.get('date')
        if not target_date:
            return jsonify({'status': 'error', 'message': 'Date parameter required'}), 400

        with DatabaseManager.get_cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT Time
                FROM nifty_oc_historical
                WHERE Date = %s AND ce_efficiency IS NOT NULL
                ORDER BY Time ASC
            """, (target_date,))
            rows = cursor.fetchall()

            times = [row[0].strftime('%H:%M:%S') if hasattr(row[0], 'strftime') else str(row[0]) for row in rows]

            return jsonify({
                'status': 'success',
                'date': target_date,
                'times': times,
                'count': len(times)
            })

    except Exception as e:
        logger.error(f"Error in available-times endpoint: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/')
def index():
    """Serve the main dashboard page."""
    from flask import send_file
    return send_file('index.html')


@app.route('/greeks.html')
def greeks_dashboard():
    """Serve the Greeks dashboard page."""
    from flask import send_file
    return send_file('greeks.html')


@app.route('/option_chain.html')
def option_chain():
    """Serve the option chain page."""
    from flask import send_file
    return send_file('option_chain.html')


@app.route('/historical_data.html')
def historical_data():
    """Serve the historical data page."""
    from flask import send_file
    return send_file('historical_data.html')


@app.route('/api_credentials.html')
def api_credentials():
    """Serve the API credentials page."""
    from flask import send_file
    return send_file('api_credentials.html')


if __name__ == '__main__':
    logger.info("Starting OI Dashboard API server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
