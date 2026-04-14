# CONTINUITY

Bu dosya, yeni bir oturum açıldığında projeye hızlı ve tutarlı şekilde devam etmek için tutulur.

## Read First

Yeni bir session başlarken şu sırayla ilerle:

1. `CONTINUITY.md`
2. `TASK.md`
3. `TODO.md`
4. `ANALYSIS.md`
5. Sonra ilgili kod dosyaları:
- `air_cooler_main_core.py`
- `air_cooler_main_app.py`
- `tests/test_air_cooler_main.py`

## Current Status

Tarih: 2026-04-15

`Air Cooler Main` klasörü, bundan sonraki geliştirmelerin kalıcı çalışma alanı olarak kullanılıyor.

Tamamlanan ana geçişler:

- kaynak dosyalar versiyonsuz `Main` isimlerine taşındı
- hesap motoru UI katmanından ayrıldı
- iki faz belirsizliği için güvenli hata akışı eklendi
- test ve build iskeleti güncellendi
- operasyonel markdown dosyaları oluşturuldu
- UA / LMTD / gerekli alan ön boyutlandırması eklendi
- giriş ekranı gas cooler şeması etrafında yeniden kurgulandı

## Last Completed Work

1. Yerel `.venv` kuruldu ve bağımlılıklar yüklendi.
2. Birim testleri, termodinamik smoke testleri ve Streamlit sağlık kontrolü çalıştırıldı.
3. UA / LMTD / gerekli alan ön boyutlandırması çekirdeğe ve rapor ekranına bağlandı.
4. `assets/gas_cooler_schematic.svg` eklendi.
5. `air_cooler_main_app.py` içinde A1/A2/B1/B2/C1 odaklı şematik giriş düzeni kuruldu.

## Verified Commands

```powershell
python -m py_compile air_cooler_main_core.py air_cooler_main_app.py run_air_cooler_main.py tests\test_air_cooler_main.py
.venv\Scripts\python -m unittest tests\test_air_cooler_main.py
.venv\Scripts\python -m streamlit run air_cooler_main_app.py --server.headless true
```

## Open Items

1. PyInstaller çıktısı küçültülmeli.
2. Hava tarafı modeli genişletilmeli.
3. Fan gücü, hava debisi ve yüz hızı hesapları eklenmeli.
4. Gerekirse gerçek drag-drop etkileşimi için custom component düşünülmeli.

## Next Recommended Step

En mantıklı sonraki adım:

`air_cooler_main_core.py` üzerine hava tarafı mühendislik modelini eklemek.

Önerilen sıra:

1. Hava debisi
2. Fan gücü
3. Face velocity
4. Air-side pressure drop

## Session Update Template

```text
### YYYY-MM-DD

Yapılanlar:
- ...

Doğrulama:
- ...

Açık kalanlar:
- ...

Bir sonraki adım:
- ...
```

### 2026-04-15

Yapılanlar:
- Proje altında `.venv` oluşturuldu.
- `requirements.txt` bağımlılıkları kuruldu.
- Birim testleri gerçek ortamda çalıştırıldı.
- Çekirdek hesaplar için gaz, yoğuşma ve belirsiz iki-faz smoke testleri koşturuldu.
- Streamlit sağlık endpoint'i `/_stcore/health` üzerinden doğrulandı.
- UA / LMTD / gerekli alan ön boyutlandırması eklendi ve test edildi.
- Gas cooler şeması eklendi ve giriş ekranı ekipman bölgelerine göre düzenlendi.

Doğrulama:
- `.venv\\Scripts\\python -m unittest tests\\test_air_cooler_main.py`
- `HEALTH_OK ok`

Açık kalanlar:
- Build boyutu optimizasyonu
- Tasarım/boyutlandırma hesaplarının hava tarafında derinleştirilmesi

Bir sonraki adım:
- Hava debisi, fan gücü ve yüz hızı modelini ekle
