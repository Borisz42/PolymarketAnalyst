import datetime
import os
import glob

# --- Data File Configuration ---
DATA_DIR = "data"
BASE_DATA_FILENAME = "market_data"
DATE_FILENAME_FORMAT = "%Y%m%d" # yyyymmdd

# --- Analysis Configuration ---
# Set to 0 to use the latest available data file for analysis.
# Set to a specific date in yyyymmdd format (e.g., 20231225) to analyze that day's data.
ANALYSIS_DATE = 0

def get_logger_filename():
    """Always returns the filename for the current date, for the data logger."""
    today_str = datetime.datetime.now().strftime(DATE_FILENAME_FORMAT)
    return os.path.join(DATA_DIR, f"{BASE_DATA_FILENAME}_{today_str}.csv")

def get_analysis_filename():
    """
    Returns the filename for analysis.
    If ANALYSIS_DATE is set to a specific yyyymmdd date, it uses that.
    If ANALYSIS_DATE is 0, it finds the latest available data file in the data directory.
    """
    if ANALYSIS_DATE != 0:
        # Use the specific date provided
        date_str = str(ANALYSIS_DATE)
        return os.path.join(DATA_DIR, f"{BASE_DATA_FILENAME}_{date_str}.csv")
    else:
        # Find the latest file in the data directory
        search_pattern = os.path.join(DATA_DIR, f"{BASE_DATA_FILENAME}_*.csv")
        files = glob.glob(search_pattern)
        
        if not files:
            # If no files are found, default to today's filename as a fallback
            return get_logger_filename()
            
        # Find the latest file by sorting alphabetically (since dates are yyyymmdd)
        latest_file = max(files, key=os.path.basename)
        return latest_file

# --- Other Configurations ---
FETCH_INTERVAL_SECONDS = 1
WRITE_INTERVAL_SECONDS = 5
MAX_WORKERS = 15
INITIAL_CAPITAL = 1000.0
SLIPPAGE_SECONDS = 0
