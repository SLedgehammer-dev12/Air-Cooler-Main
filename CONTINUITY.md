# CONTINUITY

Bu dosya yeni bir oturum açıldığında projeye hızlı ve tutarlı şekilde devam etmek için tutulur.

## Read First

1. `CONTINUITY.md`
2. `TASK.md`
3. `TODO.md`
4. `ANALYSIS.md`
5. Kod tarafında:
- `air_cooler_main_core.py`
- `air_cooler_main_app.py`
- `tests/test_air_cooler_main.py`

## Güncel Durum

Tarih: 2026-06-09

Kalıcı çalışma klasörü:

- `/Users/macbook/Documents/Kodlama/Air-Cooler-Main`

Ana teknik durum:

- gerçek gaz termal yük hesabı çalışıyor
- iki-faz belirsizlik koruması var
- UA / LMTD / gerekli alan ön boyutlandırması var
- şematik giriş ekranı A1/A2/B1/B2/C1 bölgeleri ile kurulmuş durumda
- Güvenli Giriş Sistemi (Admin & User Rolleri, SHA-256 + Tuzlama) aktif hale getirildi.
- Gelişmiş 3-Kademeli Boyutlandırma ve Değerlendirme sekmesi (`📐 Gelişmiş Boyutlandırma`) eklendi ve admin rolüne kısıtlandı.
- Test kapsamı %93'e yükseltildi (26 birim testi başarıyla geçiyor).
- macOS standalone paket üretildi ve çalıştığı doğrulandı.
- `requirements.txt` eksik bağımlılıklar (`ht`, `fluids`, `scipy`) eklendi.
- `air_cooler_main_app.py`'ye `import ht` eklendi.
- PyInstaller spec'e `ht`, `fluids`, `scipy` hidden imports eklendi.

## Son Bu Oturumda Yapılanlar

1. Güvenli giriş, tuzlama ve doğrulama motoru eklendi.
2. Rol tabanlı UI kısıtlamaları kuruldu.
3. Test kapsamı %93'e çıkarılarak 13 yeni test senaryosu eklendi (geçişli Re akışı, çıkış iki-faz koruması, efektif LMTD sınırları, transport properties, gauge basınç dönüşümü, bozuk/kayıp kullanıcı DB dosyaları, düşük hava debisi rating, entegre hava sizing).
4. `ModuleNotFoundError: No module named 'ht'` hatası giderildi.
5. `requirements.txt`, `app.py` imports, ve PyInstaller spec dosyası güncellendi.
6. Sürüm 3.7.1'e yükseltildi; CHANGELOG, RELEASE_NOTES güncellendi.

## Doğrulama Özeti

- `python3 -m pytest tests/test_air_cooler_main.py -v` -> `26 tests OK`
- `coverage report -m` -> `TOTAL: 93% coverage`
- packaged launcher macOS smoke test -> `build complete, standalone folder ready`

## Repo ve Release Bilgisi

- Repo: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main`

## Bir Sonraki Mantıklı Adım

1. Streamlit login arayüzünün görünümünü zenginleştirmek (CSS özelleştirmeleri, glassmorphism vb.).
2. admin/user rollerinin dinamik yönetilmesi için kullanıcı ekleme/çıkarma arayüzü eklemek.

## Paket Notu

macOS dağıtımı için `dist/AirCooler_Main` klasörü içindeki `AirCooler_Main` çalıştırılabilir dosyası, aynı klasördeki `_internal` diziniyle birlikte dağıtılmalıdır.
