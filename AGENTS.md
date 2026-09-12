# Air-Cooler-Main — Agent Memory

## Project
Streamlit-based air-cooled heat exchanger sizing/rating tool. Python 3.13, CoolProp + ht + fluids + neqsim (Java bridge via JPype). Current version: **5.0.0**.

## Architecture
- `air_cooler_main_app.py` — Streamlit UI (login, sizing/rating tabs, admin panel)
- `air_cooler_main_core.py` — `AirFinnedGasCooler` class, all engineering calculations
- `air_cooler_neqsim.py` — neqsim wrapper (JVM mgmt, NeqSimFluid, EOS risk, fallback)
- `air_cooler_users.py` — auth/user DB (PBKDF2, register, admin CRUD)
- `air_cooler_sizing.py` — preliminary sizing
- `air_cooler_export.py` — PDF/Excel rapor export + proje yönetimi (reportlab + openpyxl)
- `tests/test_air_cooler_main.py` — 94 regression tests
- `tests/test_air_cooler_users.py` — 45 user management tests
- `tests/test_neqsim_models.py` — 73 neqsim model validation tests
- `tests/test_benchmark_eos.py` — EOS benchmark (HEOS/PR/SRK/GERG-2008)

## EOS / Engine System
Two-level selection: **Engine** (CoolProp / neqsim) → **EOS** filtered by engine.
- CoolProp: HEOS, PR, SRK
- neqsim: GERG-2008, PR, SRK, PR-MC, SRK-MC, PR-volcor, SRK-volcor, CPA-SRK, BWRS, PSRK
- Legacy positional arg `eos_secimi="HEOS"` still supported (auto-detects engine)
- Failed neqsim EOS falls back through chain → HEOS

## Key Decisions
- Risk warnings shown for certain EOS+composition combos (e.g. CPA-SRK needs H₂O, BWRS needs P>50 bar)
- Admin-only comparison table runs all neqsim models side-by-side
- Plotly bar chart in comparison (percent diff from reference)
- JVM started on demand (lazy), `_JVM_STARTED` flag prevents double-init
- `has_neqsim()` negative-caches a failed import (`_IMPORT_ATTEMPTED`) — without Java the no-Java path is ~0.4s once, then instant
- neqsim GERG-2008 matches CoolProp HEOS within 0.024% on Δh
- `serialize_inputs(state)` / `load_project_file(data, state)` accept optional state param for testability
- All ~40 unkeyed inputs now have `key=` session_state bindings for save/load serialization
- Passwords hashed with PBKDF2-HMAC-SHA256 (100k iterations) — legacy SHA-256 hashes migrated on load
- `air_cooler_users.py` is standalone; `air_cooler_main_core.py` re-exports its public API for backward compat
- Per-instance bounded cache (`self._cache`) memoizes `_h_at_pt` and `get_mixture_transport_properties` by (P, T) — speeds up segmental loops

## Save/Load & Project Management
- Proje dosyası: `.json` formatı (`version: "2.0"` — artık `results` alanını da içerir)
- **💾 Proje Yönetimi** expander (Girişler sekmesi üstü):
  - Proje adı + açıklama girerek **Sunucuya Kaydet** (`~/Air Cooler Main/projects/`)
  - **Kayıtlı Projeler** listesi → Yükle / Dışa Aktar / Sil
  - **Dosyadan Aç** (manuel `.json` yükleme) — geriye uyumlu
- `serialize_inputs()` artık `last_res` (hesaplama sonuçları) içerir
- `load_project_file()` sonuçları geri yükler
- 3 test: serialize_inputs yapısı, load_project_file geri yükleme, roundtrip uyumu

## Benchmark Results (Q match vs HEOS)
| Scenario | PR | SRK | GERG-2008 |
|---|---|---|---|
| Kuru Gaz (CH4 95%) | +0.609% | +0.756% | **+0.024%** |
| Yüksek Basınç (CH4 85%) | -0.676% | +0.226% | **+0.113%** |
| Süperkritik | -3.891% | -2.308% | **-0.006%** |
| Kütlesel Baz | HATA | HATA | **+0.041%** |

**Performance** (50 iterasyon): HEOS 17.2ms, GERG-2008 4.4ms (3.9× faster), PR/SRK 0.047ms (367× faster)

## Known Bugs Fixed (2026-06-09)
1. **KeyError** on first visit to "Gelişmiş Hesaplama" tab — `st.session_state.adv_eos_label` accessed before initialization
2. **Dead code** `eos_warning_accepted` — was set but never read; now controls expander collapse + button visibility
3. **Missing risk warnings** in "Hızlı Hesaplama" tab — now has full risk assessment + Geç/Devam Et buttons

## Known Bugs Fixed (2026-06-13 — v4.0.0)
1. **CRITICAL: Pitch solver inconsistency** — `AirCooledExchanger` called with `pitch`/`angle` instead of `pitch_normal`/`pitch_parallel`. User's 63.5 mm pitch_normal was halved to 31.75 mm by `pitch_angle_solver(angle=30)`, causing physical tube overlap. Fixed via `resolve_pitches()` + direct parameter passing.
2. **Two-phase crash** — `get_mixture_transport_properties(P_avg, T_avg)` crashed for condensing cases where T_avg falls in two-phase envelope. Fixed with saturation check + quality-weighted property blending.
3. **Missing condensation h_inside** — Shah correlation now used for condensing cases instead of single-phase Dittus-Boelter.
4. **Missing two-phase dP** — Lockhart-Martinelli multiplier now applied for condensing cases.
5. **Dead code** — `c3plus_pct` in `assess_eos_risk()` was computed but never used. Removed.

## Known Bugs Fixed (2026-08-20 — v5.0.0)
1. **Fan "uç hızı" yanlış değişkenle hesaplanıyordu** — API 661 tip-speed kontrolü, gerçek uç hızı yerine fan **yüzey hızını** (`V_air/A_fan`) kullanıyordu. Artık `fan_tip_speed = π·D·RPM/60` ile hesaplanıyor ve kontrol bu değere bağlandı.
2. **Yoğuşmada PT-flash çökmesi** — `T_sat_liq = T_bubble + 0.1` ve `T_sat_vap = T_dew - 0.1` işaretleri iki-faz bölgesine düşüyordu (CoolProp "gaseous density" hatası). İşaretler düzeltildi; ayrıca `get_mixture_transport_properties` iki-faz P-T noktalarında kalite-ağırlıklı yoğunluk/cp fallback'ine sahip.
3. **`has_neqsim()` negatif önbellekleme yoktu** — Java yokken her çağrı neqsim import'unu yeniden deniyordu (~0.44s + hata çıktısı), test paketini 100s+ yapıyordu. `_IMPORT_ATTEMPTED` flag eklendi.

## Known Bugs Fixed & Architecture Refactor (2026-09-12 — Post-Review)
1. **CRITICAL (P0): Enthalpy/Flash-Based Rating Engine** — `hesapla_degerlendirme_rating` tek sabit cp ve ε-NTU ile çözülüyordu; yoğuşmalı akışkanlarda latent ısıyı duyulur ısı gibi bölerek eksi/akıldışı sıcaklıklar üretiyordu. Artık $Q$ üzerinde Brent kök-bulucu (`scipy.optimize.brentq`), $(T, H)$ soğuma profili interpolasyonu ve $Q \to h_{out} \to \text{flash} \to T_{out}, x_{out} \to U \to \text{yeni } Q$ mimarisiyle çalışır.
2. **CRITICAL (P1): Segmental Çapraz Akış Ft Düzeltmesi** — `_compute_segment_areas` içinde $F_t$ faktörü 1.0 varsayılıyordu. Artık her segment için `ht.air_cooler.Ft_aircooler` ile yerel çapraz akış faktörü hesaplanır (izotermal yoğuşmada $F_t = 1.0$).
3. **Süreç Tarafı Birleşik Basınç Kaybı Modeli** — Sizing ve rating'de kollektör, nozül ve boru dönüş kayıpları ($K_{minor} = 1.5(N-1) + K_{header} + K_{nozzle}$) sürtünme kaybına eklenerek birleştirildi; `gas_dP_bar`, `gas_dP_friction_bar`, `gas_dP_minor_bar` olarak raporlanır.
4. **NeqSim PQ-Flash Fallback Şeffaflığı** — NeqSim motorunda çiğ/kabarcık noktası CoolProp HEOS'a düştüğünde arayüzde ve metadatada `saturation_fallback_applied` uyarısı verilir.
5. **Sıvı Taşıma Özellikleri** — `get_mixture_transport_properties` sıvı fazda Wilke/Mason-Saxena gaz formülleri yerine logaritmik viskozite ($\ln \mu = \sum y_i \ln \mu_i$) ve sıvıya uygun fallback ($1.0 \times 10^{-4}$ Pa·s) kullanır.
6. **Yazılım & UI Hataları** — ASME kontrolünde mutlak Pa dönüşümü, JSON serileştirmede Pint Quantity ve Dataclass özyinelemeli temizleme, proje yüklemede `ui_p_u`/`ui_t_u`/`ui_flow_u` eşleştirmesi, ana raporda multi-model şema ayrımı, API 661 "screening checks" terminolojisi düzeltildi.

## v5.0.0 New Features
- **Wilke / Mason-Saxena karışım μ & k** — `get_mixture_transport_properties` doğrusal toplama yerine Wilke viskozite + Mason-Saxena iletkenlik korelasyonları kullanır (tek bileşende saf değer, hata durumunda doğrusal fallback).
- **Rouhani-Axelsson void fraction** — yoğuşmalı karışım yoğunluğu slip-ratio modeliyle (`_mixture_surface_tension` ile yüzey gerilimi), homojen modele düşer.
- **Segmental (zone-by-zone) hesap** — `_compute_segment_areas`: ısı yükü 12 eşit entalpi segmentine bölünür; her segmentte ayrı U/h/alan + hava sıcaklık profili; yoğuşma segmentlerinde Shah + Silver-Bell-Ghaly düzeltmesi. `hesapla_detayli_dizayn` geriye uyumlu kalır, sonuçlara `segments`/`segmental_applied` ekler.
- **Gerçek fan uç hızı + dB(A)** — `fan_tip_speed()`, `estimate_fan_sound_power_level()`; RPM girdisi, 61/50 m/s API 661 tip-speed kontrolü, gürültü tahmini.
- **Kanat tipi + API 661 sıcaklık limitleri** — `FIN_TYPE_LIMITS_C` / `fin_type_temperature_limit_C()` (L-Foot 130, KL 250, Embedded 400, Extruded 350 °C).
- **ASME VIII Div.1 App.1-1** — `required_tube_wall_thickness()`/`with_ca()`; CA girdisi + malzeme sınıfı (A179, 316L, Duplex) + mekanik et kalınlığı doğrulaması.
- **Header tipi + nozül kayıpları** — `HEADER_TYPES` / `header_minor_loss_k()`; tapalı/kapaklı/başlıklı kollektör + giriş/çıkış nozülü K kayıpları dP'e eklendi.
- **Draft tipi (Forced/Induced)** — fan yoğunluğu fan konumuna göre (forced→T_air,in, induced→T_air,out).
- **PT Faz Zarfı** — `get_phase_envelope()` (CoolProp HEOS/PR/SRK + tek bileşen), kritik/cricondentherm/cricondenbar + giriş/çıkış noktası işaretli Plotly grafiği.
- **Grafikler** — `draw_temperature_profile` (proses+hava T vs alan) ve `draw_bundle_layout` (boru demeti kesiti).
- **API 661 Data Sheet bölümleri** — PDF/Excel'e Proses / Performans / Boru & Kanat Geometrisi / Mekanik & Malzeme bölümleri.
- **Akıllı EOS Öneri Sistemi** — `recommend_eos()`: Girilen akışkan kompozisyonu (saf akışkan, ıslak gaz, LPG/NGL yoğuşma, asit gaz, yüksek basınç) ve basınca göre en uygun EOS (HEOS, GERG-2008, CPA-SRK, PR-volcor, PR) önerir; gerekçesini açıklar ve arayüzde tek tıkla uygulama sunar.

## v4.0.0 New Features
- **Gnielinski correlation** replaces Dittus-Boelter for tube-side Nusselt (Re>2300)
- **API 661 fan power** includes dynamic pressure (½ρv²) + plenum losses (10%)
- **API 661 compliance panel** checks tube OD, wall thickness, fan tip speed
- **Password change flow** — default password detection + change form on login
- **Fan geometry inputs** — fan diameter (m) and fan count for accurate fan power
- **PDF/Excel Export** — reportlab + openpyxl ile rapor indirme (sizing + rating)
- **Project Management** — sunucu tarafı depolama (`~/Air Cooler Main/projects/`), proje adı/açıklama, sonuç kaydı, yükle/sil/dışa aktar
- **User Management** — `air_cooler_users.py`: PBKDF2-HMAC-SHA256, admin panel (CRUD), self-registration, email/metadata, last_login takibi
- **Backward compatible** — all 53+45 existing tests pass; legacy SHA-256 hashes migrated on load

## Build & Release
- macOS: `air_cooler_main_macos.spec` → `.app` bundle → `.dmg` (ARM64)
- Windows: `air_cooler_main.spec` → `_internal` folder → `.zip` (x64)
- Entry point: `run_air_cooler_main.py` (Streamlit launcher with auto-port + browser open)
- Scripts: `build/build_macos.sh`, `build/build_windows.bat`

## Test Commands
```bash
# All tests (neqsim + regression) — JAVA_HOME opsiyonel (otomatik bulunur)
# Java yoksa: macOS'a Temurin JDK kurun veya:
#   curl -L -o /tmp/temurin21.tar.gz "https://api.adoptium.net/v3/binary/latest/21/ga/mac/aarch64/jdk/hotspot/normal/eclipse"
#   mkdir -p /tmp/java21_arm && tar -xzf /tmp/temurin21.tar.gz -C /tmp/java21_arm
export JAVA_HOME=/tmp/java21_arm/jdk-21.0.12.1+1/Contents/Home   # opsiyonel
python3 -m pytest tests/ -v

# Regression only
python3 -m pytest tests/test_air_cooler_main.py -v

# User management only
python3 -m pytest tests/test_air_cooler_users.py -v

# neqsim model validation
python3 -m pytest tests/test_neqsim_models.py -v

# EOS benchmark
python3 tests/test_benchmark_eos.py

# Run streamlit
streamlit run air_cooler_main_app.py
```

## Requirements
- Java JDK 11+ (tested with Temurin-21; otomatik tespit: `/tmp/java21_arm/*/Contents/Home`)
- neqsim 3.13.0 via `JPype1` + Java `.jar`
- CoolProp, ht, fluids, pandas, plotly, streamlit
