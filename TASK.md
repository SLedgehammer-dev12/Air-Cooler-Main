# TASK

## Mevcut Odak

`Air Cooler Main` hattını mühendislik ön boyutlandırma, hava tarafı modelleme ve paketleme kalitesi açısından ileri taşımak.

## Son Tamamlananlar

- CoolProp fluid adları düzeltildi (`I-BUTANE`→`ISOBUTANE`, `I-PENTANE`→`ISOPENTANE`).
- `COOLPROP_ALIASES` alias sistemi eklendi (geriye dönük uyumluluk).
- Editable kompozisyon tablosu eklendi (yüzdeler doğrudan düzenlenebilir).
- 4 ondalık haneli hassasiyet (`%.4f`) ile yüzde giriş/görüntüleme.
- %99 normalizasyon desteği (toplam ≥ %99 → normalize edilir).
- 8 yeni test ile toplam 34 teste ulaşıldı, coverage %93.
- Sürüm 3.7.1'e yükseltildi; tüm release dosyaları güncellendi.

## Şu An Nerede Kaldık

- v3.7.1 release hazır: CHANGELOG, RELEASE_NOTES, CONTINUITY, TASK güncel.
- Tüm bağımlılıklar requirements.txt'de tanımlı.
- Testler 34/34 başarılı, coverage %93.
- `COOLPROP_ALIASES` ile eski `I-BUTANE`/`I-PENTANE` kullanan şablonlar çalışmaya devam eder.

## Sıradaki Teknik İşler

1. Streamlit login arayüz CSS zenginleştirmesi (glassmorphism vb.).
2. Admin/User dinamik yönetim arayüzü (kullanıcı ekleme/çıkarma).
3. Paketleme boyutunu küçült.
4. Gerekirse gerçek drag-drop etkileşimi için custom Streamlit component değerlendir.

## Referanslar

- Repo: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main`
- Release: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main/releases/tag/v3.7.1`
- Release asset: `AirCooler_Main-v3.7.1-windows-x64.zip`
- Release asset: `AirCooler_Main-v3.7.1-macos-arm64.dmg`
