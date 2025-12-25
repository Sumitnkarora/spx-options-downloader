# SPX Options Downloader

A Python tool to download SPX and SPXW options data from ThetaData API and store it in a SQLite database.

## Prerequisites

- Python 3.x with conda
- Conda environment named `Theta`
- ThetaData Terminal running locally on port 25503
- Required Python packages: `requests`

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
└── download_dates.py       # Step 3: Download quote dates
```

## Database Schema

The tool creates a SQLite database at `database/theta_options.db` with three tables:

- **expirations**: Stores all available expiration dates for SPX and SPXW
- **strikes**: Stores all strike prices for each expiration
- **available_dates**: Stores all available quote dates for each expiration

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
