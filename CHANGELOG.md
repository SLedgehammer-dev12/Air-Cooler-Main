# CHANGELOG

## 3.7.0 - 2026-06-03

- **Güvenli Giriş Sistemi:** Şifreleri SHA-256 + Tuzlama (Salt) ile saklayan ve doğrulayan giriş altyapısı eklendi.
- **Rol Tabanlı Arayüz (admin/user):** Gelişmiş boyutlandırma sekmesi (`📐 Gelişmiş Boyutlandırma`) yalnızca `admin` kullanıcısına görünür hale getirildi, `user` yetkileri kısıtlandı.
- **Gelişmiş Çapraz Akış Sizing ve Rating Modülleri:** Briggs-Young ısı transfer katsayısı, ESDU hava tarafı basınç kaybı ve fan motor gücü hesaplamaları entegre edildi.
- **Test ve Kapsam Artışı:** Yeni birim testleri ile test coverage oranı %91'e yükseltildi.
- **macOS standalone Paket Desteği:** PyInstaller yapılandırması çapraz platform (Windows/macOS) uyumlu hale getirilerek macOS standalone paketi başarıyla derlendi.

## 3.6.0 - 2026-04-15

- Giriş ekranı, gas cooler şeması etrafındaki A1/A2/B1/B2/C1 kartları ile yeniden tasarlandı.
- `assets/gas_cooler_schematic.svg` eklendi ve veri girişleri ekipman bölgeleriyle eşleştirildi.
- UA / LMTD / gerekli alan ön boyutlandırması yeni arayüz ile birlikte korunarak rapora bağlandı.
- Windows standalone paket `dist\AirCooler_Main` altında PyInstaller ile oluşturuldu.
- Public repo `SLedgehammer-dev12/Air-Cooler-Main` açıldı.
- `v3.6.0` GitHub release yayınlandı ve Windows zip paketi release varlığı olarak yüklendi.

## 3.5.0 - 2026-04-15

- UA / LMTD / gerekli alan ön boyutlandırma hesapları eklendi.
- Hava giriş/çıkış sıcaklığı, kullanıcı tanımlı U ve LMTD düzeltme faktörü F girdileri eklendi.
- LMTD için fiziksel olmayan terminal sıcaklık kombinasyonları açık hata ile engellendi.
- Yeni boyutlandırma testleri eklendi ve gerçek ortam smoke testleri çalıştırıldı.

## 3.4.0 - 2026-04-15

- `Air Cooler Main` çalışma klasörü oluşturuldu.
- Versiyona bağlı dosya adları kaldırıldı ve `Main` isimlendirmesine geçildi.
- Hesap motoru `air_cooler_main_core.py` dosyasına ayrıldı.
- Belirsiz iki faz `P-T` girişleri için güvenli hata akışı eklendi.
- İdeal gaz referansı `cp0mass()` ile düzeltildi.
- Kullanıcı tercih dosyası kullanıcı profiline taşındı.
- Yeni test, continuity ve backlog markdown dosyaları eklendi.
