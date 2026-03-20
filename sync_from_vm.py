#command to get data from vm to local sql
#python sync_from_vm.py --vm-name index-data-analyser --zone asia-south1-a


#!/usr/bin/env python3
"""
Sync database data from GCP VM to local MySQL.

Usage:
  1. Incremental sync (default — only new data since last sync):
     python sync_from_vm.py --vm-name index-data-analyser --zone asia-south1-a

  2. Full sync (all data from scratch):
     python sync_from_vm.py --full --vm-name index-data-analyser --zone asia-south1-a

  3. Import an already-downloaded dump file:
     python sync_from_vm.py --import-only vm_data_dump.sql
     python sync_from_vm.py --import-only vm_data_dump.sql.gz

  4. Just create the dump on VM (download manually later):
     python sync_from_vm.py --dump-only --vm-name index-data-analyser --zone asia-south1-a
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration – edit these if your setup differs
# ---------------------------------------------------------------------------
VM_DB_USER = "root"
VM_DB_PASSWORD = "Indian#9190"
VM_DB_NAME = "analyzer_db"
VM_DUMP_DIR = "/tmp"  # /tmp is always writable
VM_DUMP_FILE = "vm_data_dump.sql.gz"  # compressed dump
GCP_PROJECT = "complete-energy-450807-r6"

LOCAL_DB_HOST = os.getenv("DB_HOST", "localhost")
LOCAL_DB_USER = os.getenv("DB_USER", "root")
LOCAL_DB_PASSWORD = os.getenv("DB_PASSWORD", "qwerty123456")
LOCAL_DB_NAME = os.getenv("DB_NAME", "analyzer_db")
LOCAL_DB_PORT = os.getenv("DB_PORT", "3306")
MYSQL_BIN = r'"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"'

SYNC_STATE_FILE = Path(__file__).parent / "sync_state.json"

# Table name → date/time column used for incremental WHERE clause
TABLE_DATE_COLUMNS = {
    "nifty_oc_historical": "Date",
    "market_feed_realtime": "timestamp",
    "market_watch_wide": "timestamp",
    "user_trades": "entry_time",
    "user_": "entry_time",
}

TABLES = list(TABLE_DATE_COLUMNS.keys())


def run(cmd, check=True, capture=False, **kwargs):
    """Run a shell command with nice logging."""
    print(f"  > {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        check=check,
        capture_output=capture,
        text=True,
        **kwargs,
    )
    return result


def mysql_cmd(sql, capture=True):
    """Execute a SQL statement on the local database and return stdout."""
    cmd = (
        f'{MYSQL_BIN} -h {LOCAL_DB_HOST} -P {LOCAL_DB_PORT} '
        f'-u {LOCAL_DB_USER} -p{LOCAL_DB_PASSWORD} '
        f'{LOCAL_DB_NAME} -N -e "{sql}"'
    )
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def get_row_counts_fast():
    """Get approximate row counts using information_schema (instant).

    After a bulk import InnoDB estimates may lag, so we force a stats
    refresh with ANALYZE TABLE first.
    """
    # Force InnoDB to update its row estimates
    for table in TABLES:
        mysql_cmd(f"ANALYZE TABLE {table}")

    sql = (
        "SELECT TABLE_NAME, TABLE_ROWS "
        "FROM information_schema.TABLES "
        f"WHERE TABLE_SCHEMA = '{LOCAL_DB_NAME}'"
    )
    out = mysql_cmd(sql)
    counts = {table: 0 for table in TABLES}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in counts:
            try:
                counts[parts[0]] = int(parts[1])
            except (ValueError, TypeError):
                pass
    return counts


# ---------------------------------------------------------------------------
# Sync state — tracks last successful sync date per table
# ---------------------------------------------------------------------------
def load_sync_state():
    """Load the last sync state from sync_state.json."""
    if SYNC_STATE_FILE.exists():
        try:
            with open(SYNC_STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_sync_state(state):
    """Save sync state to sync_state.json."""
    state["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SYNC_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"  Sync state saved to {SYNC_STATE_FILE.name}")


def get_local_max_dates():
    """Query local DB for the max date/timestamp of each table."""
    max_dates = {}
    for table, col in TABLE_DATE_COLUMNS.items():
        out = mysql_cmd(f"SELECT MAX({col}) FROM {table}")
        if out and out != "NULL":
            max_dates[table] = out.strip()
    return max_dates


def decompress_gz(gz_path):
    """Decompress a .gz file and return the path to the decompressed .sql file."""
    import gzip as gz_lib
    import shutil

    sql_path = str(gz_path).replace(".gz", "")
    print(f"  Decompressing {gz_path}...")
    with gz_lib.open(gz_path, 'rb') as f_in:
        with open(sql_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    gz_size_mb = os.path.getsize(gz_path) / (1024 * 1024)
    sql_size_mb = os.path.getsize(sql_path) / (1024 * 1024)
    print(f"  Decompressed to {sql_path} ({sql_size_mb:.1f} MB)")
    if sql_size_mb > 0:
        print(f"  Compression ratio: {gz_size_mb:.1f} MB → {sql_size_mb:.1f} MB "
              f"({(1 - gz_size_mb / sql_size_mb) * 100:.0f}% smaller transfer)")
    return sql_path


# ---------------------------------------------------------------------------
# Step 1: Create dump on VM via gcloud SSH (with gzip compression)
# ---------------------------------------------------------------------------
def create_vm_dump(vm_name, zone, project=None, incremental_dates=None):
    """SSH into the VM and run mysqldump, piped through gzip.

    Args:
        incremental_dates: dict of {table: "YYYY-MM-DD ..."} for WHERE clauses.
                          If None, dumps all data (full sync).
    """
    is_incremental = incremental_dates and any(incremental_dates.values())

    if is_incremental:
        print("\n[1/3] Creating INCREMENTAL dump on VM (gzip compressed)...")
        print("  Only fetching data newer than:")
        for table, dt in incremental_dates.items():
            if dt:
                print(f"    {table}: after {dt}")
            else:
                print(f"    {table}: FULL (no prior data)")
    else:
        print("\n[1/3] Creating FULL dump on VM (gzip compressed)...")

    dump_path = f"{VM_DUMP_DIR}/{VM_DUMP_FILE}"
    proj = project or GCP_PROJECT

    if is_incremental:
        # Per-table dumps with WHERE clauses
        # Each table dumps independently (;) so one failure doesn't skip the rest.
        # stderr goes to /dev/stderr so errors are visible through SSH.
        dump_parts = []
        for table in TABLES:
            date_val = incremental_dates.get(table)
            col = TABLE_DATE_COLUMNS[table]
            if date_val:
                where = f"--where=\\\"{col} >= '{date_val}'\\\""
                dump_parts.append(
                    f"mysqldump -u {VM_DB_USER} -p'{VM_DB_PASSWORD}' "
                    f"--insert-ignore --no-create-info "
                    f"--single-transaction --quick "
                    f"{where} {VM_DB_NAME} {table}"
                )
            else:
                dump_parts.append(
                    f"mysqldump -u {VM_DB_USER} -p'{VM_DB_PASSWORD}' "
                    f"--insert-ignore --no-create-info "
                    f"--single-transaction --quick "
                    f"{VM_DB_NAME} {table}"
                )

        # Use ; so all tables are attempted even if one fails.
        # Wrap in subshell and pipe combined stdout to gzip.
        combined = " ; ".join(dump_parts)
        remote_cmd = f"({combined}) | gzip > {dump_path}"
    else:
        # Full dump — all tables at once, piped through gzip
        tables_str = " ".join(TABLES)
        remote_cmd = (
            f"mysqldump -u {VM_DB_USER} -p'{VM_DB_PASSWORD}' "
            f"--insert-ignore --no-create-info "
            f"--single-transaction --quick "
            f"{VM_DB_NAME} {tables_str} | gzip > {dump_path}"
        )

    # On Windows, gcloud is a .cmd file so we need shell=True.
    # Double-quote the --command value so cmd.exe doesn't interpret > as local redirect.
    gcloud = (
        f'gcloud compute ssh {vm_name} '
        f'--zone={zone} --project={proj} '
        f'--command="{remote_cmd}"'
    )

    mode = "incremental" if is_incremental else "full"
    print(f"  Running {mode} mysqldump + gzip on VM...")
    print(f"  > gcloud compute ssh {vm_name} --zone={zone} --command=mysqldump | gzip ...")
    subprocess.run(gcloud, shell=True, check=True)
    print("  Compressed dump created on VM.\n")


# ---------------------------------------------------------------------------
# Step 2: Download the dump via gcloud SCP
# ---------------------------------------------------------------------------
def download_dump(vm_name, zone, local_path, project=None):
    """Download the compressed dump file from the VM using gcloud scp."""
    print("[2/3] Downloading compressed dump from VM...")

    remote_path = f"{vm_name}:{VM_DUMP_DIR}/{VM_DUMP_FILE}"
    proj = project or GCP_PROJECT

    # Download the .gz file
    gz_local = local_path + ".gz" if not local_path.endswith(".gz") else local_path
    gcloud = (
        f"gcloud compute scp {remote_path} {gz_local} "
        f"--zone={zone} --project={proj}"
    )

    print(f"  > gcloud compute scp {vm_name}:/tmp/{VM_DUMP_FILE} {gz_local}")
    subprocess.run(gcloud, shell=True, check=True)
    gz_size_mb = os.path.getsize(gz_local) / (1024 * 1024)
    print(f"  Downloaded {gz_local} ({gz_size_mb:.1f} MB compressed)")

    # Decompress locally
    sql_path = decompress_gz(gz_local)

    # Clean up .gz file
    try:
        os.remove(gz_local)
    except OSError:
        pass

    print()
    return sql_path


# ---------------------------------------------------------------------------
# Step 3: Import the dump into local MySQL (with fast-import optimizations)
# ---------------------------------------------------------------------------
def import_dump(dump_path, save_state=True):
    """Import the SQL dump into the local MySQL database."""
    dump_path = Path(dump_path)
    if not dump_path.exists():
        print(f"  ERROR: Dump file not found: {dump_path}")
        sys.exit(1)

    # Handle .gz files transparently
    if str(dump_path).endswith(".gz"):
        sql_path = decompress_gz(str(dump_path))
        dump_path = Path(sql_path)

    size_mb = dump_path.stat().st_size / (1024 * 1024)
    print(f"[Import] Importing {dump_path.name} ({size_mb:.1f} MB) into local DB...")

    # Get approximate row counts before import
    print("  Counting rows before import (approximate)...")
    before = get_row_counts_fast()
    for table, count in before.items():
        print(f"    {table}: ~{count:,} rows")

    # Use --init-command to disable checks for THIS import session only.
    # No GLOBAL changes needed — keeps the server safe if script crashes.
    print("\n  Importing with index checks disabled for speed...")
    start = time.time()

    import_cmd = (
        f'{MYSQL_BIN} -h {LOCAL_DB_HOST} -P {LOCAL_DB_PORT} '
        f'-u {LOCAL_DB_USER} -p{LOCAL_DB_PASSWORD} '
        f'--init-command="SET autocommit=0; SET unique_checks=0; SET foreign_key_checks=0;" '
        f'{LOCAL_DB_NAME} < "{dump_path}"'
    )
    result = run(import_cmd, check=False, capture=True)

    elapsed = time.time() - start

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Warnings about INSERT IGNORE are expected
        if "ERROR" in stderr:
            print(f"  MySQL errors:\n{stderr}")
            sys.exit(1)
        elif stderr:
            print(f"  MySQL warnings (expected for INSERT IGNORE):\n{stderr[:500]}")

    print(f"  Import completed in {elapsed:.1f}s")

    # Get approximate row counts after import
    print("\n  Counting rows after import (approximate)...")
    after = get_row_counts_fast()

    # Summary
    print("\n" + "=" * 60)
    print("  SYNC SUMMARY")
    print("=" * 60)
    print(f"  {'Table':<30} {'Before':>10} {'After':>10} {'~New':>10}")
    print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*10}")

    total_new = 0
    for table in TABLES:
        b = before.get(table, 0)
        a = after.get(table, 0)
        new = a - b
        total_new += new
        marker = " <--" if new > 0 else ""
        print(f"  {table:<30} {b:>10,} {a:>10,} {new:>+10,}{marker}")

    print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'TOTAL':<30} {'':>10} {'':>10} {total_new:>+10,}")
    print("=" * 60)
    print("  (counts are approximate via information_schema)")

    if total_new == 0:
        print("  No new data — local DB is already up to date.")
    else:
        print(f"  Successfully synced ~{total_new:,} new rows.")

    # Save sync state after successful import
    if save_state:
        max_dates = get_local_max_dates()
        state = load_sync_state()
        state["tables"] = max_dates
        save_sync_state(state)

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Sync database from GCP VM to local MySQL"
    )
    parser.add_argument(
        "--vm-name",
        default="index-data-analyser",
        help="GCP VM instance name (default: index-data-analyser)",
    )
    parser.add_argument(
        "--zone",
        default="asia-south1-a",
        help="GCP zone (default: asia-south1-a)",
    )
    parser.add_argument(
        "--project",
        default=GCP_PROJECT,
        help=f"GCP project ID (default: {GCP_PROJECT})",
    )
    parser.add_argument(
        "--import-only",
        metavar="FILE",
        help="Skip VM SSH — just import an existing dump file (.sql or .sql.gz)",
    )
    parser.add_argument(
        "--dump-only",
        action="store_true",
        help="Only create the dump on VM, don't download or import",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full sync — dump all data instead of incremental (default: incremental)",
    )
    parser.add_argument(
        "--output",
        default="vm_data_dump.sql",
        help="Local path to save the dump file (default: vm_data_dump.sql)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  VM → Local Database Sync")
    print("=" * 60)

    if args.import_only:
        # Just import an existing file
        import_dump(args.import_only)
        return

    if args.dump_only:
        # Just create the dump on VM
        incremental_dates = None
        if not args.full:
            incremental_dates = get_local_max_dates()
            if incremental_dates:
                print("  Using incremental mode (add --full for complete dump)")
        create_vm_dump(args.vm_name, args.zone, args.project, incremental_dates)
        print("Dump created on VM. Download it manually via GCP SSH browser")
        print(f"or run: gcloud compute scp {args.vm_name}:{VM_DUMP_DIR}/{VM_DUMP_FILE} . --zone={args.zone} --project={args.project}")
        return

    # Full flow: dump → download → import
    incremental_dates = None
    if not args.full:
        # Check local DB for latest data to determine incremental cutoff
        print("\n  Checking local DB for latest data...")
        incremental_dates = get_local_max_dates()
        if incremental_dates:
            print("  INCREMENTAL mode — only fetching new data")
            print("  (use --full to re-download everything)\n")
            for table, dt in incremental_dates.items():
                print(f"    {table}: last data at {dt}")
            print()
        else:
            print("  No existing data found — doing full sync\n")

    create_vm_dump(args.vm_name, args.zone, args.project, incremental_dates)
    sql_path = download_dump(args.vm_name, args.zone, args.output, args.project)
    import_dump(sql_path)


if __name__ == "__main__":
    main()
