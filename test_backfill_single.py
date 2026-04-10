"""
Test backfill for a single timestamp to debug the issue
"""
import logging
from datetime import datetime
from dhanhq import dhanhq
from core.config import Config, now_ist
from core import Utilities
from core.greeks_processor import process_greeks_from_db
from core.database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize
DatabaseManager.initialize_pool()
dhan_client = dhanhq(Config.DHAN_CLIENT_ID, Config.DHAN_ACCESS_TOKEN)

# Get expiry
expiry_data = Utilities.get_expiry_list(dhan_client)
expiry_str = expiry_data[0] if isinstance(expiry_data, list) and len(expiry_data) > 0 else expiry_data
expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else now_ist().date()

print(f"\nExpiry Date: {expiry_date}")

# Test with March 2, first timestamp
target_date = '2026-03-02'
target_time = '09:32:12'

print(f"\n{'='*80}")
print(f"Testing: {target_date} {target_time}")
print(f"{'='*80}\n")

# Get data from database
with DatabaseManager.get_cursor() as cursor:
    cursor.execute("""
        SELECT *
        FROM nifty_oc_historical
        WHERE Date = %s AND Time = %s
        LIMIT 5
    """, (target_date, target_time))

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    print(f"Found {cursor.rowcount} rows")

    if rows:
        # Convert to lowercase for greeks processor compatibility
        db_rows = [{col.lower(): val for col, val in zip(columns, row)} for row in rows]

        # Check first row
        print(f"\nFirst row sample:")
        print(f"  Strike: {db_rows[0].get('strike_price')}")
        print(f"  Spot: {db_rows[0].get('spot_price')}")
        print(f"  CE LTP: {db_rows[0].get('ce_price')}")
        print(f"  CE Delta: {db_rows[0].get('ce_delta')}")
        print(f"  CE Theta: {db_rows[0].get('ce_theta')}")
        print(f"  CE Gamma: {db_rows[0].get('ce_gamma')}")
        print(f"  CE Vega: {db_rows[0].get('ce_vega')}")
        print(f"  CE IV: {db_rows[0].get('ce_iv')}")
        print(f"  CE Efficiency (before): {db_rows[0].get('ce_efficiency')}")

        # Get spot price
        spot_price = float(db_rows[0].get('spot_price', 0))

        # Get PCR
        cursor.execute("""
            SELECT
                SUM(pe_oi) as pe_oi_total,
                SUM(ce_oi) as ce_oi_total
            FROM nifty_oc_historical
            WHERE Date = %s AND Time = %s
        """, (target_date, target_time))

        pcr_row = cursor.fetchone()
        pe_oi_total = float(pcr_row[0] or 1)
        ce_oi_total = float(pcr_row[1] or 1)
        pcr = pe_oi_total / ce_oi_total if ce_oi_total > 0 else 1.0

        print(f"\nMarket Data:")
        print(f"  Spot Price: {spot_price}")
        print(f"  PCR: {pcr:.3f}")

# Process Greeks with ALL rows
with DatabaseManager.get_cursor() as cursor:
    cursor.execute("""
        SELECT *
        FROM nifty_oc_historical
        WHERE Date = %s AND Time = %s
    """, (target_date, target_time))

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    # Convert to lowercase for greeks processor compatibility
    db_rows = [{col.lower(): val for col, val in zip(columns, row)} for row in rows]
    spot_price = float(db_rows[0].get('Spot_price', 0))

    cursor.execute("""
        SELECT SUM(pe_oi) as pe_oi_total, SUM(ce_oi) as ce_oi_total
        FROM nifty_oc_historical
        WHERE Date = %s AND Time = %s
    """, (target_date, target_time))

    pcr_row = cursor.fetchone()
    pcr = float(pcr_row[0] or 1) / float(pcr_row[1] or 1) if pcr_row[1] else 1.0

# Process Greeks
print(f"\nProcessing Greeks...")
greeks_result = process_greeks_from_db(
    db_rows=db_rows,
    spot=spot_price,
    expiry_date=expiry_date,
    vix_current=14.0,
    vix_prev=14.0,
    pcr=pcr,
    prev_minute_greeks=None
)

print(f"\nGreeks Result:")
print(f"  DTE: {greeks_result['dte']}")
print(f"  CE Strikes: {len(greeks_result['ce_ranked'])}")
print(f"  PE Strikes: {len(greeks_result['pe_ranked'])}")

if greeks_result['ce_ranked']:
    first_ce = greeks_result['ce_ranked'][0]
    print(f"\nFirst CE Strike:")
    print(f"  Strike: {first_ce.get('strike_price')}")
    print(f"  Efficiency: {first_ce.get('efficiency')}")
    print(f"  Vega Adj Efficiency: {first_ce.get('vega_adj_efficiency')}")
    print(f"  Delta Velocity: {first_ce.get('delta_velocity')}")

# Now try to UPDATE
print(f"\n{'='*80}")
print("Attempting UPDATE...")
print(f"{'='*80}\n")

strikes_by_price = {}
for strike_data in greeks_result['ce_ranked'] + greeks_result['pe_ranked']:
    sp = strike_data['strike_price']
    if sp not in strikes_by_price:
        strikes_by_price[sp] = {'CE': None, 'PE': None}
    strikes_by_price[sp][strike_data['option_type']] = strike_data

update_count = 0
with DatabaseManager.get_cursor() as cursor:
    for strike_price, data in list(strikes_by_price.items())[:3]:  # Only first 3 for testing
        ce_data = data.get('CE', {}) or {}
        pe_data = data.get('PE', {}) or {}

        print(f"\nUpdating Strike {strike_price}:")
        print(f"  CE Efficiency: {ce_data.get('efficiency')}")
        print(f"  PE Efficiency: {pe_data.get('efficiency')}")

        cursor.execute("""
            UPDATE nifty_oc_historical
            SET
                dte = %s,
                ce_efficiency = %s,
                ce_vega_adj_efficiency = %s,
                ce_delta_velocity = %s,
                ce_gamma_velocity = %s,
                ce_theta_velocity = %s,
                ce_iv_velocity = %s,
                ce_alert_theta_trap = %s,
                ce_alert_gamma_blast = %s,
                ce_alert_negative_carry = %s,
                pe_efficiency = %s,
                pe_vega_adj_efficiency = %s,
                pe_delta_velocity = %s,
                pe_gamma_velocity = %s,
                pe_theta_velocity = %s,
                pe_iv_velocity = %s,
                pe_alert_theta_trap = %s,
                pe_alert_gamma_blast = %s,
                pe_alert_negative_carry = %s
            WHERE Date = %s
              AND Time = %s
              AND Strike_price = %s
        """, (
            greeks_result['dte'],
            # CE columns
            ce_data.get('efficiency') if ce_data else None,
            ce_data.get('vega_adj_efficiency') if ce_data else None,
            ce_data.get('delta_velocity', 0.0) if ce_data else 0.0,
            ce_data.get('gamma_velocity', 0.0) if ce_data else 0.0,
            ce_data.get('theta_velocity', 0.0) if ce_data else 0.0,
            ce_data.get('iv_velocity', 0.0) if ce_data else 0.0,
            ce_data.get('alert_theta_trap', False) if ce_data else False,
            ce_data.get('alert_gamma_blast', False) if ce_data else False,
            ce_data.get('alert_negative_carry', False) if ce_data else False,
            # PE columns
            pe_data.get('efficiency') if pe_data else None,
            pe_data.get('vega_adj_efficiency') if pe_data else None,
            pe_data.get('delta_velocity', 0.0) if pe_data else 0.0,
            pe_data.get('gamma_velocity', 0.0) if pe_data else 0.0,
            pe_data.get('theta_velocity', 0.0) if pe_data else 0.0,
            pe_data.get('iv_velocity', 0.0) if pe_data else 0.0,
            pe_data.get('alert_theta_trap', False) if pe_data else False,
            pe_data.get('alert_gamma_blast', False) if pe_data else False,
            pe_data.get('alert_negative_carry', False) if pe_data else False,
            # WHERE clause
            target_date, target_time, strike_price
        ))

        print(f"  Rows affected: {cursor.rowcount}")
        update_count += cursor.rowcount

print(f"\nTotal rows updated: {update_count}")

# Verify the update
print(f"\n{'='*80}")
print("Verifying UPDATE...")
print(f"{'='*80}\n")

with DatabaseManager.get_cursor() as cursor:
    cursor.execute("""
        SELECT Strike_price, ce_efficiency, pe_efficiency
        FROM nifty_oc_historical
        WHERE Date = %s AND Time = %s
        ORDER BY Strike_price
        LIMIT 5
    """, (target_date, target_time))

    rows = cursor.fetchall()
    for row in rows:
        print(f"  Strike {row[0]}: CE Eff = {row[1]}, PE Eff = {row[2]}")

print("\nDone!")
