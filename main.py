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
    
    # Artık network loglarına ihtiyacımız yok ama hızlı yükleme stratejisi kalsın
    chrome_options.page_load_strategy = 'eager'
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    return driver

def get_channel_list(driver):
    log(f"Ana sayfa taranıyor: {BASE_URL}")
    try:
        driver.get(BASE_URL)
        time.sleep(3) # Sayfa iskeletinin yüklenmesi için kısa bekleme
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        channels = []
        
        channel_list_div = soup.find("div", {"id": "channelList"})
        if not channel_list_div:
            log("Kanal listesi bulunamadı.")
            return []

        # Hem maçlar hem 7/24 kanalları al
        links = channel_list_div.find_all("a", class_="channel-item")
        
        for link in links:
            name_div = link.find("div", class_="channel-name")
            if name_div:
                name = name_div.get_text(strip=True)
                href = link.get("href") # /channel.html?id=yayin1
                
                # Full URL oluştur
                if href:
                    if not href.startswith("http"):
                        full_url = BASE_URL.rstrip("/") + href if href.startswith("/") else BASE_URL + href
                    else:
                        full_url = href
                    
                    # URL'den ID'yi çek (örn: yayin1)
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

def extract_real_m3u8(driver, channel_url, channel_id):
    """
    Sayfa kaynağındaki JavaScript kodundan 'baseurl' değişkenini bulur
    ve ID ile birleştirerek gerçek linki üretir.
    """
    try:
        driver.get(channel_url)
        # Playerın yüklenmesini beklemeye gerek yok, kaynak kod yeterli
        # Ancak JS değişkenlerinin render olması için çok kısa bekleyelim
        time.sleep(1)
        
        html_source = driver.page_source
        
        # Regex ile 'const baseurl = "..."' yapısını ara
        # Örnek: const baseurl = "https://h29.04bf112a615942b35.sbs/";
        match = re.search(r'const\s+baseurl\s*=\s*["\']([^"\']+)["\'];', html_source)
        
        if match:
            base_url = match.group(1)
            # Link oluşturma mantığı: baseurl + id + .m3u8
            real_m3u8 = f"{base_url}{channel_id}.m3u8"
            
            # Bazı durumlarda baseurl slash ile bitmeyebilir
            if not base_url.endswith("/"):
                real_m3u8 = f"{base_url}/{channel_id}.m3u8"
                
            log(f"Link Üretildi: {real_m3u8}")
            return real_m3u8
        else:
            log(f"Base URL bulunamadı: {channel_id}")
            return None

    except Exception as e:
        log(f"Link çıkarma hatası: {e}")
        return None

def update_github_repo(content):
    if not GITHUB_TOKEN or not REPO_NAME:
        log("Github Token veya Repo bilgisi eksik. Kayıt yapılmadı.")
        return

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, f"Update {datetime.datetime.now()}", content, contents.sha)
            log("Github dosyası güncellendi.")
        except:
            repo.create_file(FILE_PATH, "Initial create", content)
            log("Github dosyası oluşturuldu.")
    except Exception as e:
        log(f"Github hatası: {e}")

def main():
    driver = None
    try:
        driver = init_driver()
        channels = get_channel_list(driver)
        
        if not channels:
            return

        m3u_content = "#EXTM3U\n"
        valid_count = 0
        
        # Base URL genellikle tüm kanallar için aynıdır.
        # Her sayfa için tekrar tekrar tarayıcıyı yormak yerine
        # İlk kanaldan baseurl'i alıp diğerlerine uygulayabiliriz.
        # Ancak site yapısı değişirse diye şimdilik her sayfaya girip teyit edelim.
        # Hızlandırmak için: İlk kanaldan base_url alıp döngüde kullanabilirsin.
        
        current_base_url = None
        
        for channel in channels:
            # Eğer base_url'i henüz bulamadıysak veya her seferinde kontrol etmek istiyorsak:
            # Performans için: Sadece ilk kanalda base_url bul, diğerlerinde ID değiştir.
            
            if current_base_url is None:
                # İlk kanaldan base_url'i çekmeye çalış
                real_link = extract_real_m3u8(driver, channel['url'], channel['id'])
                if real_link:
                    # Linkten base_url kısmını ayıkla
                    # real_link: https://site.com/yayint2.m3u8 -> base: https://site.com/
                    current_base_url = real_link.replace(f"{channel['id']}.m3u8", "")
            else:
                # Base URL zaten bulunduysa direkt oluştur
                real_link = f"{current_base_url}{channel['id']}.m3u8"
                log(f"Hızlı Üretim: {real_link}")

            if real_link:
                m3u_content += f'#EXTINF:-1 group-title="Canlı", {channel["name"]}\n'
                m3u_content += f'{real_link}\n'
                valid_count += 1
            
        if valid_count > 0:
            update_github_repo(m3u_content)
        else:
            log("Hiç link üretilemedi.")

    except Exception as e:
        log(f"Genel Hata: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
