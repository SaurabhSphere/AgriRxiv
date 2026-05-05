import json
import logging
import os
import re
import requests
import shutil
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from seleniumbase import SB

# --- Configuration ---
SCRAPER_CONFIG = {
    # "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate",
    "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate&target=articles-chapters&content=articlesChapters&startPage=0&pageSize=100",
    "base_url": "https://www.cabidigitallibrary.org",
    "max_pages": 100,
    "crawl_delay": 2,  # Standard crawl delay in seconds to prevent IP blocking
}

# --- File System Setup ---
OUTPUT_FILE = Path("agrirxiv_final_data.json")
DOWNLOAD_DIR = Path(r"C:\Users\Saurabh-CSIO\Desktop\Scrapy\downloaded_files")
BACKUP_DIR = Path(r"C:\Users\Saurabh-CSIO\Desktop\Scrapy\downloaded_files_backup")

def setup_safe_directories():
    """Create directories safely without deleting existing files."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

setup_safe_directories()

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper_debug.log", encoding="utf-8"), 
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AgriRxivUltimateScraper:
    def __init__(self):
        self.articles = []
        self.seen_dois = set()
        self.backup_existing_downloads()
        self.load_existing_data()

    def backup_existing_downloads(self):
        """Create a backup of existing PDF downloads before processing starts."""
        if DOWNLOAD_DIR.exists() and any(DOWNLOAD_DIR.glob("*.pdf")):
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = BACKUP_DIR / f"backup_{timestamp}"
                
                # Copy all existing PDFs to backup
                for pdf_file in DOWNLOAD_DIR.glob("*.pdf"):
                    shutil.copy2(pdf_file, backup_path / pdf_file.name)
                
                logger.info(f"STEP: BACKUP - Successfully backed up existing PDFs to {backup_path}")
            except Exception as e:
                logger.warning(f"STEP: BACKUP - Could not backup PDFs: {e}")

    def load_existing_data(self):
        if OUTPUT_FILE.exists():
            try:
                with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                    self.articles = json.load(f)
                    self.seen_dois = {item["doi"] for item in self.articles}
                logger.info(f"STEP: Resume - Loaded {len(self.seen_dois)} items from existing JSON.")
            except Exception as e:
                logger.error(f"STEP: Resume - Failed to load existing data: {e}")

    def apply_crawl_delay(self):
        """Apply crawl delay to prevent IP blocking."""
        delay = SCRAPER_CONFIG.get("crawl_delay", 2)
        logger.info(f"STEP: CRAWL_DELAY - Waiting {delay} seconds before next request")
        time.sleep(delay)

    def scrape_article_details(self, sb, article_info):
        try:
            logger.info(f"STEP: DETAILS - Navigating to article: {article_info['link']}")
            sb.uc_open_with_reconnect(article_info["link"], 5)
            sb.sleep(5) 
            
            soup = BeautifulSoup(sb.get_page_source(), "html.parser")
            
            # 1. Extract Abstract
            logger.info("STEP: DETAILS - Extracting abstract text")
            abstract_div = soup.select_one("#summary-abstract div[role='paragraph']")
            
            # 2. Extract Authors (Updated for provided HTML)
            logger.info("STEP: DETAILS - Attempting author extraction")
            authors = []
            
            # Target the specific role="listitem" and extract combined names
            author_items = soup.select('span[property="author"][role="listitem"]')
            for item in author_items:
                given = item.select_one('[property="givenName"]')
                family = item.select_one('[property="familyName"]')
                if given and family:
                    full_name = f"{given.get_text(strip=True)} {family.get_text(strip=True)}"
                    authors.append(full_name)
                else:
                    # Fallback for plain text links within authors span
                    name_text = item.get_text(strip=True)
                    if name_text:
                        # Clean up any email addresses if they exist in the string
                        name_text = re.split(r'\S+@\S+', name_text)[0].strip()
                        authors.append(name_text)

            logger.info(f"STEP: DETAILS - Found {len(authors)} authors: {', '.join(authors)}")
            
            # 3. Extract Publish Date
            date_div = soup.select_one(".meta-panel__onlineDate")
            publish_date = date_div.get_text(strip=True) if date_div else None

            data = {
                "abstract": abstract_div.get_text(strip=True) if abstract_div else None,
                "authors": list(dict.fromkeys(authors)),
                "publish_date": publish_date,
                "is_pdf_available": False,
                "pdf_url": None,
                "status": "complete"
            }

            # 4. Handle PDF Logic - Extract URL only, no download
            pdf_btn = "a.btn--pdf"
            if sb.is_element_visible(pdf_btn):
                logger.info("STEP: PDF - Found PDF button, extracting URL")
                data["is_pdf_available"] = True
                viewer_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(pdf_btn, "href"))
                
                # Navigate to viewer to get the actual download link
                sb.uc_open_with_reconnect(viewer_url, 4)
                sb.sleep(3) 
                
                download_btn = "a.navbar-download"
                if sb.is_element_visible(download_btn):
                    final_pdf_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(download_btn, "href"))
                    data["pdf_url"] = final_pdf_url
                    logger.info(f"STEP: PDF - Extracted PDF URL for DOI: {article_info['doi']} - {final_pdf_url}")
                else:
                    logger.warning("STEP: PDF - Viewer opened but download button not found")
            else:
                logger.info("STEP: PDF - No PDF button available for this article")
            
            return data
        except Exception as e:
            logger.error(f"STEP: DETAILS - Critical error in article logic: {e}")
            return None

    def run(self):
        try:
            with SB(uc=True, test=True, locale="en") as sb:
                logger.info("STEP: INIT - Starting SeleniumBase Instance")
                sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
                
                page = 1
                while page <= SCRAPER_CONFIG["max_pages"]:
                    logger.info(f"STEP: PAGINATION - Processing Search Page {page}")
                    sb.wait_for_element("li.search__item", timeout=30)
                    
                    elements = sb.find_elements(".issue-item__title a")
                    current_page_items = []
                    for a in elements:
                        href = a.get_attribute("href")
                        current_page_items.append({
                            "title": a.text.strip(),
                            "link": urljoin(SCRAPER_CONFIG["base_url"], href),
                            "doi": href.split("/doi/")[-1]
                        })

                    for i, item in enumerate(current_page_items):
                        if item["doi"] in self.seen_dois:
                            continue
                        
                        logger.info(f"STEP: MAIN - Starting item {i+1}/{len(current_page_items)} | DOI: {item['doi']}")
                        
                        details = self.scrape_article_details(sb, item)
                        if details:
                            item.update(details)
                            item["scraped_at"] = datetime.now().isoformat()
                            self.articles.append(item)
                            self.seen_dois.add(item["doi"])
                            
                            logger.info(f"STEP: SAVE - Updating {OUTPUT_FILE}")
                            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                                json.dump(self.articles, f, indent=4, ensure_ascii=False)
                        
                        # Apply crawl delay before returning to search results
                        self.apply_crawl_delay()
                        
                        logger.info("STEP: MAIN - Returning to search results")
                        sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 5)
                        sb.wait_for_element("li.search__item", timeout=20)

                    next_btn = "a.pagination__btn--next"
                    if sb.is_element_visible(next_btn):
                        logger.info("STEP: PAGINATION - Clicking NEXT button")
                        sb.uc_click(next_btn, reconnect_time=5)
                        page += 1
                        # Apply crawl delay before next page
                        self.apply_crawl_delay()
                    else:
                        break
        except Exception as e:
            logger.critical(f"STEP: FATAL - Browser instance failed: {e}")

if __name__ == "__main__":
    AgriRxivUltimateScraper().run()