# CHANGELOG

## 3.6.0 - 2026-04-15

- Giriş ekranı, gas cooler şeması etrafındaki A1/A2/B1/B2/C1 kartları ile yeniden tasarlandı.
- `assets/gas_cooler_schematic.svg` eklendi ve veri girişleri ekipman bölgeleriyle eşleştirildi.
- Proses, hava ve UA girdileri fiziksel konum mantığına göre ayrıştırıldı.
- Mevcut termal yük ve UA/LMTD akışı yeni şematik yerleşime taşındı.

## 3.5.0 - 2026-04-15

- UA / LMTD / gerekli alan ön boyutlandırma hesapları eklendi.
- Hava giriş/çıkış sıcaklığı, kullanıcı tanımlı U ve LMTD düzeltme faktörü F girdileri eklendi.
- LMTD için fiziksel olmayan terminal sıcaklık kombinasyonları açık hata ile engelleniyor.
- Yeni boyutlandırma testleri eklendi ve gerçek ortam smoke testleri çalıştırıldı.

## 3.4.0 - 2026-04-15

- `Air Cooler Main` çalışma klasörü oluşturuldu.
- Versiyona bağlı dosya adları kaldırıldı ve `Main` isimlendirmesine geçildi.
- Hesap motoru `air_cooler_main_core.py` dosyasına ayrıldı.
- Belirsiz iki faz `P-T` girişleri için güvenli hata akışı eklendi.
- İdeal gaz referansı `cp0mass()` ile düzeltildi.
- Kullanıcı tercih dosyası kullanıcı profiline taşındı.
- Yeni test, continuity ve backlog markdown dosyaları eklendi.
