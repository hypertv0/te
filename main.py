import time
import os
import sys
import re
import datetime
import shutil
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# ================= AYARLAR =================
BASE_URL = "https://trgoals1472.xyz/"
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
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
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
    try:
        driver.get(channel_url)
        time.sleep(1)
        html_source = driver.page_source
        match = re.search(r'const\s+baseurl\s*=\s*["\']([^"\']+)["\'];', html_source)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        log(f"Base URL bulma hatası: {e}")
        return None

def sanitize_filename(name):
    """Dosya isimlerindeki geçersiz karakterleri temizler"""
    # Türkçe karakterleri İngilizceye çevir (Opsiyonel ama önerilir)
    tr_map = {'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G', 'ü': 'u', 'Ü': 'U', 'ş': 's', 'Ş': 'S', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'}
    for tr, en in tr_map.items():
        name = name.replace(tr, en)
    
    # Geçersiz karakterleri sil, boşlukları alt çizgi yap
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return name.strip().replace(" ", "_")

def main():
    driver = None
    try:
        driver = init_driver()
        channels = get_channel_list(driver)
        
        if not channels:
            return

        current_base_url = None
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

        # Klasör Hazırlığı
        if os.path.exists("channels"):
            shutil.rmtree("channels") # Eski klasörü sil
        os.makedirs("channels") # Yeni klasör oluştur

        m3u_content = "#EXTM3U\n"
        count = 0
        
        for channel in channels:
            if not current_base_url.endswith("/"):
                base = current_base_url + "/"
            else:
                base = current_base_url
                
            raw_link = f"{base}{channel['id']}.m3u8"
            referer_url = channel['url']
            
            # Headerlı link
            final_link_with_headers = f"{raw_link}|Referer={referer_url}&User-Agent={USER_AGENT}"
            
            # 1. Ana M3U Dosyasına Ekle
            m3u_content += f'#EXTINF:-1 group-title="Canlı TV", {channel["name"]}\n'
            m3u_content += f'{final_link_with_headers}\n'
            
            # 2. Tekil M3U8 Dosyası Oluştur (Channels klasörüne)
            clean_name = sanitize_filename(channel["name"])
            file_name = f"channels/{clean_name}.m3u8"
            
            # Tekil dosya içeriği de bir M3U playlist olmalı ki header çalışsın
            individual_content = "#EXTM3U\n"
            individual_content += f'#EXTINF:-1,{channel["name"]}\n'
            individual_content += f'{final_link_with_headers}'
            
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(individual_content)

            count += 1
            
        # Ana M3U dosyasını kaydet
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_content)

        log(f"İşlem Tamamlandı: {count} kanal.")
        log("Dosyalar diske kaydedildi, Github'a pushlanmayı bekliyor.")

    except Exception as e:
        log(f"Genel Hata: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
