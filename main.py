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
# Github Actions ortam değişkenlerinden bilgileri al
GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN") 
REPO_NAME = os.environ.get("GITHUB_REPOSITORY") 
FILE_PATH = "playlist.m3u"
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
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
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
                            "url": full_url,
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
    """Github'a yükleme fonksiyonu - Detaylı Hata Raporlama ile"""
    log("--- GITHUB YÜKLEME İŞLEMİ BAŞLIYOR ---")
    
    # 1. Kontrol: Değişkenler dolu mu?
    if not GITHUB_TOKEN:
        log("HATA: 'MY_GITHUB_TOKEN' bulunamadı! Github Secrets ayarlarını kontrol et.")
        return
    if not REPO_NAME:
        log("HATA: 'GITHUB_REPOSITORY' bulunamadı! Repo adı çekilemedi.")
        return

    log(f"Hedef Repo: {REPO_NAME}")
    log(f"Hedef Dosya: {FILE_PATH}")

    try:
        # 2. Kontrol: Bağlantı
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        log("Repo bağlantısı başarılı.")
        
        # 3. Kontrol: Dosya var mı yok mu?
        try:
            contents = repo.get_contents(FILE_PATH)
            log(f"Dosya mevcut, güncelleniyor... (SHA: {contents.sha})")
            repo.update_file(contents.path, f"Otomatik Güncelleme {datetime.datetime.now()}", content, contents.sha)
            log("✅ BAŞARILI: M3U dosyası Github üzerinde güncellendi.")
        except Exception as e:
            # Dosya yoksa oluşturmayı dene (404 hatası normaldir)
            log("Dosya repoda bulunamadı, yeni oluşturuluyor...")
            try:
                repo.create_file(FILE_PATH, "İlk otomatik oluşturma", content)
                log("✅ BAŞARILI: Yeni M3U dosyası oluşturuldu.")
            except Exception as create_error:
                log(f"❌ KRİTİK HATA (Dosya Oluşturma): {create_error}")
                log("İPUCU: Token yetkilerini kontrol et. 'Repo' ve 'Workflow' kutucukları işaretli mi?")

    except Exception as e:
        log(f"❌ KRİTİK HATA (Genel): {e}")

def main():
    driver = None
    try:
        driver = init_driver()
        channels = get_channel_list(driver)
        
        if not channels:
            log("Kanal listesi boş.")
            return

        current_base_url = None
        
        # Base URL'i bulana kadar ilk birkaç kanalı dene
        for i in range(min(5, len(channels))):
            log(f"Base URL aranıyor (Deneme {i+1})...")
            found_base = extract_base_url(driver, channels[i]['url'])
            if found_base:
                current_base_url = found_base
                log(f"Base URL Bulundu: {current_base_url}")
                break
        
        if not current_base_url:
            log("❌ HATA: Hiçbir kanaldan yayın linki (baseurl) çekilemedi.")
            return

        # Linkleri Oluştur
        m3u_content = "#EXTM3U\n"
        count = 0
        
        for channel in channels:
            # Slash kontrolü
            if not current_base_url.endswith("/"):
                base = current_base_url + "/"
            else:
                base = current_base_url
                
            real_link = f"{base}{channel['id']}.m3u8"
            
            m3u_content += f'#EXTINF:-1 group-title="Canlı TV", {channel["name"]}\n'
            m3u_content += f'{real_link}\n'
            count += 1
            
        log(f"Toplam {count} adet link hazırlandı.")

        # Github'a yükle
        if count > 0:
            update_github_repo(m3u_content)
            
            # Yükleme başarısız olursa diye LOGLARA da basıyoruz:
            log("\n--- OLUŞTURULAN DOSYA İÇERİĞİ (Yedek) ---")
            print(m3u_content) # sys.stdout.flush gerekmez print sonunda yapar ama yine de:
            sys.stdout.flush()
            log("-------------------------------------------")

    except Exception as e:
        log(f"Ana döngü hatası: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
