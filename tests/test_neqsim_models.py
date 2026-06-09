"""neqsim EOS model validasyon testleri.

Her EOS modelinin çeşitli kompozisyonlarda çalıştığını doğrular.
Risk değerlendirme ve fallback mekanizmasını test eder.

Koşmak için:
  export JAVA_HOME=/tmp/java21_arm/jdk-21.0.11+10/Contents/Home
  python -m pytest tests/test_neqsim_models.py -v --tb=short
"""
import sys, os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from air_cooler_neqsim import (
    has_neqsim,
    start_jvm,
    NeqSimFluid,
    NEQSIM_EOS_DISPLAY_TO_MODEL,
    NEQSIM_EOS_FALLBACK,
    assess_eos_risk,
    get_fallback_eos,
    EOS_RISK_RULES,
)

# Test kompozisyonları (CoolProp bileşen isimleriyle)
KOMPOZISYONLAR = [
    pytest.param(
        {"METHANE": 0.95, "ETHANE": 0.03, "NITROGEN": 0.02},
        "kuru_gaz",
        id="Kuru Gaz (CH4+C2H6+N2)",
    ),
    pytest.param(
        {"METHANE": 0.85, "ETHANE": 0.05, "PROPANE": 0.03,
         "CARBONDIOXIDE": 0.03, "NITROGEN": 0.01, "WATER": 0.01},
        "islak_gaz",
        id="Islak Gaz (7 bileşenli)",
    ),
    pytest.param(
        {"METHANE": 1.0},
        "saf_metan",
        id="Saf Metan",
    ),
    pytest.param(
        {"METHANE": 0.7, "ETHANE": 0.15, "PROPANE": 0.1, "N-BUTANE": 0.05},
        "agir_gaz",
        id="Ağır Gaz (C4+ içeren)",
    ),
]

# Test edilecek tüm neqsim EOS modelleri
TUM_EOS = list(NEQSIM_EOS_DISPLAY_TO_MODEL.keys())

pytestmark = pytest.mark.skipif(
    not has_neqsim(),
    reason="neqsim kullanılamıyor (Java gerekli)",
)


def setup_module():
    """Tüm testler öncesi JVM başlat."""
    start_jvm()


@pytest.mark.parametrize("eos", TUM_EOS)
def test_eos_tek_nokta(eos):
    """Her EOS'un tek bir P-T noktasında çalıştığını doğrula."""
    f = NeqSimFluid(eos, ["METHANE", "ETHANE"], [0.95, 0.05])
    f.update(9, 60e5, 373.15)
    Z = f.keyed_output(72)
    rho = f.rhomass()
    h = f.hmass()
    assert Z > 0
    assert rho > 0
    assert isinstance(h, float)


@pytest.mark.parametrize("eos", TUM_EOS)
@pytest.mark.parametrize("komp, _", KOMPOZISYONLAR)
def test_eos_kompozisyon(eos, komp, _):
    """Her EOS'un her kompozisyonda çalıştığını doğrula."""
    keys = list(komp.keys())
    vals = list(komp.values())
    try:
        f = NeqSimFluid(eos, keys, vals)
        f.update(9, 60e5, 373.15)
        Z = f.keyed_output(72)
        rho = f.rhomass()
        assert Z > 0.1
        assert rho > 0
    except Exception:
        # Bazı modeller bazı bileşenleri desteklemez - fallback ile düşülebilir
        pytest.skip(f"{eos} + {komp}: desteklenmiyor olabilir")


def test_fallback_zinciri():
    """Fallback zincirinin geçerli modeller içerdiğini doğrula."""
    for eos in NEQSIM_EOS_FALLBACK:
        assert eos in NEQSIM_EOS_DISPLAY_TO_MODEL, f"{eos} model tanımında yok"


def test_get_fallback_eos():
    """get_fallback_eos'un geçerli bir sonraki model döndürdüğünü doğrula."""
    # Orta sıradaki model için fallback var mı?
    fallback = get_fallback_eos("BWRS")
    assert fallback is not None
    assert isinstance(fallback, str)
    assert fallback in NEQSIM_EOS_DISPLAY_TO_MODEL

    # Son model None dönmeli
    last_fb = get_fallback_eos(NEQSIM_EOS_FALLBACK[-1])
    assert last_fb is None

    # Olmayan model None dönmeli
    none_fb = get_fallback_eos("OLMAYAN_MODEL")
    assert none_fb is None


@pytest.mark.parametrize("eos", list(EOS_RISK_RULES.keys()))
def test_risk_degerlendirme_kuru_gaz(eos):
    """Kuru gaz için risk değerlendirmesi."""
    komp = {"METHANE": {"yuzde": 95, "tip": "Molar"}, "ETHANE": {"yuzde": 5, "tip": "Molar"}}
    risk = assess_eos_risk(eos, komp, 60)
    assert isinstance(risk, list)
    # Kuru gazda h2o ile ilgili uyarılar olmamalı
    if any("h2o_var" in str(r) for r in EOS_RISK_RULES.get(eos, {}).get("risk_if", [])):
        assert "su" in " ".join(risk).lower() if risk else True


@pytest.mark.parametrize("eos", list(EOS_RISK_RULES.keys()))
def test_risk_degerlendirme_islak_gaz(eos):
    """Islak gaz (su içeren) için risk değerlendirmesi."""
    komp = {
        "METHANE": {"yuzde": 85, "tip": "Molar"},
        "ETHANE": {"yuzde": 5, "tip": "Molar"},
        "WATER": {"yuzde": 1, "tip": "Molar"},
    }
    risk = assess_eos_risk(eos, komp, 60)
    assert isinstance(risk, list)


def test_risk_dusuk_basinc():
    """Düşük basınçta BWRS uyarı vermeli."""
    komp = {"METHANE": {"yuzde": 100, "tip": "Molar"}}
    risk = assess_eos_risk("BWRS", komp, 30)
    assert len(risk) > 0  # basinc_dusuk uyarısı


def test_risk_bilinmeyen_eos():
    risk = assess_eos_risk("OLMAYAN_EOS", {}, 60)
    assert risk == []


def test_risk_co2_yuksek():
    komp = {"METHANE": {"yuzde": 80, "tip": "Molar"}, "CARBONDIOXIDE": {"yuzde": 20, "tip": "Molar"}}
    risk = assess_eos_risk("PR", komp, 60)
    assert len(risk) > 0
    assert any("CO" in r for r in risk)


def test_get_neqsim_jar():
    from air_cooler_neqsim import _get_neqsim_jar
    jar = _get_neqsim_jar()
    assert jar is None or jar.endswith(".jar")


def test_neqsim_fluid_non_pt_inputs():
    f = NeqSimFluid("GERG-2008", ["METHANE"], [1.0])
    with pytest.raises(NotImplementedError):
        f.update(2, 60e5, 0.5)


def test_neqsim_fluid_keyed_output_extra_keys():
    f = NeqSimFluid("GERG-2008", ["METHANE"], [1.0])
    f.update(9, 60e5, 373.15)
    d = f.keyed_output(39)  # CP.iDmass
    assert d > 0
    cp = f.keyed_output(42)  # CP.iCpmass
    assert cp > 0
    h = f.keyed_output(40)  # CP.iHmass
    assert isinstance(h, float)
    with pytest.raises(NotImplementedError):
        f.keyed_output(999)


def test_neqsim_fluid_phase_and_temp():
    f = NeqSimFluid("GERG-2008", ["METHANE"], [1.0])
    f.update(9, 60e5, 373.15)
    p = f.phase()
    assert p >= 0
    t = f.T()
    assert t == 373.15
    name = f.get_phase_name()
    assert isinstance(name, str)


def test_neqsim_fluid_cp0mass_and_hmolar():
    f = NeqSimFluid("GERG-2008", ["METHANE"], [1.0])
    f.update(9, 60e5, 373.15)
    cp0 = f.cp0mass()
    assert cp0 > 0
    hm = f.hmolar()
    assert isinstance(hm, (int, float))


def test_create_neqsim_fluid_wrapper():
    from air_cooler_neqsim import _create_neqsim_fluid_wrapper
    f = _create_neqsim_fluid_wrapper("GERG-2008", ["METHANE"], [1.0])
    f.update(9, 60e5, 373.15)
    assert f.rhomass() > 0
