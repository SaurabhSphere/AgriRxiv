import json
import os
import re
import time
import logging
import shutil
from pathlib import Path
from seleniumbase import SB

# --- Configuration ---
JSON_INPUT_FILE = "agrirxiv_final_data.json"
# We download to a temp location first, then move to the final folder
DOWNLOAD_DIR = Path(r"C:\Users\Saurabh-CSIO\Desktop\Scrapy\downloaded_files")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class PDFDownloader:
    def __init__(self, json_file):
        self.json_file = json_file
        self.data = self.load_json()

    def load_json(self):
        if not os.path.exists(self.json_file):
            logger.error(f"File {self.json_file} not found!")
            return []
        with open(self.json_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def sanitize_filename(self, doi):
        """Creates a Windows-safe filename from the DOI."""
        return re.sub(r'[^a-zA-Z0-9._]', '_', doi) + ".pdf"

    def start_downloading(self):
        pending = [i for i in self.data if i.get("is_pdf_available") and i.get("pdf_url")]
        if not pending:
            logger.info("No pending PDF downloads found.")
            return

        logger.info(f"Found {len(pending)} PDFs to process.")

        # Launching SB with uc=True for Cloudflare bypass
        with SB(uc=True, test=True, locale="en") as sb:
            for item in pending:
                doi = item['doi']
                pdf_url = item['pdf_url']
                safe_name = self.sanitize_filename(doi)
                final_path = DOWNLOAD_DIR / safe_name

                if final_path.exists():
                    continue

                logger.info(f"Processing DOI: {doi}")
                
                try:
                    # 1. Open the URL to establish/refresh the session
                    sb.uc_open_with_reconnect(pdf_url, 6)
                    
                    # 2. Handle Human Verification if it appears
                    if "Cloudflare" in sb.get_page_title():
                        logger.warning("Cloudflare challenge detected. Waiting...")
                        sb.sleep(8) 

                    # 3. USE BROWSER TO DOWNLOAD (Avoids 403 Requests error)
                    # This saves the file to the browser's default download folder
                    sb.download_file(pdf_url)
                    sb.sleep(5) # Wait for file to finish writing to disk

                    # 4. Find the downloaded file and move it
                    # SeleniumBase saves to its own 'downloaded_files' temp folder
                    # We locate the most recent file and move/rename it to your path
                    downloaded_files = sorted(
                        Path("downloaded_files").glob("*"), 
                        key=os.path.getmtime
                    )
                    
                    if downloaded_files:
                        newest_file = downloaded_files[-1]
                        shutil.move(str(newest_file), str(final_path))
                        item["pdf_local_path"] = str(final_path.absolute())
                        logger.info(f"Successfully saved: {safe_name}")
                        
                        # Save JSON progress incrementally
                        self.save_json()
                    else:
                        logger.error(f"File was not found in browser download folder for {doi}")

                    # Respect crawl-delay
                    sb.sleep(3)

                except Exception as e:
                    logger.error(f"Error for {doi}: {e}")

    def save_json(self):
        with open(self.json_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    PDFDownloader(JSON_INPUT_FILE).start_downloading()