# CHANGELOG

## 3.7.2 - 2026-06-10

- **Proje Kaydet/Aç Özelliği:** Tüm girdilerin (kompozisyon, proses, geometri, üniteler) JSON formatında kaydedilip tekrar yüklenebilmesi sağlandı. (Toolbar'da 💾/📂 butonları eklendi)
- **Kapsam Artışı:** 4 yeni test eklendi (save/load roundtrip, neqsim fallback chain, transport properties exception handler, benchmark performance guard).
- **Kapsam Oranı:** Core modülünde %96'ya (toplamda %93) ulaşıldı.
- **Güvenlik/Hata Düzeltme:** EOS fallback zinciri hatası giderildi, neqsim JVM hata durumları için daha sağlam yönetim eklendi.

## 3.7.1 - 2026-06-09

- **CoolProp Fluid Adı Düzeltmesi:** `"I-BUTANE"` → `"ISOBUTANE"`, `"I-PENTANE"` → `"ISOPENTANE"` olarak düzeltildi; eski adlar için `COOLPROP_ALIASES` geriye dönük uyumluluk eklendi.
- **Editable Kompozisyon Tablosu:** Mevcut karışım tablosundaki yüzde değerleri artık doğrudan düzenlenebilir hale getirildi (number_input ile).
- **4 Ondalık Haneli Hassasiyet:** Tüm yüzde girişleri ve görüntülemeler `%.4f` formatına yükseltildi.
- **%99 Normalizasyon Desteği:** Bileşen toplamı en az %99.00 olduğunda, otomatik normalize edilerek hesaplamaya izin veriliyor.
- **Bağımlılık Yönetimi Düzeltmesi:** `requirements.txt`'ye eksik bağımlılıklar (`ht`, `fluids`, `scipy`) eklendi; `air_cooler_main_app.py`'ye `import ht` eklendi; PyInstaller spec'e hidden imports tanımlandı.
- **Test Kapsamı Artışı:** 8 yeni test ile toplam 34 teste ulaşıldı, coverage %93 korunuyor.

## 3.7.0 - 2026-06-03

- **Güvenli Giriş Sistemi:** Şifreleri SHA-256 + Tuzlama (Salt) ile saklayan ve doğrulayan giriş altyapısı eklendi.
- **Rol Tabanlı Arayüz (admin/user):** Gelişmiş boyutlandırma sekmesi (`📐 Gelişmiş Boyutlandırma`) yalnızca `admin` kullanıcısına görünür hale getirildi, `user` yetkileri kısıtlandı.
- **Gelişmiş Çapraz Akış Sizing ve Rating Modülleri:** Briggs-Young ısı transfer katsayısı, ESDU hava tarafı basınç kaybı ve fan motor gücü hesaplamaları entegre edildi.
- **Test ve Kapsam Artışı:** Yeni birim testleri ile test coverage oranı %93'e yükseltildi.
- **macOS standalone Paket Desteği:** PyInstaller yapılandırması çapraz platform (Windows/macOS) uyumlu hale getirilerek macOS standalone paketi başarıyla derlendi.
- **Bağımlılık Yönetimi:** `requirements.txt`'ye eksik bağımlılıklar (`ht`, `fluids`, `scipy`) eklendi; `air_cooler_main_app.py`'ye `import ht` eklendi; PyInstaller spec'e hidden imports tanımlandı.

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
