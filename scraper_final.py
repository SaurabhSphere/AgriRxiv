# import json
# import logging
# import random
# from datetime import datetime
# from pathlib import Path
# from bs4 import BeautifulSoup
# from seleniumbase import SB

# # --- Configuration ---
# SCRAPER_CONFIG = {
#     "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate&startPage=0&pageSize=100",
#     "base_url": "https://www.cabidigitallibrary.org",
#     "max_pages": 5,
# }

# OUTPUT_FILE = Path("agrirxiv_full_data.json")

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
# logger = logging.getLogger(__name__)

# class AgriRxivAutoBypassScraper:
#     def __init__(self):
#         self.articles = []
#         self.seen_dois = set()

#     def scrape_items(self, html):
#         soup = BeautifulSoup(html, "html.parser")
#         items = soup.select("li.search__item")
#         count = 0
#         for item in items:
#             link_tag = item.select_one(".issue-item__title a")
#             if not link_tag: continue

#             href = link_tag.get("href", "")
#             doi = href.split("/doi/")[-1] if "/doi/" in href else href
            
#             if doi not in self.seen_dois:
#                 title = link_tag.get_text(strip=True)
#                 date_tag = item.select_one(".issue-item__header span:nth-last-child(1)")
                
#                 self.articles.append({
#                     "doi": doi,
#                     "title": title,
#                     "link": f"{SCRAPER_CONFIG['base_url']}{href}" if href.startswith("/") else href,
#                     "date": date_tag.get_text(strip=True) if date_tag else None,
#                     "scraped_at": datetime.now().isoformat()
#                 })
#                 self.seen_dois.add(doi)
#                 count += 1
#         return count

#     def run(self):
#         # uc_reconnect=True is key for continuous Cloudflare bypass
#         with SB(uc=True, test=True, locale="en") as sb:
#             logger.info("🚀 Launching Undetected Browser...")
            
#             # Open with automated verification handling
#             sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
            
#             # Handle potential initial Turnstile box
#             try:
#                 sb.uc_gui_handle_captcha()
#             except:
#                 pass

#             # Initial wait for the first page
#             sb.wait_for_element("li.search__item", timeout=30)
#             logger.info("✅ Initial verification bypassed.")

#             for current_page in range(1, SCRAPER_CONFIG["max_pages"] + 1):
#                 logger.info(f"📄 Processing Page {current_page}...")
                
#                 # Check for re-verification screens that sometimes pop up between pages
#                 if "Just a moment" in sb.get_title():
#                     logger.info("🛡️ Cloudflare re-challenge detected. Reconnecting...")
#                     sb.uc_reconnect(10)

#                 # Extract and Save
#                 new_count = self.scrape_items(sb.get_page_source())
#                 logger.info(f"✨ Found {new_count} new items. Total: {len(self.articles)}")
                
#                 with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#                     json.dump(self.articles, f, indent=4, ensure_ascii=False)

#                 # Behavior: Wait like a human
#                 sb.sleep(random.uniform(5, 8))
                
#                 if current_page >= SCRAPER_CONFIG["max_pages"]:
#                     logger.info("Reached the page limit set in config.")
#                     break

#                 # Robust Pagination Logic
#                 next_btn = "a.pagination__btn--next"
#                 try:
#                     # Check visibility without crashing
#                     if sb.is_element_visible(next_btn):
#                         logger.info("Moving to next page...")
#                         sb.scroll_to(next_btn)
#                         sb.sleep(1)
#                         # uc_click handles the disconnect/reconnect automatically
#                         sb.uc_click(next_btn, reconnect_time=5)
#                     else:
#                         logger.info("Next button not visible. Likely reached the last page.")
#                         break
#                 except Exception as e:
#                     logger.warning(f"Could not click next button: {e}. Ending scrape.")
#                     break

# if __name__ == "__main__":
#     scraper = AgriRxivAutoBypassScraper()
#     scraper.run()






import json
import logging
import random
import os
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from seleniumbase import SB

# --- Configuration ---
SCRAPER_CONFIG = {
    "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate",
    "base_url": "https://www.cabidigitallibrary.org",
    "max_pages": 3,
}

# Directories
OUTPUT_FILE = Path("agrirxiv_detailed_data.json")
PDF_DIR = Path("downloaded_pdfs")
PDF_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

class AgriRxivDeepScraper:
    def __init__(self):
        self.articles = []
        self.session = requests.Session()

    def sync_session(self, sb):
        """Sync cookies from Selenium to Requests for direct downloading"""
        cookies = sb.get_cookies()
        for cookie in cookies:
            self.session.cookies.set(cookie['name'], cookie['value'])

    def download_pdf_file(self, url, doi):
        """Downloads the PDF and returns the local path"""
        try:
            filename = doi.replace(".", "_").replace("/", "_") + ".pdf"
            path = PDF_DIR / filename
            
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                with open(path, "wb") as f:
                    f.write(response.content)
                return str(path.absolute())
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
        return None

    def extract_full_details(self, sb, item):
        """Parses the article page and handles PDF logic"""
        html = sb.get_page_source()
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Basic Metadata
        abstract_div = soup.select_one("#summary-abstract div[role='paragraph']")
        details = {
            "abstract": abstract_div.get_text(strip=True) if abstract_div else "No abstract available",
            "is_pdf_available": False,
            "pdf_local_path": None,
            "pdf_url": None
        }

        # 2. PDF Logic
        # Look for the PDF/EPUB button on the article page
        pdf_btn_selector = "a.btn--pdf" 
        if sb.is_element_visible(pdf_btn_selector):
            details["is_pdf_available"] = True
            viewer_url = sb.get_attribute(pdf_btn_selector, "href")
            
            # Navigate to the large PDF viewer page
            logger.info("Opening PDF viewer...")
            sb.open(f"{SCRAPER_CONFIG['base_url']}{viewer_url}")
            sb.sleep(3) # Wait for viewer to load the internal download button
            
            # Find the actual download link in the viewer (the HTML you provided)
            # Selector targets the link with class 'navbar-download'
            final_link_selector = "a.navbar-download"
            if sb.is_element_visible(final_link_selector):
                final_pdf_url = sb.get_attribute(final_link_selector, "href")
                full_pdf_url = f"{SCRAPER_CONFIG['base_url']}{final_pdf_url}"
                details["pdf_url"] = full_pdf_url
                
                # Sync cookies and download
                self.sync_session(sb)
                local_path = self.download_pdf_file(full_pdf_url, item['doi'])
                details["pdf_local_path"] = local_path
            
            # Go back to the article page
            sb.go_back()

        return details

    def get_list_items(self, html):
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("li.search__item")
        results = []
        for item in items:
            link_tag = item.select_one(".issue-item__title a")
            if not link_tag: continue
            href = link_tag.get("href", "")
            results.append({
                "title": link_tag.get_text(strip=True),
                "link": f"{SCRAPER_CONFIG['base_url']}{href}" if href.startswith("/") else href,
                "doi": href.split("/doi/")[-1] if "/doi/" in href else "unknown"
            })
        return results

    def run(self):
        with SB(uc=True, test=True) as sb:
            sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
            
            page_num = 1
            while page_num <= SCRAPER_CONFIG["max_pages"]:
                sb.wait_for_element("li.search__item", timeout=20)
                current_page_list = self.get_list_items(sb.get_page_source())
                
                for i, item in enumerate(current_page_list):
                    logger.info(f"🔍 Article {i+1}/{len(current_page_list)}: {item['title'][:50]}...")
                    
                    sb.uc_open_with_reconnect(item['link'], 5)
                    deep_details = self.extract_full_details(sb, item)
                    item.update(deep_details)
                    
                    self.articles.append(item)
                    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(self.articles, f, indent=4, ensure_ascii=False)
                    
                    sb.go_back()
                    sb.wait_for_element("li.search__item", timeout=20)

                next_btn = "a.pagination__btn--next"
                if sb.is_element_visible(next_btn):
                    sb.uc_click(next_btn, reconnect_time=5)
                    page_num += 1
                else:
                    break

if __name__ == "__main__":
    scraper = AgriRxivDeepScraper()
    scraper.run()










# import json
# import logging
# import random
# from datetime import datetime
# from pathlib import Path
# from bs4 import BeautifulSoup
# from seleniumbase import SB

# # --- Configuration ---
# # --- Configuration ---
# SCRAPER_CONFIG = {
#     "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate&startPage=0&pageSize=100",
#     "base_url": "https://www.cabidigitallibrary.org",
#     "max_pages": 100,  # Increased to ensure we get all records
# }

# OUTPUT_FILE = Path("agrirxiv_full_data.json")

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
# logger = logging.getLogger(__name__)

# class AgriRxivUltimateScraper:
#     def __init__(self):
#         self.articles = []
#         self.seen_dois = set()

#     def scrape_items(self, html):
#         soup = BeautifulSoup(html, "html.parser")
#         items = soup.select("li.search__item")
#         count = 0
#         for item in items:
#             link_tag = item.select_one(".issue-item__title a")
#             if not link_tag:
#                 continue

#             href = link_tag.get("href", "")
#             doi = href.split("/doi/")[-1] if "/doi/" in href else href
            
#             if doi not in self.seen_dois:
#                 title = link_tag.get_text(strip=True)
#                 date_tag = item.select_one(".issue-item__header span:nth-last-child(1)")
                
#                 # --- Author Extraction Logic ---
#                 authors = []
#                 author_container = item.select_one(".issue-item__authors")
#                 if author_container:
#                     # Find all individual author links
#                     author_links = author_container.select("li span.hlFld-ContribAuthor a")
#                     for auth in author_links:
#                         name = auth.get_text(strip=True)
#                         if name:
#                             authors.append(name)
#                 # -------------------------------

#                 self.articles.append({
#                     "doi": doi,
#                     "title": title,
#                     "authors": authors,  # Added authors list here
#                     "link": f"{SCRAPER_CONFIG['base_url']}{href}" if href.startswith("/") else href,
#                     "date": date_tag.get_text(strip=True) if date_tag else None,
#                     "scraped_at": datetime.now().isoformat()
#                 })
#                 self.seen_dois.add(doi)
#                 count += 1
#         return count

#     def run(self):
#         # uc=True is the 'Undetected' mode to bypass Cloudflare
#         with SB(uc=True, test=True, locale="en") as sb:
#             logger.info("🚀 Starting Automated Bypass...")
#             sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
            
#             try:
#                 sb.uc_gui_handle_captcha()
#             except:
#                 pass

#             sb.wait_for_element("li.search__item", timeout=30)
            
#             page_num = 1
#             while page_num <= SCRAPER_CONFIG["max_pages"]:
#                 logger.info(f"📄 Processing Page {page_num}...")
                
#                 if "Just a moment" in sb.get_title():
#                     logger.info("🛡️ Re-verification triggered. Reconnecting...")
#                     sb.uc_reconnect(10)

#                 # Wait for results to actually render
#                 sb.wait_for_element("li.search__item", timeout=15)
                
#                 new_count = self.scrape_items(sb.get_page_source())
#                 logger.info(f"✨ Found {new_count} new items (Total: {len(self.articles)})")
                
#                 # Progress Save
#                 with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#                     json.dump(self.articles, f, indent=4, ensure_ascii=False)

#                 next_btn = "a.pagination__btn--next"
#                 if sb.is_element_visible(next_btn):
#                     logger.info("Moving to next page...")
#                     sb.scroll_to(next_btn)
#                     sb.sleep(random.uniform(4, 7))
#                     sb.uc_click(next_btn, reconnect_time=5)
#                     page_num += 1
#                 else:
#                     # One final check to see if the last page loaded content but removed the button
#                     sb.sleep(3)
#                     final_check = self.scrape_items(sb.get_page_source())
#                     if final_check > 0:
#                         logger.info(f"Captured {final_check} items from the absolute last page.")
                    
#                     logger.info("✅ Finished all pages.")
#                     break

# if __name__ == "__main__":
#     scraper = AgriRxivUltimateScraper()
#     scraper.run()