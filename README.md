# SPX Options Downloader

A Python tool to download SPX and SPXW options data from ThetaData API and store it in a SQLite database.

## Prerequisites

- Python 3.x with conda
- Conda environment named `Theta`
- ThetaData Terminal running locally on port 25503
- Required Python packages: `requests`, `zstandard`
- External SSD mounted at `/Volumes/X9` (for Greeks data storage)

## Setup

1. Activate the conda environment:
```bash
conda activate Theta
```

2. Ensure ThetaData Terminal is running on `localhost:25503`

## Project Structure

```
src/
├── api_client.py           # ThetaData API client
├── database.py             # SQLite database manager
├── download_expirations.py # Step 1: Download expirations
├── download_strikes.py     # Step 2: Download strikes
├── download_dates.py       # Step 3: Download quote dates
├── download_greeks.py      # Step 4: Download Greeks history data (with compression)
├── migrate_database.py     # Migration: Add download tracking columns
├── migrate_compression.py  # Migration: Add compression tracking column
└── retry_failed_dates.py   # Retry specific failed downloads
```

## Database Schema

The tool creates a SQLite database at `database/theta_options.db` with three tables:

- **expirations**: Stores all available expiration dates for SPX and SPXW
- **strikes**: Stores all strike prices for each expiration
- **available_dates**: Stores all available quote dates for each expiration
  - Includes download tracking: `status`, `started_at`, `completed_at`, `retry_count`, `error_message`
  - Includes compression tracking: `compressed_file_path`

## Usage

**Important:** Activate the conda environment before running any script:
```bash
conda activate Theta
```

The scripts must be run in the following order:

### Step 1: Download Expirations

Downloads all available expiration dates for SPX and SPXW symbols.

```bash
conda activate Theta
python src/download_expirations.py
```

**What it does:**
- Connects to ThetaData API at `http://localhost:25503`
- Fetches all expirations for SPX and SPXW
- Stores them in the `expirations` table

### Step 2: Download Strikes

Downloads all strike prices for each expiration in the database.

```bash
conda activate Theta
python src/download_strikes.py
```

**What it does:**
- Reads all expirations from the database
- For each expiration, fetches all available strike prices
- Stores them in the `strikes` table

**Note:** Run `download_expirations.py` first before running this script.

### Step 3: Download Quote Dates

Downloads all available quote dates for each expiration in the database.

```bash
conda activate Theta
python src/download_dates.py
```

**What it does:**
- Reads all expirations from the database
- For each expiration, fetches all available quote dates
- Stores them in the `available_dates` table

**Note:** Run `download_expirations.py` first before running this script.

### Step 4: Download Greeks History Data (with Compression)

Downloads 5-second interval Greeks history data for all symbol/expiration/date combinations and compresses them with zstd.

**First-time setup (run once):**
```bash
conda activate Theta
python src/migrate_database.py      # Adds download tracking columns
python src/migrate_compression.py   # Adds compression tracking column
```

**Running the downloader:**

Option 1: Single process (sequential)
```bash
conda activate Theta
python src/download_greeks.py
```

Option 2: Multiple processes (4x faster - recommended)
```bash
# Open 4 terminal windows, in each run:
conda activate Theta
python src/download_greeks.py
```

**What it does:**
- Processes rows from `available_dates` table (latest expirations first)
- Downloads Greeks data from ThetaData API for each row
- Saves CSV file to `/Volumes/X9/data/{symbol}/{year}/{month}/`
- Compresses file with zstd level 10 (typically 40-100x compression)
- Deletes original CSV, keeps only `.csv.zst` file
- Tracks progress in database with retry logic (max 3 retries per row)
- Stores compressed file path in database

**Features:**
- **Concurrent processing**: Run multiple instances safely
- **Automatic retry**: Failed downloads retry up to 3 times
- **Resume capability**: Stop (Ctrl+C) and resume anytime
- **Progress tracking**: Database tracks pending/in_progress/completed/failed status
- **Space efficient**: 40-100x compression with zstd (147K files → ~6GB vs ~295GB uncompressed)

**File organization:**
```
/Volumes/X9/data/
├── SPX/
│   ├── 2024/
│   │   └── 07/
│   │       └── SPX_20240719_20240709_5s.csv.zst
│   └── 2025/
│       └── 12/
│           └── SPX_20311219_20251224_5s.csv.zst
└── SPXW/
    └── 2024/
        └── 07/
            └── SPXW_20880710_20240709_5s.csv.zst
```

**Monitoring progress:**
```bash
# Check status breakdown
sqlite3 database/theta_options.db "SELECT status, COUNT(*) FROM available_dates GROUP BY status;"

# Example output:
# completed|1234
# in_progress|4
# pending|146486
# failed|0
```

**Decompressing files:**
```bash
# Decompress a single file
zstd -d filename.csv.zst

# View compressed file without decompressing
zstd -d -c filename.csv.zst | head -10
```

**Estimated runtime:**
- Single process: ~4-8 days for 147,724 rows
- 4 processes: ~2-4 days
- 8 processes: ~1-2 days

### Retrying Failed Downloads

If some downloads fail due to timeouts or API errors, you can retry specific symbol/expiration combinations.

```bash
conda activate Theta
python src/retry_failed_dates.py
```

**What it does:**
- Retries downloading quote dates for specific expirations that failed
- Uses the same error logging to `errors.log`
- Safe to run multiple times (duplicates are ignored)

**How to use:**
1. Check `errors.log` for failed downloads
2. Edit `src/retry_failed_dates.py` and update the `FAILED_EXPIRATIONS` list with the combinations you want to retry
3. Run the script

**Example:**
```python
FAILED_EXPIRATIONS = [
    ("SPXW", "2019-07-08"),
    ("SPXW", "2019-07-10"),
    ("SPX", "2012-06-16"),
]
```

## Running Individual Scripts

Each script can be run independently as long as the prerequisites are met.

**Remember to activate the conda environment first:**

### Download Expirations Only
```bash
conda activate Theta
python src/download_expirations.py
```

### Download Strikes Only
```bash
# Requires expirations to be downloaded first
conda activate Theta
python src/download_strikes.py
```

### Download Dates Only
```bash
# Requires expirations to be downloaded first
conda activate Theta
python src/download_dates.py
```

## Debugging in VS Code

The project includes VS Code debug configurations for each script:

1. Open the project in VS Code
2. Go to the Debug panel (Cmd/Ctrl + Shift + D)
3. Select one of the following configurations:
   - `Debug download_expirations.py`
   - `Debug download_strikes.py`
   - `Debug download_dates.py`
   - `Debug download_greeks.py`
   - `Debug retry_failed_dates.py`
4. Press F5 to start debugging

## Error Handling

- All scripts handle keyboard interrupts (Ctrl+C) gracefully
- Progress is saved incrementally, so you can resume if interrupted
- Duplicate entries are automatically ignored using `INSERT OR IGNORE`
- API errors are caught and logged without stopping the entire process

## Database Location

The SQLite database is created at:
```
database/theta_options.db
```

You can view the data using any SQLite browser or query it directly using Python's sqlite3 module.

## Useful SQL Queries

### Reset Download Status

**Mark all rows back to pending status:**
```sql
sqlite3 database/theta_options.db "UPDATE available_dates SET status='pending', retry_count=0, error_message=NULL WHERE status IN ('failed', 'in_progress');"
```

**Mark one specific row as pending:**
```sql
sqlite3 database/theta_options.db "UPDATE available_dates SET status='pending', retry_count=0, error_message=NULL WHERE symbol='SPXW' AND expiration='2024-11-08' AND date='2024-11-04';"
```

**Mark all failed rows as pending (to retry them):**
```sql
sqlite3 database/theta_options.db "UPDATE available_dates SET status='pending', retry_count=0, error_message=NULL WHERE status='failed';"
```

**Reset stuck in_progress rows (older than 30 minutes):**
```sql
sqlite3 database/theta_options.db "UPDATE available_dates SET status='pending', error_message='Reset from stuck in_progress state' WHERE status='in_progress' AND started_at < datetime('now', '-30 minutes');"
```

### Monitor Progress

**Check status breakdown:**
```sql
sqlite3 database/theta_options.db "SELECT status, COUNT(*) FROM available_dates GROUP BY status;"
```

**View failed rows with error messages:**
```sql
sqlite3 database/theta_options.db "SELECT symbol, expiration, date, error_message FROM available_dates WHERE status='failed' LIMIT 10;"
```

**Group errors by message:**
```sql
sqlite3 database/theta_options.db "SELECT error_message, COUNT(*) as count FROM available_dates WHERE status='failed' GROUP BY error_message ORDER BY count DESC;"
```

**Check which rows are currently being processed:**
```sql
sqlite3 database/theta_options.db "SELECT symbol, expiration, date, started_at FROM available_dates WHERE status='in_progress';"
```
