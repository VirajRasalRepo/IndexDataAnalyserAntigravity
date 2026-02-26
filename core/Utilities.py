


def get_atm_strike(last_price, base=50):
    return base * round(last_price / base)

# 2. AUTOMATIC EXPIRY LOOKUP (Recommended)
# This ensures we get the exact Tuesday date the API expects
def get_expiry_list(dhan):
    print("Fetching valid Tuesday expiries for Nifty 50...")
    expiry_response = dhan.expiry_list(under_security_id=13, under_exchange_segment="IDX_I")

    if expiry_response.get('status') == 'success':
        # Get the first available expiry date from the list
        next_tuesday = expiry_response['data']['data'][0]
        print(f"Targeting Expiry: {next_tuesday}")
    else:
        print("Could not fetch expiry list. Defaulting to 2026-01-27.")
        next_tuesday = "2026-01-27"

    return next_tuesday