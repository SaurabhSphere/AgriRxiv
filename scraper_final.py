import json
import logging
import os
import re
import requests
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from seleniumbase import SB

# --- Configuration ---
SCRAPER_CONFIG = {
    "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate&target=articles-chapters&content=articlesChapters&startPage=0&pageSize=100",
    "base_url": "https://www.cabidigitallibrary.org",
    "max_pages": 100,
    "crawl_delay": 1.5  # Added a 1.5s delay to safely respect Crawl-delay: 1
}

OUTPUT_FILE = Path("agrirxiv_final_data.json")
DOWNLOAD_DIR = Path(r"C:\Users\Saurabh-CSIO\Desktop\Scrapy\downloaded_files")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
        self.load_existing_data()

    def load_existing_data(self):
        if OUTPUT_FILE.exists():
            try:
                with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                    self.articles = json.load(f)
                    self.seen_dois = {item["doi"] for item in self.articles}
                logger.info(f"STEP: Resume - Loaded {len(self.seen_dois)} items from JSON.")
            except Exception as e:
                logger.error(f"STEP: Resume - Failed to load data: {e}")

    def download_pdf_securely(self, sb, url, doi):
        """Downloads PDF ONLY if it does not already exist."""
        clean_name = re.sub(r'[^a-zA-Z0-9._]', '_', doi)
        target_path = DOWNLOAD_DIR / f"{clean_name}.pdf"

        if target_path.exists():
            logger.info(f"STEP: PDF - File already exists, skipping: {target_path.name}")
            return str(target_path.absolute())

        try:
            # Respect crawl delay before direct request
            time.sleep(SCRAPER_CONFIG["crawl_delay"])
            
            cookies = {c['name']: c['value'] for c in sb.get_cookies()}
            headers = {
                "User-Agent": sb.get_user_agent(),
                "Referer": sb.get_current_url()
            }
            
            response = requests.get(url, cookies=cookies, headers=headers, stream=True, timeout=45)
            
            if response.status_code == 200:
                with open(target_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"STEP: PDF - Successfully saved: {target_path.name}")
                return str(target_path.absolute())
        except Exception as e:
            logger.error(f"STEP: PDF - Download error for {doi}: {e}")
        return None

    def scrape_article_details(self, sb, article_info):
        try:
            logger.info(f"STEP: DETAILS - Navigating to: {article_info['link']}")
            
            # Navigate with delay
            sb.sleep(SCRAPER_CONFIG["crawl_delay"])
            sb.uc_open_with_reconnect(article_info["link"], 5)
            
            # Wait for content to render
            sb.sleep(5) 
            
            soup = BeautifulSoup(sb.get_page_source(), "html.parser")
            abstract_div = soup.select_one("#summary-abstract div[role='paragraph']")
            
            authors = []
            author_items = soup.select('span[property="author"][role="listitem"]')
            for item in author_items:
                given = item.select_one('[property="givenName"]')
                family = item.select_one('[property="familyName"]')
                if given and family:
                    authors.append(f"{given.get_text(strip=True)} {family.get_text(strip=True)}")
                else:
                    name_text = item.get_text(strip=True)
                    if name_text:
                        name_text = re.split(r'\S+@\S+', name_text)[0].strip()
                        authors.append(name_text)

            date_div = soup.select_one(".meta-panel__onlineDate")
            publish_date = date_div.get_text(strip=True) if date_div else None

            data = {
                "abstract": abstract_div.get_text(strip=True) if abstract_div else None,
                "authors": list(dict.fromkeys(authors)),
                "publish_date": publish_date,
                "is_pdf_available": False,
                "pdf_url": None,
                "pdf_local_path": None,
                "status": "incomplete"
            }

            pdf_btn = "a.btn--pdf"
            if sb.is_element_visible(pdf_btn):
                data["is_pdf_available"] = True
                viewer_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(pdf_btn, "href"))
                
                # Navigate to viewer with delay
                sb.sleep(SCRAPER_CONFIG["crawl_delay"])
                sb.uc_open_with_reconnect(viewer_url, 4)
                sb.sleep(7) 
                
                download_btn = "a.navbar-download"
                if sb.is_element_visible(download_btn):
                    final_pdf_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(download_btn, "href"))
                    data["pdf_url"] = final_pdf_url
                    
                    # Direct download function handles its own delay
                    local_path = self.download_pdf_securely(sb, final_pdf_url, article_info['doi'])
                    if local_path:
                        data["pdf_local_path"] = local_path
                        data["status"] = "complete"
            else:
                data["status"] = "complete"
            
            return data
        except Exception as e:
            logger.error(f"STEP: DETAILS - Error: {e}")
            return None

    def run(self):
        try:
            with SB(uc=True, test=True, locale="en") as sb:
                logger.info("STEP: INIT - Starting Scraper")
                sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
                
                page = 1
                while page <= SCRAPER_CONFIG["max_pages"]:
                    logger.info(f"STEP: PAGINATION - Search Page {page}")
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

                    skipped = sum(1 for item in current_page_items if item["doi"] in self.seen_dois)
                    new_items = len(current_page_items) - skipped
                    
                    if new_items == 0:
                        logger.info(f"STEP: SKIP - Page {page} (All {len(current_page_items)} already exist)")
                    else:
                        logger.info(f"STEP: LIST - Page {page} has {new_items} new items")

                    for i, item in enumerate(current_page_items):
                        if item["doi"] in self.seen_dois: continue
                        
                        logger.info(f"STEP: MAIN - {i+1}/{len(current_page_items)} | DOI: {item['doi']}")
                        
                        # Detail scraping function handles its own delays
                        details = self.scrape_article_details(sb, item)
                        if details:
                            item.update(details)
                            item["scraped_at"] = datetime.now().isoformat()
                            self.articles.append(item)
                            self.seen_dois.add(item["doi"])
                            
                            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                                json.dump(self.articles, f, indent=4, ensure_ascii=False)
                        
                        # Respect delay before going back to search
                        sb.sleep(SCRAPER_CONFIG["crawl_delay"])
                        sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 5)
                        sb.wait_for_element("li.search__item", timeout=20)

                    next_btn = "a.pagination__btn--next"
                    if sb.is_element_visible(next_btn):
                        # Respect delay before pagination
                        sb.sleep(SCRAPER_CONFIG["crawl_delay"])
                        sb.uc_click(next_btn, reconnect_time=5)
                        page += 1
                        sb.sleep(4)
                    else: break
        except Exception as e:
            logger.critical(f"STEP: FATAL - Error: {e}")

if __name__ == "__main__":
    AgriRxivUltimateScraper().run()