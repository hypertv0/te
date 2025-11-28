import time
import json
import os
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from github import Github

# ================= AYARLAR =================
BASE_URL = "https://trgoals1472.xyz/"
# Token'ı gizli ayarlardan (Secrets) çekeceğiz
GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN") 
# Repo adını otomatik olarak mevcut repodan almayı dener veya manuel yazabilirsin
REPO_NAME = os.environ.get("GITHUB_REPOSITORY") # Örn: kullanici/repo
FILE_PATH = "playlist.m3u"
# ===========================================

def init_driver():
    """Headless Chrome sürücüsünü başlatır."""
    chrome_options = Options()
    chrome_options.add_argument("--headless") # GUI yok
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Network loglarını aç
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_channel_list(driver):
    print(f"[{datetime.datetime.now()}] Ana sayfa taranıyor: {BASE_URL}")
    try:
        driver.get(BASE_URL)
        time.sleep(5)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        channels = []
        
        channel_list_div = soup.find("div", {"id": "channelList"})
        if not channel_list_div:
            return []

        links = channel_list_div.find_all("a", class_="channel-item")
        
        for link in links:
            name_div = link.find("div", class_="channel-name")
            if name_div:
                name = name_div.get_text(strip=True)
                href = link.get("href")
                if href and not href.startswith("http"):
                    full_url = BASE_URL.rstrip("/") + href
                else:
                    full_url = href
                channels.append({"name": name, "url": full_url})
                
        print(f"Toplam {len(channels)} kanal bulundu.")
        return channels
    except Exception as e:
        print(f"Kanal listesi alma hatası: {e}")
        return []

def get_m3u8_from_logs(driver, url):
    print(f"Link taranıyor: {url}")
    try:
        driver.get(url)
        time.sleep(5) # Yükleme bekleme süresi
        logs = driver.get_log("performance")
        
        for entry in logs:
            message = json.loads(entry["message"])["message"]
            if "Network.requestWillBeSent" in message["method"]:
                request_url = message["params"]["request"]["url"]
                if ".m3u8" in request_url and "ad-delivery" not in request_url:
                    print(f"BULUNDU: {request_url[:60]}...")
                    return request_url
        return None
    except Exception as e:
        print(f"Hata: {e}")
        return None

def update_github_repo(content):
    if not GITHUB_TOKEN or not REPO_NAME:
        print("Github Token veya Repo adı eksik!")
        return

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, f"Güncelleme {datetime.datetime.now()}", content, contents.sha)
            print("M3U dosyası güncellendi.")
        except:
            repo.create_file(FILE_PATH, "İlk yükleme", content)
            print("M3U dosyası oluşturuldu.")
    except Exception as e:
        print(f"Github işlem hatası: {e}")

def main():
    driver = init_driver()
    try:
        channels = get_channel_list(driver)
        if not channels:
            print("Kanal bulunamadı, çıkılıyor.")
            return

        m3u_content = "#EXTM3U\n"
        
        for channel in channels:
            m3u8_url = get_m3u8_from_logs(driver, channel['url'])
            if m3u8_url:
                m3u_content += f'#EXTINF:-1 group-title="Canlı", {channel["name"]}\n'
                m3u_content += f'{m3u8_url}\n'
        
        # Eğer içerik doluysa Github'a yükle
        if len(m3u_content) > 15:
            update_github_repo(m3u_content)
        else:
            print("Geçerli link bulunamadığı için dosya güncellenmedi.")

    except Exception as e:
        print(f"Ana döngü hatası: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
