import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

class VavooScraper:
    def __init__(self):
        self.base_url = "https://vavoo.to"
        self.output_file = "vavoo_playlist.m3u"
        
        # Headless Chrome Ayarları (GitHub Actions uyumlu)
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(options=chrome_options)

    def scroll_channel_list(self):
        """Kanal listesini aşağı kaydırarak tüm kanalların yüklenmesini sağlar."""
        print("Siteye gidiliyor...")
        self.driver.get(self.base_url)
        
        try:
            # Kanal listesini içeren kaydırılabilir div'i bul
            scrollable_div = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[style*='overflow: hidden scroll']"))
            )
            print("Liste bulundu, tüm kanallar yükleniyor...")
            
            last_height = self.driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            
            while True:
                # En alta kaydır
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(1.5)  # Yükleme beklemesi
                
                new_height = self.driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                if new_height == last_height:
                    break
                last_height = new_height
                
        except Exception as e:
            print(f"Scroll hatası: {e}")

    def extract_and_save(self):
        """HTML'den verileri çeker ve M3U oluşturur."""
        print("HTML analiz ediliyor...")
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        
        buttons = soup.find_all("button", id=lambda x: x and x.startswith("channel-"))
        
        if not buttons:
            print("Kanal bulunamadı.")
            return

        print(f"Toplam {len(buttons)} kanal işleniyor.")
        
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            
            for btn in buttons:
                try:
                    raw_id = btn.get("id")
                    channel_id = raw_id.replace("channel-", "")
                    
                    # İsim ve Grup bulma
                    name_div = btn.find("div", style=lambda s: s and "white-space: nowrap" in s)
                    country_span = btn.find("span")
                    
                    channel_name = name_div.text.strip() if name_div else "Bilinmeyen Kanal"
                    group_name = country_span.text.strip() if country_span else "Genel"
                    
                    # Oynatılabilir link formatı
                    stream_url = f"http://vavoo.to/play/{channel_id}.index.m3u8"
                    
                    # Dosyaya yazma
                    f.write(f'#EXTINF:-1 group-title="{group_name}" tvg-id="{channel_id}", {channel_name}\n')
                    f.write(f"{stream_url}\n")
                    
                except Exception:
                    continue

        print(f"İşlem tamamlandı: {self.output_file}")

    def run(self):
        try:
            self.scroll_channel_list()
            self.extract_and_save()
        finally:
            self.driver.quit()

if __name__ == "__main__":
    scraper = VavooScraper()
    scraper.run()
