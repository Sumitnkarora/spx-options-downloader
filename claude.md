# Claude Context - SPX Options Downloader

## Project Overview
A Python tool that downloads SPX and SPXW options data from ThetaData API and stores it in SQLite. The project follows a three-step download process.

## Environment
- **Conda Environment**: `Theta` (MUST be activated before running any scripts)
- **Python Path**: `/Users/snk/miniforge3/envs/Theta/bin/python`
- **ThetaData API**: Runs locally at `http://localhost:25503`
- **Database**: `database/theta_options.db` (SQLite)
- **Data Storage**: `/Volumes/X9/data/` (External SSD for Greeks data)
- **Dependencies**: `requests==2.31.0`, `zstandard==0.22.0`

## Architecture

### Core Files
1. **api_client.py** - ThetaData API wrapper
   - `get_expirations(symbol)` → list of (symbol, expiration)
     - Catches exceptions, prints error, returns [] on failure
   - `get_strikes(symbol, expiration)` → list of (symbol, expiration, strike)
     - Raises exceptions (no try-except) - handled by download script
   - `get_dates(symbol, expiration)` → list of (symbol, expiration, date)
     - Raises exceptions (no try-except) - handled by download script
   - `get_greeks_history(symbol, expiration, date)` → raw CSV string
     - Returns raw CSV text (not parsed) for direct file writing
     - Raises exceptions (no try-except) - handled by download script
     - Fixed interval: 5 seconds
   - Date conversion: YYYY-MM-DD ↔ YYYYMMDD for API calls
   - Returns CSV responses parsed into tuples (except greeks which returns raw CSV)

2. **database.py** - SQLite database manager
   - Tables: `expirations`, `strikes`, `available_dates`
   - All use `INSERT OR IGNORE` to prevent duplicates
   - Foreign keys enforced between tables
   - Helper methods:
     - `insert_*()` - Insert data into tables
     - `get_*_count()` - Get row counts
     - `get_all_expirations()` - Retrieve all expirations
     - `claim_next_row(max_retries)` - Atomically claim pending row (ORDER BY expiration DESC, date DESC)
     - `mark_completed(row_id)` - Mark row as successfully downloaded
     - `mark_failed(row_id, error_msg, max_retries)` - Handle failures with retry logic
     - `reset_stuck_rows(timeout_minutes)` - Reset stuck in_progress rows
     - `get_download_stats()` - Get status breakdown
     - `update_compressed_file_path(row_id, file_path)` - Store compressed file location
     - `set_busy_timeout(timeout_ms)` - Configure concurrent access timeout

3. **Download Scripts** (must run in order):
   - `download_expirations.py` - Downloads SPX/SPXW expirations
     - No error logging (exceptions caught in API client)
   - `download_strikes.py` - Downloads strikes for each expiration
     - Has error logging: logs to `errors.log` with timestamp
     - Catches exceptions per expiration, logs symbol/expiration info, continues
   - `download_dates.py` - Downloads quote dates for each expiration
     - Has error logging: logs to `errors.log` with timestamp
     - Catches exceptions per expiration, logs symbol/expiration info, continues
   - **`download_greeks.py`** - Downloads Greeks history data with compression
     - **Multi-process capable**: Run multiple instances in separate terminals
     - **Atomic row claiming**: Uses BEGIN IMMEDIATE transactions to prevent conflicts
     - **Compression**: Uses zstandard level 10 (40-100x compression)
     - **Download flow**:
       1. Claim row → mark as in_progress
       2. Download CSV from API
       3. Save CSV to /Volumes/X9/data/{symbol}/{year}/{month}/
       4. Compress with zstd → creates .csv.zst file
       5. Delete original CSV
       6. Store compressed file path in database
       7. Mark as completed
     - **Retry logic**: Max 3 retries per row, increments retry_count on failure
     - **Error handling**: Logs to errors.log, continues on failure
     - **Progress tracking**: Database status (pending/in_progress/completed/failed)
     - **Resume capability**: Graceful Ctrl+C, resets stuck rows on startup
   - `retry_failed_dates.py` - Retries specific symbol/expiration combinations that failed
     - Has error logging: logs to `errors.log` with timestamp
     - Processes only combinations listed in FAILED_EXPIRATIONS (hardcoded in script)
     - User edits the list before running

4. **Migration Scripts** (run once before first use):
   - `migrate_database.py` - Adds download tracking columns to available_dates
     - Columns: status, started_at, completed_at, retry_count, error_message
     - Resets stuck in_progress rows from previous runs
   - `migrate_compression.py` - Adds compression tracking column
     - Column: compressed_file_path

### Database Schema
```sql
expirations: (symbol, expiration) - UNIQUE

strikes: (symbol, expiration, strike) - UNIQUE, FK to expirations

available_dates: (symbol, expiration, date) - UNIQUE, FK to expirations
  Download tracking columns:
    - status TEXT DEFAULT 'pending' (values: pending, in_progress, completed, failed)
    - started_at TIMESTAMP
    - completed_at TIMESTAMP
    - retry_count INTEGER DEFAULT 0
    - error_message TEXT
    - compressed_file_path TEXT (full path to .csv.zst file)
```

## Execution Workflow
1. User runs `download_expirations.py` → Populates expirations table
2. User runs `download_strikes.py` → Reads expirations, downloads strikes
3. User runs `download_dates.py` → Reads expirations, downloads quote dates
4. User runs `migrate_database.py` → Adds download tracking columns (one-time setup)
5. User runs `migrate_compression.py` → Adds compression column (one-time setup)
6. User runs `download_greeks.py` (in 1-8 terminals) → Downloads and compresses Greeks data
7. (Optional) If downloads fail, user resets failed rows via SQL and re-runs

**Important**:
- Steps 2 and 3 are independent - they both depend on step 1, but not on each other
- Steps 4-5 are one-time migrations (safe to run multiple times, idempotent)
- Step 6 can be run with multiple concurrent processes
- Step 7 uses SQL queries to reset status (see README.md for queries)

## Code Patterns

### Print Statement Flow (used in all download scripts)
```python
print("Starting [name] downloader...", flush=True)
print("Connecting to database...", flush=True)
print(f"Found {len(items)} items in database", flush=True)
print(f"\n[{idx}/{total}] Processing: {symbol} {expiration}")
print(f"  Found {len(results)} [items]")
print(f"    Inserting [item]: {value}")
print(f"\nDone! Total [items] in database: {db.get_count()}")
```

### API Endpoint Pattern
- `/v3/option/list/expirations?symbol=SPX`
- `/v3/option/list/strikes?symbol=SPX&expiration=20250117`
- `/v3/option/list/dates/quote?symbol=SPX&expiration=20250117`
- `/v3/option/history/greeks/all?symbol=SPX&expiration=20250117&date=20250103&interval=5s`

## Key Technical Details

### ThetaData API
- **Request Type**: Only downloads `quote` data (not `trade` data)
- **Symbols**: SPX and SPXW
- **Date Format**: API requires YYYYMMDD, but we store YYYY-MM-DD in database
- **Timeout**: 30 seconds per request
- **Response Format**: CSV with headers

### VS Code Debug Configurations
All download scripts have debug configurations in `.vscode/launch.json`:
- Debug download_expirations.py
- Debug download_strikes.py
- Debug download_dates.py
- Debug download_greeks.py
- Debug retry_failed_dates.py

### Compression Details
- **Library**: zstandard (Python library)
- **Compression level**: 10 (good balance of speed vs size)
- **Typical compression ratios**: 40-100x (depends on data density)
- **File naming**: Original `.csv` becomes `.csv.zst`
- **Space savings**: 147K files → ~6GB compressed vs ~295GB uncompressed
- **Process flow**:
  1. Download CSV from API
  2. Save CSV to disk temporarily
  3. Compress with zstd level 10
  4. Delete original CSV
  5. Store .zst path in database
- **Decompression**: `zstd -d filename.csv.zst` or `zstd -d -c filename.csv.zst | head`

## Important Notes
- Always activate conda environment: `conda activate Theta`
- ThetaData Terminal must be running on localhost:25503
- Scripts handle interrupts gracefully (Ctrl+C)
- Progress is saved incrementally
- No request_type tracking - only quote data is downloaded
- Print statements use `flush=True` for real-time output
- All dates stored in YYYY-MM-DD format internally
- **Multi-process downloads**: download_greeks.py can run multiple instances concurrently
  - Each process independently claims rows via atomic database transactions
  - No coordination needed between processes
  - Safe to start/stop individual processes anytime
  - Database tracks which rows are being processed (in_progress status)
- **File organization**: Monthly folders on external SSD (`/Volumes/X9/data/{symbol}/{year}/{month}/`)
- **Download order**: Latest expirations first (ORDER BY expiration DESC, date DESC)

## Error Logging
- **File**: `errors.log` (created in project root)
- **Format**: `[YYYY-MM-DD HH:MM:SS] Error processing SYMBOL EXPIRATION: error message`
- **Behavior**:
  - `download_strikes.py` and `download_dates.py` log errors to file
  - `download_expirations.py` does NOT log to file (errors caught in API client)
  - When error occurs, script prints error, logs it, and continues with next item
  - Common errors: timeouts, network issues, API unavailability
- **Pattern used in scripts**:
  ```python
  def log_error(error_message: str, log_file: str = "errors.log"):
      timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      with open(log_file, "a") as f:
          f.write(f"[{timestamp}] {error_message}\n")

  # In loop:
  try:
      # API call and processing
  except Exception as e:
      error_msg = f"Error processing {symbol} {expiration}: {e}"
      print(f"  {error_msg}")
      log_error(error_msg)
  ```

## Common Tasks
- **Add new API endpoint**: Follow pattern in `api_client.py` (convert dates, parse CSV)
  - Decide if exceptions should be caught (like expirations) or raised (like strikes/dates/greeks)
  - For bulk data downloads, return raw CSV instead of parsing (like greeks)
- **Add new table**: Update `create_tables()` in `database.py`, add insert/get methods
  - Avoid SQL reserved keywords for table names (e.g., use `available_dates` not `dates`)
- **Add new download script**: Follow pattern from existing scripts, update launch.json
  - If adding error logging, use the pattern from strikes/dates/greeks scripts
- **Change symbols**: Modify the `symbols` list in `download_expirations.py`
- **Retry failed Greeks downloads**: Use SQL to reset failed rows to pending
  - Check `errors.log` for error patterns
  - Reset all failed: See README.md for SQL queries
  - Reset specific row: `UPDATE available_dates SET status='pending', retry_count=0 WHERE symbol='...' AND expiration='...' AND date='...'`
- **Monitor Greeks download progress**: Query database status
  - `SELECT status, COUNT(*) FROM available_dates GROUP BY status;`
  - See README.md for more monitoring queries
- **Change download location**: Edit `base_dir` in `download_greeks.py` get_file_path() function
- **Adjust compression level**: Change `level=10` in `download_greeks.py` ZstdCompressor
- **Increase concurrent processes**: Simply open more terminals and run download_greeks.py
  - Each process safely claims different rows via database locking

## Lessons Learned
- **Table naming**: Avoid SQL reserved keywords (changed `dates` → `available_dates`)
- **Error handling**: Two patterns exist:
  1. API client catches exceptions, returns [] (expirations)
  2. API client raises exceptions, download script catches and logs (strikes, dates, greeks)
- **Minimal code impact**: Keep error logging simple - one function, try-except around loop
- **Be explicit**: Only implement changes that are explicitly requested
- **Multi-process downloads**: Simple independent processes work better than threading
  - SQLite handles concurrency via BEGIN IMMEDIATE transactions
  - No need for locks, queues, or complex coordination
  - Each process just claims next row atomically
- **Compression timing**: Compress BEFORE marking completed
  - Ensures database only tracks successfully compressed files
  - Delete original CSV after compression succeeds
  - Store compressed path before marking complete
- **File organization**: Monthly folders prevent directory with 100K+ files
  - Easier to navigate and manage
  - Better filesystem performance
- **Resume capability**: Database state tracking enables safe resume
  - Stuck rows auto-reset on next run
  - Ctrl+C doesn't lose progress
  - Can stop/start individual processes anytime
