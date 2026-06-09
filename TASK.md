# TASK

## Mevcut Odak

`Air Cooler Main` hattını mühendislik ön boyutlandırma, hava tarafı modelleme ve paketleme kalitesi açısından ileri taşımak.

## Son Tamamlananlar

- Güvenli Giriş Sistemi (SHA-256 + Salt) ve Admin/User rolleri eklendi.
- Gelişmiş 3-Kademeli Boyutlandırma (Basit/Detaylı/Değerlendirme) modülleri entegre edildi.
- Briggs-Young, Kern-Kraus, ESDU korelasyonları ile hava tarafı modeli derinleştirildi.
- Test kapsamı %93'e yükseltildi (26 test).
- `ModuleNotFoundError: No module named 'ht'` hatası giderildi.
- `requirements.txt` güncellendi; `air_cooler_main_app.py`'ye `import ht` eklendi.
- PyInstaller spec hidden imports (`ht`, `fluids`, `scipy`) eklendi.
- macOS standalone paket desteği eklendi.
- Sürüm 3.7.1'e yükseltildi.

## Şu An Nerede Kaldık

- v3.7.1 release hazır: CHANGELOG, RELEASE_NOTES, CONTINUITY güncel.
- Tüm bağımlılıklar requirements.txt'de tanımlı.
- Testler 26/26 başarılı, coverage %93.

## Sıradaki Teknik İşler

1. Streamlit login arayüz CSS zenginleştirmesi (glassmorphism vb.).
2. Admin/User dinamik yönetim arayüzü (kullanıcı ekleme/çıkarma).
3. Paketleme boyutunu küçült.
4. Gerekirse gerçek drag-drop etkileşimi için custom Streamlit component değerlendir.

## Referanslar

- Repo: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main`
- Release: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main/releases/tag/v3.6.0`
- Paket: `dist\AirCooler_Main\AirCooler_Main.exe`
- Release asset: `AirCooler_Main-v3.6.0-windows-x64.zip`
