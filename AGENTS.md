# Air-Cooler-Main — Agent Memory

## Project
Streamlit-based air-cooled heat exchanger sizing/rating tool. Python 3.13, CoolProp + ht + fluids + neqsim (Java bridge via JPype).

## Architecture
- `air_cooler_main_app.py` — Streamlit UI (login, sizing/rating tabs, admin panel)
- `air_cooler_main_core.py` — `AirFinnedGasCooler` class, all engineering calculations
- `air_cooler_neqsim.py` — neqsim wrapper (JVM mgmt, NeqSimFluid, EOS risk, fallback)
- `air_cooler_users.py` — auth/user DB
- `air_cooler_sizing.py` — preliminary sizing
- `tests/test_air_cooler_main.py` — 34 regression tests
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
- neqsim GERG-2008 matches CoolProp HEOS within 0.024% on Δh

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

## Test Commands
```bash
# All tests (neqsim + regression)
export JAVA_HOME=/tmp/java21_arm/jdk-21.0.11+10/Contents/Home
python3 -m pytest tests/ -v

# Regression only
python3 -m pytest tests/test_air_cooler_main.py -v

# neqsim model validation
python3 -m pytest tests/test_neqsim_models.py -v

# EOS benchmark
python3 tests/test_benchmark_eos.py

# Run streamlit
streamlit run air_cooler_main_app.py
```

## Requirements
- Java JDK 11+ (tested with `/tmp/java21_arm/jdk-21.0.11+10/Contents/Home`)
- neqsim 3.13.0 via `JPype1` + Java `.jar`
- CoolProp, ht, fluids, pandas, plotly, streamlit
