import os
import re
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Renk kodları
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'
INFO = f"{GREEN}[INFO]{RESET}"
ERROR = f"{RED}[HATA]{RESET}"

# Hangi kanalların ID'lerini bildiğimizi buraya yazıyoruz
KANALLAR = {
    "Bein_Sports_1": "2113462398d8dd57a8ea73",
    "ATV": "1332310706bfa3901bee7c",
    "Kanal_D": "1677679684b9f4fab2cdc5",
    "Show_TV": "879588960066fd4ecca93",
    "Star_TV": "2192971293555936a8b7c7",
    "TRT_1": "16522001356210d1dcce12",
    "S_Sport": "2123273598f3ea83219516"
    # Diğer kanal ID'lerini buraya ekleyebilirsiniz...
}

def get_stream_url_with_selenium(channel_id):
    """Selenium kullanarak bir Kool.to kanalının nihai M3U8 linkini yakalar."""
    print(f"[*] Selenium başlatılıyor: {channel_id}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")
    # Ağ trafiğini dinlemek için bu ayar kritik
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = None  # driver değişkenini başta tanımla
    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
        
        target_url = f"https://kool.to/kool-iptv/play/{channel_id}"
        print(f"[*] Sayfa açılıyor: {target_url}")
        driver.get(target_url)
        
        # Sayfanın yüklenmesi ve JavaScript'in API çağrılarını yapması için bekle
        time.sleep(15) 
        
        print("[*] Ağ trafiği logları taranıyor...")
        logs = driver.get_log('performance')
        
        m3u8_url = None
        # Ağ trafiği içinde .m3u8 linkini ara
        for log in logs:
            message = json.loads(log['message'])['message']
            # Ağdaki isteğin URL'sini al
            if 'Network.requestWillBeSent' in message['method']:
                url = message['params']['request']['url']
                # Eğer 'sunshine' ve '.m3u8' içeriyorsa, bu bizim aradığımız linktir
                if '.m3u8' in url and 'sunshine' in url:
                    print(f"{GREEN}[OK] Nihai M3U8 linki yakalandı!{RESET}")
                    m3u8_url = url
                    break # Linki bulduğumuz an döngüden çık
                    
        driver.quit()
        return m3u8_url

    except Exception as e:
        print(f"{ERROR} Selenium çalışırken bir hata oluştu: {e}")
        if driver:
            driver.quit()
        return None

def m3u8_dosyalarini_olustur():
    output_dir = "kanallar"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n{INFO} '{output_dir}' klasörüne M3U8 dosyaları oluşturuluyor...")
    
    kanallar_olusturuldu = 0
    for kanal_adi, kanal_id in KANALLAR.items():
        print(f"\n--- İşleniyor: {kanal_adi} ---")
        final_url = get_stream_url_with_selenium(kanal_id)
        
        if final_url:
            # Bu basit bir yönlendirme dosyası olacak
            m3u8_icerik = f"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000000\n{final_url}"
            dosya_yolu = os.path.join(output_dir, f"{kanal_adi}.m3u8")
            try:
                with open(dosya_yolu, 'w', encoding='utf-8') as f:
                    f.write(m3u8_icerik)
                print(f"{GREEN}[OK] Oluşturuldu: {dosya_yolu}{RESET}")
                kanallar_olusturuldu += 1
            except Exception as e:
                print(f"{ERROR} Dosya yazılırken sorun oluştu ({dosya_yolu}): {e}")
        else:
            print(f"{ERROR} {kanal_adi} için yayın linki alınamadı, bu kanal atlanıyor.")
            
    return kanallar_olusturuldu

if __name__ == "__main__":
    olusturulan_sayisi = m3u8_dosyalarini_olustur()
    if olusturulan_sayisi > 0:
        print(f"\n{GREEN}İşlem tamamlandı! Toplam {olusturulan_sayisi} kanal güncellendi.{RESET}")
    else:
        print(f"\n{RED}İşlem tamamlandı ancak hiçbir kanal için link alınamadı.{RESET}")
