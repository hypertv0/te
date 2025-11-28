import time
import os
import sys
import re
import datetime
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from github import Github

# ================= AYARLAR =================
BASE_URL = "https://trgoals1472.xyz/"
GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN") 
REPO_NAME = os.environ.get("GITHUB_REPOSITORY") 
FILE_PATH = "playlist.m3u"

# Tarayıcı gibi görünmek için sabit User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
# ===========================================

def log(message):
    print(f"[{datetime.datetime.now()}] {message}")
    sys.stdout.flush()

def init_driver():
    log("Chrome ayarları yapılıyor...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument(f"user-agent={USER_AGENT}") # User-Agent'ı buraya da ekledik
    chrome_options.page_load_strategy = 'eager'
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    return driver

def get_channel_list(driver):
    log(f"Ana sayfa taranıyor: {BASE_URL}")
    try:
        driver.get(BASE_URL)
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        channels = []
        
        channel_list_div = soup.find("div", {"id": "channelList"})
        if not channel_list_div:
            log("Kanal listesi bulunamadı.")
            return []

        links = channel_list_div.find_all("a", class_="channel-item")
        
        for link in links:
            name_div = link.find("div", class_="channel-name")
            if name_div:
                name = name_div.get_text(strip=True)
                href = link.get("href")
                
                if href:
                    if not href.startswith("http"):
                        full_url = BASE_URL.rstrip("/") + href if href.startswith("/") else BASE_URL + href
                    else:
                        full_url = href
                    
                    parsed = urlparse(full_url)
                    query = parse_qs(parsed.query)
                    channel_id = query.get('id', [None])[0]

                    if channel_id:
                        channels.append({
                            "name": name, 
                            "url": full_url, # Bu aynı zamanda bizim REFERER linkimiz
                            "id": channel_id
                        })
                
        log(f"Toplam {len(channels)} kanal bulundu.")
        return channels
    except Exception as e:
        log(f"Kanal listesi hatası: {e}")
        return []

def extract_base_url(driver, channel_url):
    """Sadece base url'i (https://...sbs/) bulur"""
    try:
        driver.get(channel_url)
        time.sleep(1)
        html_source = driver.page_source
        
        # Regex ile 'const baseurl' bul
        match = re.search(r'const\s+baseurl\s*=\s*["\']([^"\']+)["\'];', html_source)
        
        if match:
            return match.group(1)
        return None
    except Exception as e:
        log(f"Base URL bulma hatası: {e}")
        return None

def update_github_repo(content):
    log("--- GITHUB YÜKLEME İŞLEMİ ---")
    
    # Token yoksa sadece log basar (Github Actions kullanmıyorsan test için)
    if not GITHUB_TOKEN or not REPO_NAME:
        log("Github Token veya Repo adı yok. Yükleme atlandı.")
        return

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, f"Güncelleme {datetime.datetime.now()}", content, contents.sha)
            log("✅ M3U dosyası güncellendi.")
        except:
            repo.create_file(FILE_PATH, "İlk oluşturma", content)
            log("✅ Yeni M3U dosyası oluşturuldu.")

    except Exception as e:
        log(f"❌ GITHUB HATASI: {e}")

def main():
    driver = None
    try:
        driver = init_driver()
        channels = get_channel_list(driver)
        
        if not channels:
            return

        current_base_url = None
        
        # Base URL'i bulana kadar ilk birkaç kanalı dene
        for i in range(min(5, len(channels))):
            log(f"Base URL aranıyor ({i+1})...")
            found_base = extract_base_url(driver, channels[i]['url'])
            if found_base:
                current_base_url = found_base
                log(f"Base URL Bulundu: {current_base_url}")
                break
        
        if not current_base_url:
            log("❌ HATA: Base URL bulunamadı.")
            return

        # Linkleri Oluştur ve Header Ekle
        m3u_content = "#EXTM3U\n"
        count = 0
        
        for channel in channels:
            # Base URL sonuna slash ekle
            if not current_base_url.endswith("/"):
                base = current_base_url + "/"
            else:
                base = current_base_url
                
            # Ham m3u8 linki
            raw_link = f"{base}{channel['id']}.m3u8"
            
            # REFERER BELİRLEME:
            # Referer genellikle yayının olduğu sayfanın kendisidir.
            # channel['url'] bizim referer linkimizdir (örn: https://trgoals.../channel.html?id=yayin1)
            # Ancak garanti olsun diye ana domaini de ekleyebiliriz ama sayfa linki en garantisidir.
            referer_url = channel['url']
            
            # User-Agent ve Referer'i linkin sonuna pipe (|) ile ekliyoruz.
            # Birçok IPTV player (VLC, TiviMate, OTT Navigator) bu formatı tanır.
            final_link_with_headers = f"{raw_link}|Referer={referer_url}&User-Agent={USER_AGENT}"
            
            m3u_content += f'#EXTINF:-1 group-title="Canlı TV", {channel["name"]}\n'
            m3u_content += f'{final_link_with_headers}\n'
            count += 1
            
        log(f"Toplam {count} adet link (Headerlı) hazırlandı.")

        if count > 0:
            update_github_repo(m3u_content)
            
            # Yedek olarak ekrana bas (Test için)
            log("\n--- ÖRNEK ÇIKTI (İlk 3 Satır) ---")
            print('\n'.join(m3u_content.split('\n')[:6])) 
            log("...")

    except Exception as e:
        log(f"Genel Hata: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
