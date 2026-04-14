# TASK

## Mevcut Odak

`Air Cooler Main` hattını mühendislik ön boyutlandırma ve ekipman odaklı kullanıcı deneyimi açısından güçlendirmek.

## Bu Turda Tamamlananlar

- Yeni çalışma klasörü oluşturuldu.
- Dosya adları `Main` isimlerine çevrildi.
- Çekirdek hesap modülü UI'dan ayrıldı.
- İki faz bölgesine düşen belirsiz `P-T` noktaları engellendi.
- İdeal gaz referansı düzeltildi.
- Test ve build iskeleti güncellendi.
- Süreklilik markdown dosyaları oluşturuldu.
- `.venv` kuruldu ve bağımlılıklar yüklendi.
- Birim testleri ve Streamlit sağlık smoke testi çalıştırıldı.
- UA / LMTD / gerekli alan ön boyutlandırması çekirdeğe ve UI'ya eklendi.
- Boyutlandırma için yeni testler eklendi.
- Gas cooler şeması eklendi ve veri girişleri A1/A2/B1/B2/C1 bölgelerine göre yeniden yerleştirildi.

## Sıradaki Teknik İşler

1. Paketleme çıktısında gereksiz bağımlılıkları azalt.
2. Hava tarafı hesaplarını daha ileri seviyeye taşı:
- hava debisi
- fan gücü
- yüz hızları
3. Sonuç ekranına mühendislik notları ve kısıt banner'ları ekle.
4. Gerekirse gerçek drag-drop etiketleme için custom Streamlit component değerlendir.

## Hazır Kabul Kriterleri

- `streamlit run air_cooler_main_app.py` ile uygulama açılmalı.
- Gas-only senaryoda gerçek ve ideal referans yük hesaplanmalı.
- İki faz bölgesine düşen belirsiz çıkış noktası açık hata vermeli.
- Dosya isimlerinde `V3.3` bağımlılığı kalmamalı.
- Şemadaki A1/A2/B1/B2/C1 bölgeleri ile giriş kartları eşleşmeli.
