import urllib.request
import json

with urllib.request.urlopen('http://localhost:5000/api/oi-difference-live?strike_count=10') as response:
    data = json.loads(response.read().decode())

print('=== Checking Dashboard Data ===\n')

# Check for non-zero OI differences
found_nonzero = False
for ts in data['time_series']:
    for strike_key, values in ts['data'].items():
        if values['ce_oi_diff'] != 0 or values['pe_oi_diff'] != 0:
            found_nonzero = True
            print(f'[OK] Found non-zero at {ts["timestamp"]} | Strike: {strike_key}')
            print(f'  CE OI Diff: {values["ce_oi_diff"]:,} -> {values["ce_oi_diff"]/1000:.1f}K')
            print(f'  PE OI Diff: {values["pe_oi_diff"]:,} -> {values["pe_oi_diff"]/1000:.1f}K\n')
            break
    if found_nonzero:
        break

if not found_nonzero:
    print('[WARNING] ALL OI DIFFERENCES ARE ZERO - This is normal market behavior\n')

# But check if OI values themselves are showing
print('Latest timestamp OI values (should NOT be zero):')
first_strike = list(data['time_series'][-1]['data'].keys())[0]
values = data['time_series'][-1]['data'][first_strike]
print(f'  Strike {first_strike}:')
print(f'    CE OI: {values["ce_oi"]:,} -> Should display as {values["ce_oi"]/100000:.2f}L')
print(f'    PE OI: {values["pe_oi"]:,} -> Should display as {values["pe_oi"]/100000:.2f}L')
print(f'    CE Vol: {values["ce_vol"]:,} -> Should display as {values["ce_vol"]/1000:.0f}K')
print(f'    PE Vol: {values["pe_vol"]:,} -> Should display as {values["pe_vol"]/1000:.0f}K')
