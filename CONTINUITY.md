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
- Test kapsamı %93 (34 birim testi başarıyla geçiyor).
- Editable kompozisyon tablosu eklendi (yüzdeler doğrudan düzenlenebilir).
- 4 ondalık haneli hassasiyet (`%.4f`) ile yüzde giriş/görüntüleme.
- %99 normalizasyon desteği (toplam >= %99 → normalize edilerek hesaplanır).
- `I-BUTANE` / `I-PENTANE` CoolProp fluid adları `ISOBUTANE` / `ISOPENTANE` olarak düzeltildi; alias sistemi eklendi.
- macOS standalone paket üretildi ve çalıştığı doğrulandı.
- `requirements.txt`, `app.py` imports, PyInstaller spec güncellendi.

## Son Bu Oturumda Yapılanlar

1. CoolProp fluid adları düzeltildi (`I-BUTANE`→`ISOBUTANE`, `I-PENTANE`→`ISOPENTANE`).
2. `COOLPROP_ALIASES` geriye dönük uyumluluk haritası eklendi; `resolve_fluid_name()` fonksiyonu ile tüm CoolProp çağrıları alias üzerinden çözümleniyor.
3. Editable kompozisyon tablosu: Mevcut karışım satırlarında `number_input` ile yüzde düzenleme.
4. Tüm yüzde girişleri `%.4f` formatına yükseltildi (step=0.0001).
5. `validate_inputs` fonksiyonunda toplam kontrolü `abs(total-100) > 0.001` → `total < 99.0` olarak değiştirildi.
6. Normalizasyon flag'i (`ara_sonuclar["normalize_edildi"]`) core'a eklendi.
7. 8 yeni test (ISOBUTANE/ISOPENTANE, alias, normalize, 4dp, invalid fluid, tüm bileşen validasyonu).
8. Testler 34/34 başarılı, coverage %93.

## Doğrulama Özeti

- `python3 -m pytest tests/test_air_cooler_main.py -v` -> `34 tests OK`
- `coverage report -m` -> `TOTAL: 93% coverage`

## Repo ve Release Bilgisi

- Repo: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main`

## Bir Sonraki Mantıklı Adım

1. Streamlit login arayüzünün görünümünü zenginleştirmek (CSS özelleştirmeleri, glassmorphism vb.).
2. admin/user rollerinin dinamik yönetilmesi için kullanıcı ekleme/çıkarma arayüzü eklemek.

## Paket Notu

macOS dağıtımı için `dist/AirCooler_Main` klasörü içindeki `AirCooler_Main` çalıştırılabilir dosyası, aynı klasördeki `_internal` diziniyle birlikte dağıtılmalıdır.
