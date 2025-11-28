import time
import json
import os
import sys
import datetime
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
    """Logları anında yazdırmak için yardımcı fonksiyon"""
    print(f"[{datetime.datetime.now()}] {message}")
    sys.stdout.flush() # Çıktıyı zorla yazdır

def init_driver():
    log("Chrome ayarları yapılıyor...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Yeni headless modu
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    # ÇOK ÖNEMLİ: Sayfanın tamamen yüklenmesini bekleme (reklamlar yüzünden donmaması için)
    chrome_options.page_load_strategy = 'eager'
    
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    log("Driver yükleniyor...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    # Sayfa yükleme zaman aşımı (30 saniye)
    driver.set_page_load_timeout(30)
    log("Driver başlatıldı.")
    return driver

def get_channel_list(driver):
    log(f"Ana sayfa taranıyor: {BASE_URL}")
    try:
        driver.get(BASE_URL)
        # Eager modda olduğumuz için elementin görünmesini biraz bekleyelim
        time.sleep(5)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        channels = []
        
        channel_list_div = soup.find("div", {"id": "channelList"})
        if not channel_list_div:
            log("Kanal listesi div'i bulunamadı.")
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
                
        log(f"Toplam {len(channels)} kanal bulundu.")
        return channels
    except Exception as e:
        log(f"Kanal listesi alma hatası: {e}")
        return []

def get_m3u8_from_logs(driver, url):
    log(f"Link taranıyor: {url}")
    try:
        driver.get(url)
        time.sleep(8) # Playerın yüklenmesi için bekle
        
        logs = driver.get_log("performance")
        found_link = None

        for entry in logs:
            try:
                message_obj = json.loads(entry["message"])
                message = message_obj["message"]
                if "Network.requestWillBeSent" in message["method"]:
                    request_url = message["params"]["request"]["url"]
                    
                    if ".m3u8" in request_url and "ad-delivery" not in request_url:
                        found_link = request_url
                        # Döngüden çıkma, son bulunanı al (genellikle en doğrusu sondakidir)
            except:
                continue
        
        if found_link:
            log(f"BULUNDU: ...{found_link[-30:]}")
            return found_link
        else:
            log("M3U8 bulunamadı.")
            return None

    except Exception as e:
        log(f"Sayfa hatası: {e}")
        return None

def update_github_repo(content):
    if not GITHUB_TOKEN or not REPO_NAME:
        log("Github Token veya Repo adı eksik! İşlem yapılmadı.")
        return

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, f"Güncelleme {datetime.datetime.now()}", content, contents.sha)
            log("M3U dosyası güncellendi.")
        except:
            repo.create_file(FILE_PATH, "İlk yükleme", content)
            log("M3U dosyası oluşturuldu.")
    except Exception as e:
        log(f"Github işlem hatası: {e}")

def main():
    driver = None
    try:
        driver = init_driver()
        channels = get_channel_list(driver)
        
        if not channels:
            log("Kanal listesi boş, çıkılıyor.")
            return

        m3u_content = "#EXTM3U\n"
        
        # Test için sadece ilk 5 kanalı tarayalım (Hız testi için)
        # Gerçek kullanımda [:5] kısmını kaldırın: "for channel in channels:" yapın
        count = 0
        for channel in channels:
            m3u8_url = get_m3u8_from_logs(driver, channel['url'])
            if m3u8_url:
                m3u_content += f'#EXTINF:-1 group-title="Canlı", {channel["name"]}\n'
                m3u_content += f'{m3u8_url}\n'
                count += 1
            
            # Botun aşırı yorulmaması için kısa bekleme
            time.sleep(1) 
        
        log(f"Toplam {count} adet link bulundu.")

        if count > 0:
            update_github_repo(m3u_content)
        else:
            log("Hiç link bulunamadığı için güncelleme yapılmadı.")

    except Exception as e:
        log(f"Kritik hata: {e}")
    finally:
        if driver:
            driver.quit()
            log("Driver kapatıldı.")

if __name__ == "__main__":
    main()
