# ANALYSIS

## 1. Kod Tabanı Haritası

- `air_cooler_main_app.py`
  - Streamlit UI, girdi toplama, validasyon ve rapor sunumu.
- `air_cooler_main_core.py`
  - Birim dönüşümü, faz kontrolü, gerçek gaz entalpi hesabı ve bölgesel soğutma analizi.
- `run_air_cooler_main.py`
  - Yerel Streamlit sunucusunu başlatıp tarayıcıyı açan launcher.
- `tests/test_air_cooler_main.py`
  - Çekirdek motor için regresyon testleri.

## 2. Programın Amacı

Program, verilen akışkan kompozisyonu ile giriş/çıkış basınç-sıcaklık koşullarından:

- gerçek gaz bazlı ısı yükünü
- ideal gaz referans yükünü
- giriş/çıkış faz bilgisini
- varsa desuperheating / condensing / subcooling bölge dağılımını
- hava tarafı kullanıcı girdileri üzerinden UA / LMTD / gereken alan ön tahminini

hesaplamayı amaçlar.

Bu aşamada program tam bir air cooler boyutlandırıcısı değil; esas olarak `m * Δh` tabanlı termal yük hesaplayıcısı ve ilk kademe ön alan tahmin aracıdır.

## 3. Giderilen Kritik Bulgular

### Bölgesel analiz mantığı

- Eski V3.3 akışında bazı yoğuşma senaryoları yanlışlıkla tek bölge gaz soğutma olarak sınıflanabiliyordu.
- Yeni çekirdekte bölgesel analiz yalnızca güvenli ve tekil olarak tanımlanabilen faz yolları için çalışıyor.

### Belirsiz iki faz P-T noktaları

- İki faz bölgesine düşen `P-T` noktaları yalnızca basınç ve sıcaklık ile tekil olarak tanımlanamaz.
- Program artık bu noktaları sessizce hesaplamaya çalışmak yerine açık hata ile durduruyor.

### İdeal gaz referansı

- Eski kodda "ideal gaz" değeri aslında gerçek akışkanın düşük basınçtaki `cp` değeriydi.
- Yeni sürümde referans, `cp0mass()` üzerinden ideal-gaz katkısından alınıyor.

### UI bağımlılığı

- Hesap motoru artık Streamlit `session_state` bağımlı değil.
- Atmosfer basıncı ve log callback dışarıdan veriliyor.

### Test kırılması

- Eski test dosyası V3.2 modülünü import ettiği için çalışmıyordu.
- Yeni testler `air_cooler_main_core.py` üzerinden tanımlandı.

## 4. Güncel Mimari Durum

### Güçlü Yönler

- UI ve hesap motoru ayrıldı.
- Versiyona bağlı dosya adları kaldırıldı.
- Kullanıcı tercih dosyası uygulama klasörü yerine kullanıcı profiline taşındı.
- Giriş validasyonu genişletildi.

### Açık Teknik Borçlar

- Ön boyutlandırma var, ancak fan seçimi, yüzey geometri optimizasyonu ve bundle konfigürasyonu henüz yok.
- Paketleme çıktısı halen optimize edilirse küçülebilir.
- İki faz son nokta desteği istenecekse kalite girdisi veya faz oranı alanı eklenmeli.
