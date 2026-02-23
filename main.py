import schedule
import time
from downloader import download_pdfs
from monitor import check_for_changes

print("=== S&P Financial Agent Starting ===")

# Run immediately on startup
download_pdfs()
check_for_changes()

# Schedule recurring runs
schedule.every().day.at("08:00").do(download_pdfs)
schedule.every(2).hours.do(check_for_changes)

print("\n[SCHEDULER] Running... checking every 2 hours.")
print("[SCHEDULER] PDF download scheduled daily at 08:00.")
print("[SCHEDULER] Press CTRL+C to stop.\n")

while True:
    schedule.run_pending()
    time.sleep(60)