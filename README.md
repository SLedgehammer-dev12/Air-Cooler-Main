# Air Cooler Main

Doğal gaz ve hidrokarbon karışımları için gerçek gaz bazlı gaz soğutucu termal yük ve ön boyutlandırma hesaplayıcısı.

## Ana Dosyalar

- `air_cooler_main_app.py`
  - Streamlit arayüzü.
- `air_cooler_main_core.py`
  - Termodinamik hesap motoru ve UA/LMTD/alan ön boyutlandırması.
- `run_air_cooler_main.py`
  - Windows launcher.
- `air_cooler_main.spec`
  - PyInstaller yapılandırması.
- `air_cooler_main_templates.json`
  - Hazır gaz şablonları.

## Hızlı Başlangıç

```powershell
python -m pip install -r requirements.txt
streamlit run air_cooler_main_app.py
```

## Test

```powershell
python -m unittest tests\test_air_cooler_main.py
```

## Build

```powershell
build_air_cooler_main.bat
```

## Dokümanlar

- `ANALYSIS.md`: kod tabanı ve teknik bulgular
- `CONTINUITY.md`: oturumlar arası devamlılık rehberi
- `TASK.md`: mevcut odak ve son tamamlanan işler
- `TODO.md`: teknik backlog
- `CHANGELOG.md`: sürüm geçmişi
