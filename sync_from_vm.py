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

Configuration is read from environment variables (see .env.example):
  VM_DB_USER, VM_DB_PASSWORD, VM_DB_NAME   — VM mysql credentials
  DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT — local mysql credentials
  GCP_PROJECT                              — GCP project ID
  MYSQL_BIN                                — path to local mysql.exe (optional)
"""

import argparse
import gzip
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is optional — env vars can still be set by the shell
    pass


# ---------------------------------------------------------------------------
# Configuration – loaded from environment variables, no hardcoded secrets
# ---------------------------------------------------------------------------
def _require_env(name: str) -> str:
    """Return env var or exit with a helpful error."""
    val = os.environ.get(name)
    if not val:
        sys.stderr.write(
            f"ERROR: Required environment variable '{name}' is not set.\n"
            f"  Add it to your .env file or export it in your shell.\n"
            f"  See .env.example for the expected variables.\n"
        )
        sys.exit(2)
    return val


# VM MySQL credentials (required — no defaults)
VM_DB_USER = os.environ.get("VM_DB_USER", "root")
VM_DB_NAME = os.environ.get("VM_DB_NAME", "analyzer_db")
VM_DB_PASSWORD = _require_env("VM_DB_PASSWORD")

# Local MySQL credentials
LOCAL_DB_HOST = os.environ.get("DB_HOST", "localhost")
LOCAL_DB_USER = os.environ.get("DB_USER", "root")
LOCAL_DB_PASSWORD = _require_env("DB_PASSWORD")
LOCAL_DB_NAME = os.environ.get("DB_NAME", "analyzer_db")
LOCAL_DB_PORT = os.environ.get("DB_PORT", "3306")

# GCP project
GCP_PROJECT = os.environ.get("GCP_PROJECT", "complete-energy-450807-r6")

# VM paths
VM_DUMP_DIR = "/tmp"
VM_DUMP_FILE = "vm_data_dump.sql.gz"

# Local mysql client binary. Default is the typical Windows install path;
# override via MYSQL_BIN env var on other setups.
MYSQL_BIN = os.environ.get(
    "MYSQL_BIN",
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
).strip('"').strip("'")

# Resolve gcloud executable (handles gcloud.cmd on Windows via PATHEXT).
GCLOUD = shutil.which("gcloud") or "gcloud"

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


# ---------------------------------------------------------------------------
# Subprocess helpers — argv lists only, shell=False, no interpolation
# ---------------------------------------------------------------------------
def run_cmd(argv, check=True, capture=False, stdin=None, env=None):
    """Run a command with an argv list (no shell, no injection risk)."""
    display = " ".join(str(a) for a in argv)
    if len(display) > 220:
        display = display[:220] + "…"
    print(f"  > {display}")
    return subprocess.run(
        argv,
        check=check,
        capture_output=capture,
        text=True,
        stdin=stdin,
        env=env,
    )


def _mysql_env():
    """Return an env dict with MYSQL_PWD set.

    Using MYSQL_PWD keeps the password out of the command line (and out of
    `ps`/task manager) and silences the 'password on cmdline is insecure'
    warning from mysql/mysqldump.
    """
    env = os.environ.copy()
    env["MYSQL_PWD"] = LOCAL_DB_PASSWORD
    return env


def mysql_query(sql: str) -> str:
    """Execute a SQL statement on the local database and return stdout."""
    argv = [
        MYSQL_BIN,
        "-h", LOCAL_DB_HOST,
        "-P", str(LOCAL_DB_PORT),
        "-u", LOCAL_DB_USER,
        LOCAL_DB_NAME,
        "-N",
        "-e", sql,
    ]
    result = subprocess.run(
        argv, capture_output=True, text=True, env=_mysql_env()
    )
    return result.stdout.strip()


def get_row_counts_fast():
    """Approximate row counts via information_schema (instant).

    After a bulk import InnoDB estimates may lag, so we force a stats
    refresh with ANALYZE TABLE first.
    """
    for table in TABLES:
        mysql_query(f"ANALYZE TABLE {table}")

    sql = (
        "SELECT TABLE_NAME, TABLE_ROWS "
        "FROM information_schema.TABLES "
        f"WHERE TABLE_SCHEMA = '{LOCAL_DB_NAME}'"
    )
    out = mysql_query(sql)
    counts = {table: 0 for table in TABLES}
    for line in out.splitlines():
        # mysql -N output is tab-separated — do NOT use .split() (any whitespace)
        parts = line.split("\t")
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
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Warning: could not read {SYNC_STATE_FILE.name}: {e}")
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
        out = mysql_query(f"SELECT MAX({col}) FROM {table}")
        if out and out != "NULL":
            max_dates[table] = out.strip()
    return max_dates


def decompress_gz(gz_path: str) -> str:
    """Decompress a .gz file and return the path to the decompressed .sql file."""
    sql_path = str(gz_path).replace(".gz", "")
    print(f"  Decompressing {gz_path}...")
    with gzip.open(gz_path, "rb") as f_in, open(sql_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    gz_size_mb = os.path.getsize(gz_path) / (1024 * 1024)
    sql_size_mb = os.path.getsize(sql_path) / (1024 * 1024)
    print(f"  Decompressed to {sql_path} ({sql_size_mb:.1f} MB)")
    if gz_size_mb > 0 and sql_size_mb > gz_size_mb:
        ratio = sql_size_mb / gz_size_mb
        saved = (1 - gz_size_mb / sql_size_mb) * 100
        print(
            f"  Compression: {gz_size_mb:.1f} MB → {sql_size_mb:.1f} MB "
            f"({ratio:.1f}x ratio, {saved:.0f}% bandwidth saved)"
        )
    return sql_path


# ---------------------------------------------------------------------------
# VM bash script — generated locally, uploaded to VM, executed via SSH
# ---------------------------------------------------------------------------
def _build_dump_script(incremental_dates=None) -> str:
    """Build the bash script that runs mysqldump + gzip on the VM.

    The password is passed via the MYSQL_PWD env var so it never appears in
    the VM's process list (ps/top).
    """
    # shlex.quote handles any single quotes or special chars in the password.
    quoted_pw = shlex.quote(VM_DB_PASSWORD)

    lines = [
        "#!/bin/bash",
        "set -e",
        f"export MYSQL_PWD={quoted_pw}",
        "(",
    ]

    is_incremental = bool(incremental_dates and any(incremental_dates.values()))

    for table in TABLES:
        col = TABLE_DATE_COLUMNS[table]
        base = (
            f"  mysqldump -u {VM_DB_USER} "
            f"--insert-ignore --no-create-info "
            f"--single-transaction --quick"
        )
        if is_incremental:
            date_val = incremental_dates.get(table)
            if date_val:
                # Dates are well-formed (YYYY-MM-DD [HH:MM:SS[.ffffff]])
                # so the single-quoted literal is safe.
                base += f' --where="{col} >= \'{date_val}\'"'
        base += f" {VM_DB_NAME} {table}"
        lines.append(base)

    lines.append(f") | gzip > {VM_DUMP_DIR}/{VM_DUMP_FILE}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Step 1: Create dump on VM via gcloud SSH (with gzip compression)
# ---------------------------------------------------------------------------
def create_vm_dump(vm_name, zone, project, incremental_dates=None):
    """Upload a bash script to the VM and run it to produce a gzipped dump."""
    is_incremental = bool(incremental_dates and any(incremental_dates.values()))

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

    # Write bash script with Unix line endings (bash is picky about \r)
    script_body = _build_dump_script(incremental_dates)
    local_script = Path(tempfile.gettempdir()) / "_sync_dump.sh"
    with open(local_script, "w", newline="\n") as f:
        f.write(script_body)

    try:
        print("  Uploading dump script to VM...")
        run_cmd([
            GCLOUD, "compute", "scp",
            str(local_script),
            f"{vm_name}:/tmp/_sync_dump.sh",
            f"--zone={zone}",
            f"--project={project}",
        ])

        print("  Running mysqldump + gzip on VM...")
        run_cmd([
            GCLOUD, "compute", "ssh", vm_name,
            f"--zone={zone}",
            f"--project={project}",
            "--command",
            "bash /tmp/_sync_dump.sh && rm -f /tmp/_sync_dump.sh",
        ])
    finally:
        # Always clean up local temp script, even on failure
        try:
            local_script.unlink(missing_ok=True)
        except OSError:
            pass

    print("  Compressed dump created on VM.\n")


def cleanup_vm_dump(vm_name, zone, project):
    """Delete the dump file from the VM after successful download."""
    try:
        run_cmd([
            GCLOUD, "compute", "ssh", vm_name,
            f"--zone={zone}",
            f"--project={project}",
            "--command",
            f"rm -f {VM_DUMP_DIR}/{VM_DUMP_FILE}",
        ], check=False)
    except Exception as e:
        print(f"  Warning: could not clean up VM dump file: {e}")


# ---------------------------------------------------------------------------
# Step 2: Download the dump via gcloud SCP
# ---------------------------------------------------------------------------
def download_dump(vm_name, zone, local_path, project):
    """Download the compressed dump file from the VM using gcloud scp."""
    print("[2/3] Downloading compressed dump from VM...")

    remote_path = f"{vm_name}:{VM_DUMP_DIR}/{VM_DUMP_FILE}"
    gz_local = local_path if local_path.endswith(".gz") else local_path + ".gz"

    run_cmd([
        GCLOUD, "compute", "scp",
        remote_path,
        gz_local,
        f"--zone={zone}",
        f"--project={project}",
    ])

    gz_size_mb = os.path.getsize(gz_local) / (1024 * 1024)
    print(f"  Downloaded {gz_local} ({gz_size_mb:.1f} MB compressed)")

    sql_path = decompress_gz(gz_local)

    try:
        os.remove(gz_local)
    except OSError as e:
        print(f"  Warning: could not remove {gz_local}: {e}")

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
        dump_path = Path(decompress_gz(str(dump_path)))

    size_mb = dump_path.stat().st_size / (1024 * 1024)
    print(f"[Import] Importing {dump_path.name} ({size_mb:.1f} MB) into local DB...")

    print("  Counting rows before import (approximate)...")
    before = get_row_counts_fast()
    for table, count in before.items():
        print(f"    {table}: ~{count:,} rows")

    print("\n  Importing with index checks disabled for speed...")
    start = time.time()

    # --init-command runs once at session start to disable checks for speed.
    # Scoped to THIS session only — no GLOBAL changes needed.
    argv = [
        MYSQL_BIN,
        "-h", LOCAL_DB_HOST,
        "-P", str(LOCAL_DB_PORT),
        "-u", LOCAL_DB_USER,
        "--init-command=SET autocommit=0; SET unique_checks=0; SET foreign_key_checks=0;",
        LOCAL_DB_NAME,
    ]
    print(f"  > {' '.join(argv)} < {dump_path.name}")

    with open(dump_path, "rb") as f_in:
        result = subprocess.run(
            argv,
            stdin=f_in,
            capture_output=True,
            text=True,
            env=_mysql_env(),
            check=False,
        )

    elapsed = time.time() - start

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "ERROR" in stderr:
            print(f"  MySQL errors:\n{stderr}")
            sys.exit(1)
        elif stderr:
            print(f"  MySQL warnings (expected for INSERT IGNORE):\n{stderr[:500]}")

    print(f"  Import completed in {elapsed:.1f}s")

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
        import_dump(args.import_only)
        return

    if args.dump_only:
        incremental_dates = None
        if not args.full:
            incremental_dates = get_local_max_dates()
            if incremental_dates:
                print("  Using incremental mode (add --full for complete dump)")
        create_vm_dump(args.vm_name, args.zone, args.project, incremental_dates)
        print("Dump created on VM. Download it manually via GCP SSH browser or run:")
        print(
            f"  gcloud compute scp {args.vm_name}:{VM_DUMP_DIR}/{VM_DUMP_FILE} . "
            f"--zone={args.zone} --project={args.project}"
        )
        return

    # Full flow: dump → download → import
    incremental_dates = None
    if not args.full:
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
