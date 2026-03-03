#!/usr/bin/env python
"""Test script to verify Greeks API endpoints."""

import sys
import os
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'dashboard'))

from api import app
import json

print("=" * 60)
print("GREEKS API ENDPOINTS VERIFICATION")
print("=" * 60)

# Create test client
client = app.test_client()

# Test 1: Health check
print("\n[TEST 1] GET /api/health")
response = client.get('/api/health')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = json.loads(response.data)
    print(f"Response: {json.dumps(data, indent=2)}")
    print("[OK] Health check passed")
else:
    print(f"[ERROR] Health check failed: {response.data}")

# Test 2: Greeks Pro endpoint
print("\n[TEST 2] GET /api/greeks-pro")
response = client.get('/api/greeks-pro')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = json.loads(response.data)
    print(f"Response keys: {list(data.keys())}")
    print(f"Status: {data.get('status')}")
    if 'spot' in data:
        print(f"Spot: {data['spot']}")
    if 'vix' in data:
        print(f"VIX: {data['vix']}")
    if 'trend_intensity' in data:
        print(f"Market Bias: {data['trend_intensity'].get('market_bias')}")
    print("[OK] Greeks Pro endpoint working")
else:
    print(f"[WARN] Greeks Pro returned: {response.status_code}")
    error_data = json.loads(response.data) if response.data else {}
    print(f"Message: {error_data.get('message', error_data.get('error', 'No error message'))}")
    if response.status_code == 404:
        print("[INFO] This is expected when main.py hasn't run yet")

# Test 3: Portfolio endpoint
print("\n[TEST 3] GET /api/greeks/portfolio")
response = client.get('/api/greeks/portfolio')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = json.loads(response.data)
    print(f"Total Delta: {data.get('total_delta', 0.0)}")
    print(f"Delta Bias: {data.get('delta_bias', 'N/A')}")
    print(f"Open Trades: {data.get('open_trades', 0)}")
    print("[OK] Portfolio endpoint working")
else:
    print(f"[ERROR] Portfolio endpoint failed: {response.data}")

print("\n" + "=" * 60)
print("API VERIFICATION COMPLETE")
print("=" * 60)
print("\nNOTE: 'No data available' errors are expected when main.py hasn't run yet.")
print("Start main.py during market hours to populate data.")
