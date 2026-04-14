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

Tarih: 2026-04-15

Kalıcı çalışma klasörü:

- `D:\İş\Çalışan programlar\@Güncelleme\Natural gas Air Cooler\Air Cooler\Air Cooler Main`

Ana teknik durum:

- gerçek gaz termal yük hesabı çalışıyor
- iki-faz belirsizlik koruması var
- UA / LMTD / gerekli alan ön boyutlandırması var
- şematik giriş ekranı A1/A2/B1/B2/C1 bölgeleri ile kurulmuş durumda
- Windows standalone paket üretildi ve çalıştığı doğrulandı
- GitHub repo ve release yayınlandı

## Son Bu Oturumda Yapılanlar

1. Gas cooler çizimi eklendi.
2. Giriş ekranı şema etrafında yeniden düzenlendi.
3. `3.6.0` sürümü için PyInstaller paketi üretildi.
4. Standalone paket smoke test ile doğrulandı.
5. `SLedgehammer-dev12/Air-Cooler-Main` public repo oluşturuldu.
6. `v3.6.0` release açıldı ve Windows zip paketi yüklendi.

## Doğrulama Özeti

- `.\.venv\Scripts\python -m unittest tests\test_air_cooler_main.py` -> `5 tests OK`
- headless Streamlit health -> `ok`
- packaged launcher smoke test -> `health=ok`, `root=200`

## Repo ve Release Bilgisi

- Repo: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main`
- Release: `https://github.com/SLedgehammer-dev12/Air-Cooler-Main/releases/tag/v3.6.0`
- Commit: `2555d8cda50c414d76fb5f286008ba729e7e4dac`
- Release asset SHA-256: `10EC5A4403EE005E116C026A180BAADFB00D4EF26EBB201E7C14AA9BC0CCFD71`

## Bir Sonraki Mantıklı Adım

`air_cooler_main_core.py` üzerine hava tarafı mühendislik modelini eklemek:

1. hava debisi
2. fan gücü
3. face velocity
4. air-side pressure drop

## Paket Notu

Release edilen dağıtım tek başına sadece `.exe` değildir. Kullanıcıya dağıtılacak doğru artefakt:

- `AirCooler_Main-v3.6.0-windows-x64.zip`

Bu zip açıldıktan sonra:

- `AirCooler_Main.exe` dosyası, aynı klasördeki `_internal` ile birlikte çalıştırılmalıdır.
