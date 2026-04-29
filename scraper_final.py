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




# import json
# import logging
# import random
# import requests
# from datetime import datetime
# from pathlib import Path
# from urllib.parse import urljoin
# from bs4 import BeautifulSoup
# from seleniumbase import SB

# # --- Configuration ---
# SCRAPER_CONFIG = {
#     "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate",
#     "base_url": "https://www.cabidigitallibrary.org",
#     "max_pages": 100,
# }

# OUTPUT_FILE = Path("agrirxiv_final_data.json")
# PDF_DIR = Path("downloaded_pdfs")
# PDF_DIR.mkdir(exist_ok=True)

# logging.basicConfig(
#     level=logging.INFO, 
#     format="%(asctime)s - %(levelname)s - %(message)s",
#     handlers=[logging.FileHandler("scraper_debug.log"), logging.StreamHandler()]
# )
# logger = logging.getLogger(__name__)

# class AgriRxivUltimateScraper:
#     def __init__(self):
#         self.articles = []
#         self.seen_dois = set()
#         self.session = requests.Session()

#     def sync_session_cookies(self, sb):
#         """Copies browser cookies to requests session for secure PDF downloading"""
#         cookies = sb.get_cookies()
#         for cookie in cookies:
#             self.session.cookies.set(cookie['name'], cookie['value'])

#     def download_pdf(self, url, doi):
#         """Downloads PDF and returns local file path"""
#         try:
#             safe_name = doi.replace(".", "_").replace("/", "_") + ".pdf"
#             file_path = PDF_DIR / safe_name
            
#             # Using the synced session to bypass Cloudflare on the file request
#             response = self.session.get(url, timeout=30, stream=True)
#             if response.status_code == 200:
#                 with open(file_path, "wb") as f:
#                     for chunk in response.iter_content(chunk_size=8192):
#                         f.write(chunk)
#                 return str(file_path.absolute())
#         except Exception as e:
#             logger.error(f"Download failed for {doi}: {e}")
#         return None

#     def get_list_page_items(self, html):
#         soup = BeautifulSoup(html, "html.parser")
#         items = soup.select("li.search__item")
#         found = []
#         for item in items:
#             link_tag = item.select_one(".issue-item__title a")
#             if not link_tag: continue
#             raw_href = link_tag.get("href", "")
#             full_link = urljoin(SCRAPER_CONFIG["base_url"], raw_href)
#             doi = raw_href.split("/doi/")[-1] if "/doi/" in raw_href else "unknown"
#             found.append({"title": link_tag.get_text(strip=True), "link": full_link, "doi": doi})
#         return found

#     def scrape_article_details(self, sb, article_info):
#         """Extracts data from inside the article page"""
#         sb.uc_open_with_reconnect(article_info["link"], 4)
#         sb.sleep(3) # Wait for all dynamic elements (authors/date)
        
#         soup = BeautifulSoup(sb.get_page_source(), "html.parser")
        
#         # 1. Extract Abstract
#         abstract_div = soup.select_one("#summary-abstract div[role='paragraph']")
        
#         # 2. Extract Authors (Specific to Article Page)
#         authors = []
#         author_links = soup.select("span[property='author'] span[property='givenName'], span[property='author'] span[property='familyName']")
#         # Reconstruct full names from schema properties if simple links are empty
#         current_author = []
#         for span in author_links:
#             current_author.append(span.get_text(strip=True))
#             if len(current_author) == 2:
#                 authors.append(" ".join(current_author))
#                 current_author = []
        
#         # Fallback for authors if schema spans aren't present
#         if not authors:
#             authors = [a.get_text(strip=True) for a in soup.select(".contributors .authors a") if "@" not in a.get_text()]

#         # 3. Extract Published Date
#         publish_date = None
#         date_div = soup.select_one(".meta-panel__onlineDate")
#         if date_div:
#             publish_date = date_div.get_text(strip=True)

#         data = {
#             "abstract": abstract_div.get_text(strip=True) if abstract_div else None,
#             "authors": list(set(authors)),
#             "publish_date": publish_date,
#             "is_pdf_available": False,
#             "pdf_url": None,
#             "pdf_local_path": None,
#             "status": "incomplete"
#         }

#         # 4. PDF Handling
#         pdf_btn = "a.btn--pdf"
#         if sb.is_element_visible(pdf_btn):
#             data["is_pdf_available"] = True
#             viewer_path = sb.get_attribute(pdf_btn, "href")
#             viewer_url = urljoin(SCRAPER_CONFIG["base_url"], viewer_path)
            
#             sb.uc_open_with_reconnect(viewer_url, 3)
#             sb.sleep(4) # Viewer pages are heavy
            
#             download_btn = "a.navbar-download"
#             if sb.is_element_visible(download_btn):
#                 final_pdf_path = sb.get_attribute(download_btn, "href")
#                 final_pdf_url = urljoin(SCRAPER_CONFIG["base_url"], final_pdf_path)
#                 data["pdf_url"] = final_pdf_url
                
#                 self.sync_session_cookies(sb)
#                 data["pdf_local_path"] = self.download_pdf(final_pdf_url, article_info["doi"])
                
#                 # Set status based on PDF success
#                 if data["pdf_local_path"]:
#                     data["status"] = "complete"
#             else:
#                 # If PDF available but download link failed to grab
#                 data["status"] = "incomplete"
#         else:
#             # If no PDF exists at all, it's considered a complete scrape of available data
#             data["status"] = "complete"
        
#         return data

#     def run(self):
#         with SB(uc=True, test=True, locale="en") as sb:
#             logger.info("🚀 Opening CABI Portal...")
#             sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
#             sb.wait_for_element("li.search__item", timeout=30)
            
#             page = 1
#             while page <= SCRAPER_CONFIG["max_pages"]:
#                 logger.info(f"📄 Processing Page {page}...")
                
#                 if "Just a moment" in sb.get_title():
#                     sb.uc_reconnect(10)

#                 current_list = self.get_list_page_items(sb.get_page_source())
                
#                 for i, item in enumerate(current_list):
#                     if item["doi"] in self.seen_dois: continue
                    
#                     logger.info(f"  🔍 [{i+1}/{len(current_list)}] Scraping: {item['doi']}")
#                     try:
#                         details = self.scrape_article_details(sb, item)
#                         item.update(details)
#                         item["scraped_at"] = datetime.now().isoformat()
                        
#                         self.articles.append(item)
#                         self.seen_dois.add(item["doi"])
                        
#                         with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#                             json.dump(self.articles, f, indent=4, ensure_ascii=False)
                            
#                     except Exception as e:
#                         logger.error(f"  ❌ Error on {item['doi']}: {e}")
                    
#                     # Jump back to list
#                     sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 5)
                
#                 next_btn = "a.pagination__btn--next"
#                 if sb.is_element_visible(next_btn):
#                     sb.scroll_to(next_btn)
#                     sb.sleep(2)
#                     sb.uc_click(next_btn, reconnect_time=5)
#                     page += 1
#                 else:
#                     break

# if __name__ == "__main__":
#     scraper = AgriRxivUltimateScraper()
#     scraper.run()

import json
import logging
import random
import os
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from seleniumbase import SB

# --- Configuration ---
SCRAPER_CONFIG = {
    "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate",
    "base_url": "https://www.cabidigitallibrary.org",
    "max_pages": 100,
}

OUTPUT_FILE = Path("agrirxiv_final_data.json")
PDF_DIR = Path("downloaded_pdfs")
PDF_DIR.mkdir(exist_ok=True)

# FIX: Added encoding="utf-8" to the FileHandler to prevent UnicodeEncodeError
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
        self.session = requests.Session()

    def sync_session_cookies(self, sb):
        cookies = sb.get_cookies()
        for cookie in cookies:
            self.session.cookies.set(cookie['name'], cookie['value'])

    def download_pdf(self, url, doi):
        try:
            safe_name = doi.replace(".", "_").replace("/", "_") + ".pdf"
            file_path = PDF_DIR / safe_name
            
            # Use the synced session
            response = self.session.get(url, timeout=45, stream=True)
            if response.status_code == 200:
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                if file_path.stat().st_size > 1000: # Check if file is valid (>1KB)
                    return str(file_path.absolute())
            logger.error(f"Download failed for {doi} - Status: {response.status_code}")
        except Exception as e:
            logger.error(f"Download exception for {doi}: {e}")
        return None

    def get_list_page_items(self, html):
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("li.search__item")
        found = []
        for item in items:
            link_tag = item.select_one(".issue-item__title a")
            if not link_tag: continue
            raw_href = link_tag.get("href", "")
            full_link = urljoin(SCRAPER_CONFIG["base_url"], raw_href)
            doi = raw_href.split("/doi/")[-1] if "/doi/" in raw_href else "unknown"
            found.append({"title": link_tag.get_text(strip=True), "link": full_link, "doi": doi})
        return found

    def scrape_article_details(self, sb, article_info):
        # Open article
        sb.uc_open_with_reconnect(article_info["link"], 5)
        sb.sleep(4) 
        
        soup = BeautifulSoup(sb.get_page_source(), "html.parser")
        
        # 1. Extract Abstract
        abstract_div = soup.select_one("#summary-abstract div[role='paragraph']")
        
        # 2. Extract Authors
        authors = []
        author_links = soup.select("span[property='author'] span[property='givenName'], span[property='author'] span[property='familyName']")
        current_author = []
        for span in author_links:
            current_author.append(span.get_text(strip=True))
            if len(current_author) == 2:
                authors.append(" ".join(current_author))
                current_author = []
        
        if not authors:
            authors = [a.get_text(strip=True) for a in soup.select(".contributors .authors a") if "@" not in a.get_text()]

        publish_date = None
        date_div = soup.select_one(".meta-panel__onlineDate")
        if date_div:
            publish_date = date_div.get_text(strip=True)

        data = {
            "abstract": abstract_div.get_text(strip=True) if abstract_div else None,
            "authors": list(set(authors)),
            "publish_date": publish_date,
            "is_pdf_available": False,
            "pdf_url": None,
            "pdf_local_path": None,
            "status": "incomplete"
        }

        # 3. PDF Handling
        pdf_btn = "a.btn--pdf"
        if sb.is_element_visible(pdf_btn):
            data["is_pdf_available"] = True
            viewer_path = sb.get_attribute(pdf_btn, "href")
            viewer_url = urljoin(SCRAPER_CONFIG["base_url"], viewer_path)
            
            # Step into viewer
            sb.uc_open_with_reconnect(viewer_url, 4)
            sb.sleep(5) 
            
            # Look for the download button inside viewer
            download_btn = "a.navbar-download"
            if sb.is_element_visible(download_btn):
                final_pdf_path = sb.get_attribute(download_btn, "href")
                final_pdf_url = urljoin(SCRAPER_CONFIG["base_url"], final_pdf_path)
                data["pdf_url"] = final_pdf_url
                
                self.sync_session_cookies(sb)
                local_path = self.download_pdf(final_pdf_url, article_info["doi"])
                data["pdf_local_path"] = local_path
                
                if local_path:
                    data["status"] = "complete"
        else:
            data["status"] = "complete" # Scrape complete if no PDF exists
        
        return data

    def run(self):
        with SB(uc=True, test=True, locale="en") as sb:
            logger.info("Opening CABI Portal...")
            sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
            sb.wait_for_element("li.search__item", timeout=30)
            
            page = 1
            while page <= SCRAPER_CONFIG["max_pages"]:
                logger.info(f"Processing Page {page}...")
                
                if "Just a moment" in sb.get_title():
                    sb.uc_reconnect(10)

                current_list = self.get_list_page_items(sb.get_page_source())
                
                for i, item in enumerate(current_list):
                    if item["doi"] in self.seen_dois: continue
                    
                    # Emojis removed to prevent UnicodeEncodeError
                    logger.info(f"  Scraping [{i+1}/{len(current_list)}]: {item['doi']}")
                    try:
                        details = self.scrape_article_details(sb, item)
                        item.update(details)
                        item["scraped_at"] = datetime.now().isoformat()
                        
                        self.articles.append(item)
                        self.seen_dois.add(item["doi"])
                        
                        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                            json.dump(self.articles, f, indent=4, ensure_ascii=False)
                            
                    except Exception as e:
                        logger.error(f"  Error on {item['doi']}: {e}")
                    
                    # Back to list
                    sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 5)
                
                next_btn = "a.pagination__btn--next"
                if sb.is_element_visible(next_btn):
                    sb.scroll_to(next_btn)
                    sb.sleep(3)
                    sb.uc_click(next_btn, reconnect_time=5)
                    page += 1
                else:
                    break

if __name__ == "__main__":
    scraper = AgriRxivUltimateScraper()
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