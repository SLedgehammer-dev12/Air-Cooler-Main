# TASK

## Mevcut Odak

`Air Cooler Main` hattını mühendislik ön boyutlandırma, hava tarafı modelleme ve paketleme kalitesi açısından ileri taşımak.

## Son Tamamlananlar

- Çalışma klasörü kalıcı olarak `Air Cooler Main` altında kuruldu.
- Çekirdek hesap motoru UI'dan ayrıldı.
- Belirsiz iki-faz `P-T` noktaları güvenli hata ile engellendi.
- İdeal gaz referansı düzeltildi.
- UA / LMTD / gerekli alan ön boyutlandırması eklendi.
- Gas cooler şeması oluşturuldu ve A1/A2/B1/B2/C1 giriş yerleşimi kuruldu.
- Birim testleri ve Streamlit smoke testleri başarıyla çalıştırıldı.
- PyInstaller ile Windows standalone paket oluşturuldu.
- Public GitHub repo ve `v3.6.0` release yayınlandı.

## Şu An Nerede Kaldık

- Uygulama kaynak kodu repoda.
- Windows dağıtım paketi release'e yüklendi.
- Standalone paket smoke testte çalıştı.
- Bir sonraki gerçek mühendislik adımı hava tarafı modelini derinleştirmek.

## Sıradaki Teknik İşler

1. Hava debisi hesaplarını ekle.
2. Fan gücü ve yüz hızı modelini ekle.
3. Air-side pressure drop tahmini ekle.
4. Paketleme boyutunu küçült.
5. Gerekirse gerçek drag-drop etkileşimi için custom Streamlit component değerlendir.

## Referanslar

- Repo: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main`
- Release: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main/releases/tag/v3.6.0`
- Paket: `dist\AirCooler_Main\AirCooler_Main.exe`
- Release asset: `AirCooler_Main-v3.6.0-windows-x64.zip`
