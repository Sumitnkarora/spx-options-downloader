# Claude Context - SPX Options Downloader

## Project Overview
A Python tool that downloads SPX and SPXW options data from ThetaData API and stores it in SQLite. The project follows a three-step download process.

## Environment
- **Conda Environment**: `Theta` (MUST be activated before running any scripts)
- **Python Path**: `/Users/snk/miniforge3/envs/Theta/bin/python`
- **ThetaData API**: Runs locally at `http://localhost:25503`
- **Database**: `database/theta_options.db` (SQLite)

## Architecture

### Core Files
1. **api_client.py** - ThetaData API wrapper
   - `get_expirations(symbol)` → list of (symbol, expiration)
     - Catches exceptions, prints error, returns [] on failure
   - `get_strikes(symbol, expiration)` → list of (symbol, expiration, strike)
     - Raises exceptions (no try-except) - handled by download script
   - `get_dates(symbol, expiration)` → list of (symbol, expiration, date)
     - Raises exceptions (no try-except) - handled by download script
   - Date conversion: YYYY-MM-DD ↔ YYYYMMDD for API calls
   - Returns CSV responses parsed into tuples

2. **database.py** - SQLite database manager
   - Tables: `expirations`, `strikes`, `available_dates`
   - All use `INSERT OR IGNORE` to prevent duplicates
   - Foreign keys enforced between tables
   - Helper methods: `insert_*()`, `get_*_count()`, `get_all_expirations()`

3. **Download Scripts** (must run in order):
   - `download_expirations.py` - Downloads SPX/SPXW expirations
     - No error logging (exceptions caught in API client)
   - `download_strikes.py` - Downloads strikes for each expiration
     - Has error logging: logs to `errors.log` with timestamp
     - Catches exceptions per expiration, logs symbol/expiration info, continues
   - `download_dates.py` - Downloads quote dates for each expiration
     - Has error logging: logs to `errors.log` with timestamp
     - Catches exceptions per expiration, logs symbol/expiration info, continues
   - `retry_failed_dates.py` - Retries specific symbol/expiration combinations that failed
     - Has error logging: logs to `errors.log` with timestamp
     - Processes only combinations listed in FAILED_EXPIRATIONS (hardcoded in script)
     - User edits the list before running

### Database Schema
```sql
expirations: (symbol, expiration) - UNIQUE
strikes: (symbol, expiration, strike) - UNIQUE, FK to expirations
available_dates: (symbol, expiration, date) - UNIQUE, FK to expirations
```

## Execution Workflow
1. User runs `download_expirations.py` → Populates expirations table
2. User runs `download_strikes.py` → Reads expirations, downloads strikes
3. User runs `download_dates.py` → Reads expirations, downloads quote dates
4. (Optional) If downloads fail, user edits `retry_failed_dates.py` with failed combinations and runs it

**Important**: Steps 2 and 3 are independent - they both depend on step 1, but not on each other. Step 4 is only needed if errors occur.

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
- Debug retry_failed_dates.py

## Important Notes
- Always activate conda environment: `conda activate Theta`
- ThetaData Terminal must be running on localhost:25503
- Scripts handle interrupts gracefully (Ctrl+C)
- Progress is saved incrementally
- No request_type tracking - only quote data is downloaded
- Print statements use `flush=True` for real-time output
- All dates stored in YYYY-MM-DD format internally

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
  - Decide if exceptions should be caught (like expirations) or raised (like strikes/dates)
- **Add new table**: Update `create_tables()` in `database.py`, add insert/get methods
  - Avoid SQL reserved keywords for table names (e.g., use `available_dates` not `dates`)
- **Add new download script**: Follow pattern from existing scripts, update launch.json
  - If adding error logging, use the pattern from strikes/dates scripts
- **Change symbols**: Modify the `symbols` list in `download_expirations.py`
- **Retry failed downloads**: Edit `FAILED_EXPIRATIONS` list in `retry_failed_dates.py`, then run it
  - Check `errors.log` for failed symbol/expiration combinations
  - Copy failed combinations into the list and save
  - Run: `python src/retry_failed_dates.py`

## Lessons Learned
- **Table naming**: Avoid SQL reserved keywords (changed `dates` → `available_dates`)
- **Error handling**: Two patterns exist:
  1. API client catches exceptions, returns [] (expirations)
  2. API client raises exceptions, download script catches and logs (strikes, dates)
- **Minimal code impact**: Keep error logging simple - one function, try-except around loop
- **Be explicit**: Only implement changes that are explicitly requested
