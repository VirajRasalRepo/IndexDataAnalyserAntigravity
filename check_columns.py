"""Check actual column names in database"""
from core.database import DatabaseManager

DatabaseManager.initialize_pool()

with DatabaseManager.get_cursor() as cursor:
    cursor.execute("SELECT * FROM nifty_oc_historical LIMIT 1")
    columns = [desc[0] for desc in cursor.description]

    print("\nDatabase Column Names:")
    print("="*80)
    for i, col in enumerate(columns, 1):
        print(f"{i:3d}. {col}")

    print("\n" + "="*80)
    print("\nLooking for strike/greek columns:")
    for col in columns:
        if 'strike' in col.lower() or 'delta' in col.lower() or 'theta' in col.lower():
            print(f"  - {col}")
