# import json
# import logging
# import os
# import re
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
# DOWNLOAD_DIR = Path(r"C:\Users\Saurabh-CSIO\Desktop\Scrapy\downloaded_files")
# DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# logging.basicConfig(
#     level=logging.INFO, 
#     format="%(asctime)s - %(levelname)s - %(message)s",
#     handlers=[
#         logging.FileHandler("scraper_debug.log", encoding="utf-8"), 
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger(__name__)

# class AgriRxivUltimateScraper:
#     def __init__(self):
#         self.articles = []
#         self.seen_dois = set()

#     def download_pdf_manually(self, sb, url, doi):
#         """
#         Downloads PDF using requests with browser cookies to bypass 403.
#         Uses a sanitized DOI-based name to bypass Errno 22.
#         """
#         # 1. Create a strictly legal filename (Fixes Errno 22)
#         clean_doi = re.sub(r'[^a-zA-Z0-9._]', '_', doi)
#         target_path = DOWNLOAD_DIR / f"{clean_doi}.pdf"

#         try:
#             # 2. Get cookies from SeleniumBase browser
#             cookies = {c['name']: c['value'] for c in sb.get_cookies()}
            
#             # 3. Get User-Agent from browser to match TLS fingerprint
#             user_agent = sb.get_user_agent()

#             headers = {
#                 "User-Agent": user_agent,
#                 "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#                 "Referer": sb.get_current_url()
#             }

#             # 4. Perform the download
#             response = requests.get(url, cookies=cookies, headers=headers, stream=True, timeout=30)
            
#             if response.status_code == 200:
#                 with open(target_path, 'wb') as f:
#                     for chunk in response.iter_content(chunk_size=8192):
#                         f.write(chunk)
#                 return str(target_path.absolute())
#             else:
#                 logger.error(f"  Request failed with status: {response.status_code}")
#         except Exception as e:
#             logger.error(f"  Manual download exception: {e}")
        
#         return None

#     def scrape_article_details(self, sb, article_info):
#         sb.uc_open_with_reconnect(article_info["link"], 5)
#         sb.sleep(3)
        
#         soup = BeautifulSoup(sb.get_page_source(), "html.parser")
#         abstract_div = soup.select_one("#summary-abstract div[role='paragraph']")
#         authors = [a.get_text(strip=True) for a in soup.select(".hlFld-ContribAuthor a") if "@" not in a.get_text()]
#         date_div = soup.select_one(".meta-panel__onlineDate")

#         data = {
#             "abstract": abstract_div.get_text(strip=True) if abstract_div else None,
#             "authors": list(set(authors)),
#             "publish_date": date_div.get_text(strip=True) if date_div else None,
#             "is_pdf_available": False,
#             "pdf_url": None,
#             "pdf_local_path": None,
#             "status": "incomplete"
#         }

#         pdf_btn = "a.btn--pdf"
#         if sb.is_element_visible(pdf_btn):
#             data["is_pdf_available"] = True
#             viewer_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(pdf_btn, "href"))
            
#             sb.uc_open_with_reconnect(viewer_url, 4)
#             sb.sleep(6) 
            
#             download_btn = "a.navbar-download"
#             if sb.is_element_visible(download_btn):
#                 raw_pdf_url = sb.get_attribute(download_btn, "href")
#                 final_pdf_url = urljoin(SCRAPER_CONFIG["base_url"], raw_pdf_url)
#                 data["pdf_url"] = final_pdf_url
                
#                 logger.info(f"  Attempting secure manual download for DOI: {article_info['doi']}")
#                 local_path = self.download_pdf_manually(sb, final_pdf_url, article_info['doi'])
                
#                 if local_path:
#                     data["pdf_local_path"] = local_path
#                     data["status"] = "complete"
#                     logger.info(f"  Successfully Saved: {Path(local_path).name}")
#         else:
#             data["status"] = "complete"
        
#         return data

#     def run(self):
#         with SB(uc=True, test=True, locale="en") as sb:
#             sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
#             sb.wait_for_element("li.search__item", timeout=30)
            
#             page = 1
#             while page <= SCRAPER_CONFIG["max_pages"]:
#                 elements = sb.find_elements(".issue-item__title a")
#                 current_page_dois = []
#                 for a in elements:
#                     href = a.get_attribute("href")
#                     current_page_dois.append({
#                         "title": a.text.strip(),
#                         "link": urljoin(SCRAPER_CONFIG["base_url"], href),
#                         "doi": href.split("/doi/")[-1]
#                     })
                
#                 for i, item in enumerate(current_page_dois):
#                     if item["doi"] in self.seen_dois: continue
#                     logger.info(f"Scraping [{i+1}/{len(current_page_dois)}] DOI: {item['doi']}")
                    
#                     try:
#                         details = self.scrape_article_details(sb, item)
#                         item.update(details)
#                         item["scraped_at"] = datetime.now().isoformat()
#                         self.articles.append(item)
#                         self.seen_dois.add(item["doi"])
                        
#                         with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#                             json.dump(self.articles, f, indent=4, ensure_ascii=False)
#                     except Exception as e:
#                         logger.error(f"Error processing {item['doi']}: {e}")
                    
#                     sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 5)
                
#                 next_btn = "a.pagination__btn--next"
#                 if sb.is_element_visible(next_btn):
#                     sb.uc_click(next_btn, reconnect_time=5)
#                     page += 1
#                 else: break

# if __name__ == "__main__":
#     AgriRxivUltimateScraper().run()





































# import json
# import logging
# import os
# import re
# import requests
# import time
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

# # --- File System Setup ---
# OUTPUT_FILE = Path("agrirxiv_final_data.json")
# # Absolute path to ensure no ambiguity on Windows
# DOWNLOAD_DIR = Path(r"C:\Users\Saurabh-CSIO\Desktop\Scrapy\downloaded_files")
# DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# # --- Logging Setup (Unicode Fix) ---
# logging.basicConfig(
#     level=logging.INFO, 
#     format="%(asctime)s - %(levelname)s - %(message)s",
#     handlers=[
#         logging.FileHandler("scraper_debug.log", encoding="utf-8"), 
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger(__name__)

# class AgriRxivUltimateScraper:
#     def __init__(self):
#         self.articles = []
#         self.seen_dois = set()
#         self.load_existing_data()

#     def load_existing_data(self):
#         """Resume logic: prevents re-scraping and data loss after a crash."""
#         if OUTPUT_FILE.exists():
#             try:
#                 with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
#                     self.articles = json.load(f)
#                     self.seen_dois = {item["doi"] for item in self.articles}
#                 logger.info(f"Resume: Loaded {len(self.seen_dois)} items from existing JSON.")
#             except Exception as e:
#                 logger.error(f"Resume failed (clean start): {e}")

#     def download_pdf_securely(self, sb, url, doi):
#         """
#         Fixes Errno 22 (Sanitization) and 403 (Cookie Sync).
#         Downloads PDF using requests with browser's authenticated identity.
#         """
#         # Remove any character Windows dislikes (?, =, :, etc)
#         clean_name = re.sub(r'[^a-zA-Z0-9._]', '_', doi)
#         target_path = DOWNLOAD_DIR / f"{clean_name}.pdf"

#         try:
#             # Match browser's exact session to bypass Cloudflare 403
#             cookies = {c['name']: c['value'] for c in sb.get_cookies()}
#             headers = {
#                 "User-Agent": sb.get_user_agent(),
#                 "Referer": sb.get_current_url()
#             }
            
#             response = requests.get(url, cookies=cookies, headers=headers, stream=True, timeout=45)
            
#             if response.status_code == 200:
#                 with open(target_path, 'wb') as f:
#                     for chunk in response.iter_content(chunk_size=8192):
#                         f.write(chunk)
#                 return str(target_path.absolute())
#             else:
#                 logger.error(f"  Download failed: Status {response.status_code}")
#         except Exception as e:
#             logger.error(f"  Download error for {doi}: {e}")
#         return None

#     def scrape_article_details(self, sb, article_info):
#         """Extracts text and handles PDF logic inside the article view."""
#         try:
#             sb.uc_open_with_reconnect(article_info["link"], 5)
#             sb.sleep(4)
            
#             soup = BeautifulSoup(sb.get_page_source(), "html.parser")
            
#             # Extract Abstract
#             abstract_div = soup.select_one("#summary-abstract div[role='paragraph']")
            
#             # Extract Authors (Article-page specific selectors)
#             authors = [a.get_text(strip=True) for a in soup.select(".hlFld-ContribAuthor a") if "@" not in a.get_text()]
            
#             # Extract Publish Date
#             date_div = soup.select_one(".meta-panel__onlineDate")

#             data = {
#                 "abstract": abstract_div.get_text(strip=True) if abstract_div else None,
#                 "authors": list(set(authors)),
#                 "publish_date": date_div.get_text(strip=True) if date_div else None,
#                 "is_pdf_available": False,
#                 "pdf_url": None,
#                 "pdf_local_path": None,
#                 "status": "incomplete"
#             }

#             # Handle PDF Download
#             pdf_btn = "a.btn--pdf"
#             if sb.is_element_visible(pdf_btn):
#                 data["is_pdf_available"] = True
#                 viewer_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(pdf_btn, "href"))
                
#                 # Navigate to the viewer page to get final URL
#                 sb.uc_open_with_reconnect(viewer_url, 4)
#                 sb.sleep(6) 
                
#                 download_btn = "a.navbar-download"
#                 if sb.is_element_visible(download_btn):
#                     final_pdf_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(download_btn, "href"))
#                     data["pdf_url"] = final_pdf_url
                    
#                     logger.info(f"  Starting download for DOI: {article_info['doi']}")
#                     local_path = self.download_pdf_securely(sb, final_pdf_url, article_info['doi'])
                    
#                     if local_path:
#                         data["pdf_local_path"] = local_path
#                         data["status"] = "complete"
#             else:
#                 # Scrape is 'complete' if metadata was found but no PDF exists to download
#                 data["status"] = "complete"
            
#             return data
#         except Exception as e:
#             logger.error(f"  Error in article details logic: {e}")
#             return None

#     def run(self):
#         try:
#             with SB(uc=True, test=True, locale="en") as sb:
#                 logger.info("Initializing AgriRxiv Scraper...")
#                 sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 10)
                
#                 page = 1
#                 while page <= SCRAPER_CONFIG["max_pages"]:
#                     sb.wait_for_element("li.search__item", timeout=30)
                    
#                     # Correct Selenium WebElement text/attribute access
#                     elements = sb.find_elements(".issue-item__title a")
#                     current_page_items = []
#                     for a in elements:
#                         href = a.get_attribute("href")
#                         current_page_items.append({
#                             "title": a.text.strip(),
#                             "link": urljoin(SCRAPER_CONFIG["base_url"], href),
#                             "doi": href.split("/doi/")[-1]
#                         })

#                     for i, item in enumerate(current_page_items):
#                         if item["doi"] in self.seen_dois:
#                             continue
                        
#                         logger.info(f"PAGE {page} | ITEM {i+1}/{len(current_page_items)} | DOI: {item['doi']}")
                        
#                         details = self.scrape_article_details(sb, item)
#                         if details:
#                             item.update(details)
#                             item["scraped_at"] = datetime.now().isoformat()
#                             self.articles.append(item)
#                             self.seen_dois.add(item["doi"])
                            
#                             # Atomic save: data is safe even if browser closes next second
#                             with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#                                 json.dump(self.articles, f, indent=4, ensure_ascii=False)
                        
#                         # Return to Search results page
#                         sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 5)
#                         sb.wait_for_element("li.search__item", timeout=20)

#                     # Handle Pagination
#                     next_btn = "a.pagination__btn--next"
#                     if sb.is_element_visible(next_btn):
#                         logger.info("Advancing to next search result page...")
#                         sb.uc_click(next_btn, reconnect_time=5)
#                         page += 1
#                         sb.sleep(4)
#                     else:
#                         logger.info("Finished: No more pages found.")
#                         break
#         except Exception as e:
#             logger.critical(f"Browser Instance Failed: {e}. Restart script to resume.")

# if __name__ == "__main__":
#     AgriRxivUltimateScraper().run()







































































































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
    "search_url": "https://www.cabidigitallibrary.org/action/doSearch?SeriesKey=agrirxiv&sortBy=EPubDate",
    "base_url": "https://www.cabidigitallibrary.org",
    "max_pages": 100,
}

# --- File System Setup ---
OUTPUT_FILE = Path("agrirxiv_final_data.json")
DOWNLOAD_DIR = Path(r"C:\Users\Saurabh-CSIO\Desktop\Scrapy\downloaded_files")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
        self.load_existing_data()

    def load_existing_data(self):
        if OUTPUT_FILE.exists():
            try:
                with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                    self.articles = json.load(f)
                    self.seen_dois = {item["doi"] for item in self.articles}
                logger.info(f"STEP: Resume - Loaded {len(self.seen_dois)} items from existing JSON.")
            except Exception as e:
                logger.error(f"STEP: Resume - Failed to load existing data: {e}")

    def download_pdf_securely(self, sb, url, doi):
        logger.info(f"STEP: PDF - Starting secure download for DOI: {doi}")
        clean_name = re.sub(r'[^a-zA-Z0-9._]', '_', doi)
        target_path = DOWNLOAD_DIR / f"{clean_name}.pdf"

        try:
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
                logger.info(f"STEP: PDF - Successfully saved to {target_path}")
                return str(target_path.absolute())
            else:
                logger.error(f"STEP: PDF - Download failed with HTTP Status {response.status_code}")
        except Exception as e:
            logger.error(f"STEP: PDF - Exception during download: {e}")
        return None

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
                "pdf_local_path": None,
                "status": "incomplete"
            }

            # 4. Handle PDF Logic
            pdf_btn = "a.btn--pdf"
            if sb.is_element_visible(pdf_btn):
                logger.info("STEP: PDF - Found PDF button, entering viewer")
                data["is_pdf_available"] = True
                viewer_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(pdf_btn, "href"))
                
                sb.uc_open_with_reconnect(viewer_url, 4)
                sb.sleep(7) 
                
                download_btn = "a.navbar-download"
                if sb.is_element_visible(download_btn):
                    final_pdf_url = urljoin(SCRAPER_CONFIG["base_url"], sb.get_attribute(download_btn, "href"))
                    data["pdf_url"] = final_pdf_url
                    
                    local_path = self.download_pdf_securely(sb, final_pdf_url, article_info['doi'])
                    if local_path:
                        data["pdf_local_path"] = local_path
                        data["status"] = "complete"
                else:
                    logger.warning("STEP: PDF - Viewer opened but download button not found")
            else:
                logger.info("STEP: PDF - No PDF button available for this article")
                data["status"] = "complete"
            
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
                        
                        logger.info("STEP: MAIN - Returning to search results")
                        sb.uc_open_with_reconnect(SCRAPER_CONFIG["search_url"], 5)
                        sb.wait_for_element("li.search__item", timeout=20)

                    next_btn = "a.pagination__btn--next"
                    if sb.is_element_visible(next_btn):
                        logger.info("STEP: PAGINATION - Clicking NEXT button")
                        sb.uc_click(next_btn, reconnect_time=5)
                        page += 1
                        sb.sleep(4)
                    else:
                        break
        except Exception as e:
            logger.critical(f"STEP: FATAL - Browser instance failed: {e}")

if __name__ == "__main__":
    AgriRxivUltimateScraper().run()