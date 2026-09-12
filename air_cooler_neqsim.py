"""
neqsim (GERG-2008) thermodynamic engine wrapper for Air Cooler Main.

Requires:
  - Java JDK 11+ (tested with Temurin-21)
  - neqsim Python package (pip install neqsim)

JVM must be started before calling any neqsim functions.
"""

import os
import threading
import importlib

# Lazy import for neqsim (avoids JVM start on module load)
_HAS_NEQSIM = False
_IMPORT_ATTEMPTED = False
_neqsim = None
_jpype = None
_NEQSIM_JAR_PATH = None


def _try_import_neqsim():
    global _HAS_NEQSIM, _neqsim, _jpype, _NEQSIM_JAR_PATH, _IMPORT_ATTEMPTED
    if _IMPORT_ATTEMPTED:
        return _HAS_NEQSIM
    _IMPORT_ATTEMPTED = True
    # Ensure JAVA_HOME is set so neqsim's auto JVM start works
    _java_home = os.environ.get("JAVA_HOME") or ""
    if not _java_home or not os.path.exists(os.path.join(_java_home, "bin", "java")):
        # Try known locations
        for candidate in [
            "/tmp/java21_arm/jdk-21.0.11+10/Contents/Home",
            "/tmp/java21_arm/jdk-21.0.12.1+1/Contents/Home",
            "/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home",
            "/Library/Java/JavaVirtualMachines/jdk-21.0.2.jdk/Contents/Home",
            "/Library/Java/JavaVirtualMachines/jdk-11.0.22.jdk/Contents/Home",
            "/usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
        ]:
            if os.path.exists(os.path.join(candidate, "bin", "java")):
                os.environ.setdefault("JAVA_HOME", candidate)
                break
    try:
        _jpype_mod = importlib.import_module("jpype")
        _jpype = _jpype_mod
        _neqsim = importlib.import_module("neqsim")
        _HAS_NEQSIM = True
        import inspect
        _neqsim_dir = os.path.dirname(inspect.getfile(_neqsim))
        _jar_candidate = os.path.join(_neqsim_dir, "lib", "java11", "neqsim-3.13.0.jar")
        if os.path.exists(_jar_candidate):
            _NEQSIM_JAR_PATH = _jar_candidate
        return True
    except Exception:
        _HAS_NEQSIM = False
        return False


_JVM_LOCK = threading.Lock()
_JVM_STARTED = False
_JAVA_HOME_ENV = os.environ.get("JAVA_HOME", "")


def _get_neqsim_jar():
    return _NEQSIM_JAR_PATH

# Component name mapping: CoolProp -> neqsim
COOLPROP_TO_NEQSIM = {
    "METHANE": "methane",
    "ETHANE": "ethane",
    "PROPANE": "propane",
    "N-BUTANE": "n-butane",
    "ISOBUTANE": "i-butane",
    "N-PENTANE": "n-pentane",
    "ISOPENTANE": "i-pentane",
    "CYCLOPENTANE": "cyclopentane",
    "HEXANE": "n-hexane",
    "HEPTANE": "n-heptane",
    "OCTANE": "n-octane",
    "NITROGEN": "nitrogen",
    "CARBONDIOXIDE": "CO2",
    "WATER": "water",
    "HYDROGEN": "hydrogen",
    "OXYGEN": "oxygen",
    "ARGON": "argon",
}

# Phase mapping: neqsim phase index -> descriptive string
NEQSIM_PHASE_NAMES = {
    0: "Gaz",
    1: "İki Faz",
    2: "Sıvı",
}


def has_neqsim():
    _try_import_neqsim()
    return _HAS_NEQSIM


def start_jvm(java_home=None, jvm_path=None):
    global _JVM_STARTED
    if _JVM_STARTED:
        return True
    if not _try_import_neqsim():
        return False
    with _JVM_LOCK:
        if _JVM_STARTED:
            return True
        try:
            if _jpype.isJVMStarted():
                _JVM_STARTED = True
                return True

            # Determine JVM library path
            if jvm_path and os.path.exists(jvm_path):
                jvm_lib = jvm_path
            elif java_home:
                jvm_lib = os.path.join(java_home, "lib", "server", "libjvm.dylib")
            else:
                jvm_lib = _jpype.getDefaultJVMPath()

            if not os.path.exists(jvm_lib):
                raise FileNotFoundError(f"JVM library not found: {jvm_lib}")

            _jpype.startJVM(jvm_lib, "-Xrs", interrupt=False, convertStrings=False)

            # Add neqsim JAR to classpath
            if _NEQSIM_JAR_PATH:
                _jpype.addClassPath(_NEQSIM_JAR_PATH)

            _JVM_STARTED = True
            return True
        except Exception as e:
            _JVM_STARTED = False
            raise RuntimeError(f"Failed to start JVM: {e}")


def stop_jvm():
    global _JVM_STARTED
    if _HAS_NEQSIM and _jpype.isJVMStarted():
        _jpype.shutdownJVM()
    _JVM_STARTED = False


def _resolve_name(coolprop_name):
    return COOLPROP_TO_NEQSIM.get(coolprop_name, coolprop_name.lower())


# neqsim EOS name mapping (display -> neqsim fluid() arg)
NEQSIM_EOS_DISPLAY_TO_MODEL = {
    "GERG-2008": "GERG-2008",
    "PR": "PR",
    "PR-MC": "PR-MC",
    "PR-volcor": "PR-volcor",
    "SRK": "SRK",
    "SRK-MC": "SRK-MC",
    "SRK-volcor": "SRK-volcor",
    "CPA-SRK": "CPA-SRK-EoS",
    "BWRS": "BWRS",
    "PSRK": "PSRK-EoS",
}

# Fallback chain: if a model fails, try next in list
NEQSIM_EOS_FALLBACK = [
    "GERG-2008",
    "SRK",
    "PR",
    "PSRK",
    "BWRS",
    "SRK-MC",
    "PR-MC",
    "SRK-volcor",
    "PR-volcor",
    "CPA-SRK",
]


EOS_RISK_RULES = {
    "GERG-2008": {
        "oncelik": 1,
        "aciklama": "ISO 20765-1 standardı, tüm NG karışımları için.",
        "risk_if": [],
    },
    "PR": {
        "oncelik": 2,
        "aciklama": "Peng-Robinson, genel amaçlı kubik EOS.",
        "risk_if": [
            ("h2o_var", "PR su içeren karışımlarda düşük doğruluk — CPA-SRK veya GERG-2008 önerilir."),
            ("co2_yuksek", "CO₂ > %10 ise GERG-2008 veya SRK tercih edilir."),
        ],
    },
    "SRK": {
        "oncelik": 3,
        "aciklama": "Soave-Redlich-Kwong, hafif hidrokarbonlar için iyi.",
        "risk_if": [
            ("h2o_var", "SRK su içeren karışımlarda düşük doğruluk — CPA-SRK veya GERG-2008 önerilir."),
        ],
    },
    "CPA-SRK": {
        "oncelik": 4,
        "aciklama": "Kubik + Associasyon, su/CO₂ içeren ıslak gaz için ideal.",
        "risk_if": [
            ("h2o_yok", "Su içermeyen kuru gazda gereksiz — SRK/PR daha hızlı ve yeterli."),
        ],
    },
    "BWRS": {
        "oncelik": 5,
        "aciklama": "Benedict-Webb-Rubin-Starling, yüksek basınç (>100 bar) için.",
        "risk_if": [
            ("h2o_var", "BWRS su içeren karışımlarda güvenilir değildir."),
            ("co2_var", "BWRS CO₂ karışımlarında sınırlı doğruluk."),
            ("basinc_dusuk", "BWRS düşük basınçta (<50 bar) aşırı hesaplama — PR/SRK yeterli."),
        ],
    },
    "PSRK": {
        "oncelik": 6,
        "aciklama": "Predictive SRK, deneysel parametre yoksa kullanılır.",
        "risk_if": [],
    },
    "PR-MC": {
        "oncelik": 7,
        "aciklama": "PR + Mathias-Copeman, daha iyi buhar basıncı.",
        "risk_if": [
            ("h2o_var", "PR-MC su içeren karışımlarda düşük doğruluk."),
        ],
    },
    "SRK-MC": {
        "oncelik": 8,
        "aciklama": "SRK + Mathias-Copeman, daha iyi buhar basıncı.",
        "risk_if": [
            ("h2o_var", "SRK-MC su içeren karışımlarda düşük doğruluk."),
        ],
    },
    "PR-volcor": {
        "oncelik": 9,
        "aciklama": "PR + hacim düzeltmesi, daha iyi sıvı yoğunluğu.",
        "risk_if": [
            ("h2o_var", "PR-volcor su içeren karışımlarda düşük doğruluk."),
        ],
    },
    "SRK-volcor": {
        "oncelik": 10,
        "aciklama": "SRK + hacim düzeltmesi, daha iyi sıvı yoğunluğu.",
        "risk_if": [
            ("h2o_var", "SRK-volcor su içeren karışımlarda düşük doğruluk."),
        ],
    },
}


def assess_eos_risk(eos_name, kompozisyon, P_bar):
    """Kompozisyon ve P/T'ye göre EOS risk uyarılarını döndürür."""
    rules = EOS_RISK_RULES.get(eos_name)
    if not rules:
        return []

    has_h2o = any("WATER" in k.upper() for k in kompozisyon)
    has_co2 = any("CARBONDIOXIDE" in k.upper() or k.upper() == "CO2" for k in kompozisyon)

    warnings = []
    for condition, msg in rules.get("risk_if", []):
        if condition == "h2o_yok" and not has_h2o:
            warnings.append(msg)
        elif condition == "h2o_var" and has_h2o:
            warnings.append(msg)
        elif condition == "co2_var" and has_co2:
            warnings.append(msg)
        elif condition == "co2_yuksek" and has_co2:
            # CO2 > 10% check based on composition values
            co2_pct = sum(v.get("yuzde", 0) for k, v in kompozisyon.items()
                          if "CARBONDIOXIDE" in k.upper() or k.upper() == "CO2")
            if co2_pct > 10:
                warnings.append(msg)
        elif condition == "basinc_dusuk" and P_bar < 50:
            warnings.append(msg)

    return warnings


def get_fallback_eos(eos_name):
    """Başarısız EOS için sonraki uygun modeli döndürür."""
    idx = NEQSIM_EOS_FALLBACK.index(eos_name) if eos_name in NEQSIM_EOS_FALLBACK else -1
    if idx >= 0 and idx + 1 < len(NEQSIM_EOS_FALLBACK):
        return NEQSIM_EOS_FALLBACK[idx + 1]
    return None


COMPONENT_DISPLAY_NAMES = {
    "METHANE": "Metan (C1)",
    "ETHANE": "Etan (C2)",
    "PROPANE": "Propan (C3)",
    "N-BUTANE": "n-Bütan (nC4)",
    "ISOBUTANE": "i-Bütan (iC4)",
    "I-BUTANE": "i-Bütan (iC4)",
    "N-PENTANE": "n-Pentan (nC5)",
    "ISOPENTANE": "i-Pentan (iC5)",
    "I-PENTANE": "i-Pentan (iC5)",
    "CYCLOPENTANE": "Siklopentan",
    "HEXANE": "Hekzan (C6)",
    "HEPTANE": "Heptan (C7)",
    "OCTANE": "Oktan (C8)",
    "NITROGEN": "Azot (N2)",
    "CARBONDIOXIDE": "Karbondioksit (CO2)",
    "CO2": "Karbondioksit (CO2)",
    "WATER": "Su (H2O)",
    "HYDROGEN": "Hidrojen (H2)",
    "OXYGEN": "Oksijen (O2)",
    "ARGON": "Argon (Ar)",
}


def recommend_eos(kompozisyon, P_bar=None, current_engine=None):
    """
    Girilen akışkan kompozisyonu ve çalışma basıncına göre en uygun
    Termodinamik Motor ve EOS (Durum Denklemi) önerisini gerekçeleriyle döndürür.

    Args:
        kompozisyon (dict): {"METHANE": {"yuzde": 95, "tip": "Molar"}, ...}
        P_bar (float, optional): Çalışma basıncı [bar].
        current_engine (str, optional): Kullanıcının seçtiği mevcut motor ("🔥 CoolProp" veya "🌍 neqsim")

    Returns:
        dict: Öneri detayları içeren sözlük.
    """
    if not kompozisyon or not isinstance(kompozisyon, dict):
        return {
            "recommended_engine": "🔥 CoolProp",
            "recommended_eos": "PR",
            "recommended_label": "⚡ Peng-Robinson",
            "badge": "⚡ Hızlı Mühendislik Standardı",
            "title": "Genel Gaz Soğutma — Peng-Robinson (PR)",
            "reason": "Genel amaçlı hidrokarbon ve gaz soğutma hesaplarında Peng-Robinson (PR) yaygın olarak kabul görür.",
            "alternative_engine": "🔥 CoolProp",
            "alternative_eos": "HEOS",
            "alternative_label": "🏆 HEOS (Yüksek Doğruluk)",
            "alternative_reason": "Daha yüksek termodinamik doğruluk için çok parametreli Helmholtz modeli.",
            "fluid_type": "genel",
        }

    total = sum(float(v.get("yuzde", 0.0)) for v in kompozisyon.values() if isinstance(v, dict))
    if total <= 0:
        return None

    fractions = {
        k.upper(): (float(v.get("yuzde", 0.0)) / total) * 100.0
        for k, v in kompozisyon.items()
        if isinstance(v, dict) and float(v.get("yuzde", 0.0)) > 0
    }
    num_comps = len(fractions)
    P = float(P_bar) if (P_bar is not None and P_bar > 0) else 1.0

    water_pct = fractions.get("WATER", 0.0)
    co2_pct = fractions.get("CARBONDIOXIDE", 0.0) + fractions.get("CO2", 0.0)
    ch4_pct = fractions.get("METHANE", 0.0)
    n2_pct = fractions.get("NITROGEN", 0.0)
    h2_pct = fractions.get("HYDROGEN", 0.0)

    c2_c4_keys = ["ETHANE", "PROPANE", "N-BUTANE", "ISOBUTANE", "I-BUTANE"]
    c2_c4_pct = sum(fractions.get(k, 0.0) for k in c2_c4_keys)

    heavy_keys = ["N-PENTANE", "ISOPENTANE", "I-PENTANE", "CYCLOPENTANE", "HEXANE", "HEPTANE", "OCTANE"]
    heavy_pct = sum(fractions.get(k, 0.0) for k in heavy_keys)
    lpg_ngl_pct = c2_c4_pct + heavy_pct

    # 1. Saf Akışkan Durumu (num_comps == 1 veya tek bileşen >= 99.8%)
    dominant_comp = next((k for k, v in fractions.items() if v >= 99.8), None)
    if dominant_comp is None and num_comps == 1:
        dominant_comp = list(fractions.keys())[0]

    if dominant_comp:
        comp_disp = COMPONENT_DISPLAY_NAMES.get(dominant_comp, dominant_comp)
        return {
            "recommended_engine": "🔥 CoolProp",
            "recommended_eos": "HEOS",
            "recommended_label": "🏆 HEOS (Yüksek Doğruluk)",
            "badge": "🏆 En Yüksek Doğruluk (Gold Standard)",
            "title": f"Saf Akışkan ({comp_disp}) — CoolProp / HEOS Önerilir",
            "reason": (
                f"Tek bileşenli saf akışkanlarda ({comp_disp}) CoolProp HEOS (Helmholtz Serbest Enerjisi) modeli, "
                "NIST REFPROP referans tablolarıyla %100 uyumlu en yüksek hassasiyetli formülasyondur. "
                "İki faz ve doymuş buhar basıncı hesaplarında kübik modellere (PR/SRK) kıyasla kesin stabilite sunar."
            ),
            "alternative_engine": "🔥 CoolProp",
            "alternative_eos": "PR",
            "alternative_label": "⚡ Peng-Robinson",
            "alternative_reason": "Milisaniye mertebesinde hızlı mühendislik ön-boyutlandırması.",
            "fluid_type": "saf_akiskan",
        }

    # 2. Su / Islak Gaz İçeren Karışım (H2O >= 0.5%)
    if water_pct >= 0.5:
        if current_engine == "🌍 neqsim" or (current_engine is None and has_neqsim()):
            return {
                "recommended_engine": "🌍 neqsim",
                "recommended_eos": "CPA-SRK",
                "recommended_label": "CPA-SRK (Su/CO₂)",
                "badge": "💧 Polar & Hidrojen Bağı Standardı",
                "title": f"Su İçeren Islak Gaz (%{water_pct:.1f} H₂O) — neqsim / CPA-SRK Önerilir",
                "reason": (
                    f"Karışım %{water_pct:.2f} oranında su (H₂O) içeriyor. CPA-SRK (Cubic-Plus-Association), "
                    "su gibi polar ve hidrojen bağı oluşturan molekülleri kümelenme fiziğiyle çözerek "
                    "su çiğlenme noktası ve yoğuşmasını doğru hesaplayan endüstri standardı modeldir."
                ),
                "alternative_engine": "🔥 CoolProp",
                "alternative_eos": "HEOS",
                "alternative_label": "🏆 HEOS (Yüksek Doğruluk)",
                "alternative_reason": "CoolProp IAPWS-95 referans su ve hidrokarbon Helmholtz modeli.",
                "fluid_type": "islak_gaz",
            }
        else:
            return {
                "recommended_engine": "🔥 CoolProp",
                "recommended_eos": "HEOS",
                "recommended_label": "🏆 HEOS (Yüksek Doğruluk)",
                "badge": "💧 Polar Akışkan Referansı",
                "title": f"Su İçeren Karışım (%{water_pct:.1f} H₂O) — CoolProp / HEOS Önerilir",
                "reason": (
                    f"Karışım %{water_pct:.2f} oranında su (H₂O) içeriyor. CoolProp bünyesinde su moleküllerinin "
                    "termodinamik özelliklerini en hassas modelleyen formülasyon HEOS (IAPWS-95) durum denklemidir. "
                    "Klasik kübik modeller (PR/SRK) su içeren karışımlarda sapma gösterebilir."
                ),
                "alternative_engine": "🌍 neqsim",
                "alternative_eos": "CPA-SRK",
                "alternative_label": "CPA-SRK (Su/CO₂)",
                "alternative_reason": "neqsim kullanılabilir olduğunda polar ve su içeren akışkanlar için ideal model.",
                "fluid_type": "islak_gaz",
            }

    # 3. Çok Yüksek Basınçlı Gaz (P >= 75 bar)
    if P >= 75.0:
        if current_engine == "🌍 neqsim":
            target_eos = "BWRS" if P >= 100.0 else "GERG-2008"
            target_lbl = "BWRS (Yüksek Basınç)" if P >= 100.0 else "GERG-2008 (ISO Standardı)"
            target_badge = "⚡ Yüksek Basınç Standardı" if P >= 100.0 else "🏆 ISO 20765-1 Standardı"
            return {
                "recommended_engine": "🌍 neqsim",
                "recommended_eos": target_eos,
                "recommended_label": target_lbl,
                "badge": target_badge,
                "title": f"Yüksek Basınçlı Gaz ({P:.0f} bar) — neqsim / {target_eos} Önerilir",
                "reason": (
                    f"{P:.0f} bar gibi yüksek basınç ve süperkritik koşullarda {target_eos} modeli, "
                    "gerçek gaz sapma faktörünü (Z) ve entalpi değişimini en düşük hata payı ile hesaplar."
                ),
                "alternative_engine": "🔥 CoolProp",
                "alternative_eos": "HEOS",
                "alternative_label": "🏆 HEOS (Yüksek Doğruluk)",
                "alternative_reason": "Kübik olmayan çok parametreli Helmholtz enerji denklemi.",
                "fluid_type": "yuksek_basinc",
            }
        else:
            return {
                "recommended_engine": "🔥 CoolProp",
                "recommended_eos": "HEOS",
                "recommended_label": "🏆 HEOS (Yüksek Doğruluk)",
                "badge": "🏆 Süperkritik & Yüksek Basınç",
                "title": f"Yüksek Basınçlı Gaz ({P:.0f} bar) — CoolProp / HEOS Önerilir",
                "reason": (
                    f"{P:.0f} bar gibi yüksek basınç ve süperkritik akışlarda gerçek gaz yoğunluk "
                    "ve entalpi değişimlerini kübik modellere kıyasla en yüksek doğrulukla çözer."
                ),
                "alternative_engine": "🌍 neqsim",
                "alternative_eos": "GERG-2008",
                "alternative_label": "GERG-2008 (ISO Standardı)",
                "alternative_reason": "neqsim ISO 20765-1 doğal gaz referans modeli.",
                "fluid_type": "yuksek_basinc",
            }

    # 4. Yüksek CO2 İçeren Asit Gaz (CO2 >= 15%)
    if co2_pct >= 15.0:
        if current_engine == "🌍 neqsim":
            return {
                "recommended_engine": "🌍 neqsim",
                "recommended_eos": "GERG-2008",
                "recommended_label": "GERG-2008 (ISO Standardı)",
                "badge": "🌿 Asit Gaz / CO₂ Hassasiyeti",
                "title": f"Asit Gaz (%{co2_pct:.1f} CO₂) — neqsim / GERG-2008 Önerilir",
                "reason": (
                    f"Karışım %{co2_pct:.1f} oranında CO₂ içeriyor. Yüksek asit gaz konsantrasyonlarında "
                    "GERG-2008, CO₂-hidrokarbon ikili etkileşim parametrelerinde en yüksek doğruluğu sunar."
                ),
                "alternative_engine": "🔥 CoolProp",
                "alternative_eos": "HEOS",
                "alternative_label": "🏆 HEOS (Yüksek Doğruluk)",
                "alternative_reason": "CoolProp bünyesinde CO₂ karışımlarında en yüksek hassasiyete sahip model.",
                "fluid_type": "asit_gaz",
            }
        else:
            return {
                "recommended_engine": "🔥 CoolProp",
                "recommended_eos": "HEOS",
                "recommended_label": "🏆 HEOS (Yüksek Doğruluk)",
                "badge": "🌿 Asit Gaz / CO₂ Hassasiyeti",
                "title": f"Asit Gaz (%{co2_pct:.1f} CO₂) — CoolProp / HEOS Önerilir",
                "reason": (
                    f"Karışım %{co2_pct:.1f} oranında CO₂ içeriyor. Yüksek konsantrasyonlu asit gaz karışımlarında "
                    "HEOS modeli kübik modellere göre daha kararlı faz dengesi sağlar."
                ),
                "alternative_engine": "🔥 CoolProp",
                "alternative_eos": "PR",
                "alternative_label": "⚡ Peng-Robinson",
                "alternative_reason": "Hızlı mühendislik ön-boyutlandırması.",
                "fluid_type": "asit_gaz",
            }

    # 5. Yoğuşmalı Hidrokarbonlar / LPG / NGL (LPG/NGL >= 40% veya Ağır >= 10%)
    if lpg_ngl_pct >= 40.0 or heavy_pct >= 10.0:
        if current_engine == "🌍 neqsim":
            return {
                "recommended_engine": "🌍 neqsim",
                "recommended_eos": "PR-volcor",
                "recommended_label": "PR-volcor (Hacim Düz.)",
                "badge": "🛢️ Sıvı Yoğunluğu & Yoğuşma Modeli",
                "title": f"LPG / NGL Yoğuşması (%{lpg_ngl_pct:.1f} C₂+) — neqsim / PR-volcor Önerilir",
                "reason": (
                    f"Karışım C₂-C₅ ve ağır hidrokarbon ağırlıklıdır (%{lpg_ngl_pct:.1f}). Yoğuşmalı hava soğutucularda "
                    "sıvı faz yoğunluğu ve iki faz basınç kaybı kritik önemdedir. Hacim düzeltmeli Peng-Robinson "
                    "(PR-volcor), sıvı yoğunluğunu düzeltilmiş Peneloux yöntemiyle iyileştirir."
                ),
                "alternative_engine": "🔥 CoolProp",
                "alternative_eos": "PR",
                "alternative_label": "⚡ Peng-Robinson",
                "alternative_reason": "Hızlı analitik kübik yoğuşma modeli.",
                "fluid_type": "lpg_ngl",
            }
        else:
            return {
                "recommended_engine": "🔥 CoolProp",
                "recommended_eos": "PR",
                "recommended_label": "⚡ Peng-Robinson",
                "badge": "⚡ Hidrokarbon Yoğuşma Standardı",
                "title": f"LPG / NGL Karışımı (%{lpg_ngl_pct:.1f} C₂+) — CoolProp / Peng-Robinson Önerilir",
                "reason": (
                    f"Karışım C₂-C₅ hidrokarbon ağırlıklıdır (%{lpg_ngl_pct:.1f}). Peng-Robinson (PR) durum denklemi, "
                    "hidrokarbon buhar-sıvı faz dengesi (VLE) ve yoğuşma hesaplarında petrol ve gaz endüstrisinin "
                    "en yaygın ve kanıtlanmış standardıdır."
                ),
                "alternative_engine": "🔥 CoolProp",
                "alternative_eos": "HEOS",
                "alternative_label": "🏆 HEOS (Yüksek Doğruluk)",
                "alternative_reason": "Kübik olmayan yüksek hassasiyetli Helmholtz modeli.",
                "fluid_type": "lpg_ngl",
            }

    # 6. Doğal Gaz / Boru Hattı Gazı (CH4 >= 70%)
    if ch4_pct >= 70.0:
        if current_engine == "🌍 neqsim":
            return {
                "recommended_engine": "🌍 neqsim",
                "recommended_eos": "GERG-2008",
                "recommended_label": "GERG-2008 (ISO Standardı)",
                "badge": "🏆 ISO 20765-1 Standardı",
                "title": f"Boru Hattı Doğal Gazı (%{ch4_pct:.1f} CH₄) — neqsim / GERG-2008 Önerilir",
                "reason": (
                    f"Doğal gaz ağırlıklı karışımlarda (%{ch4_pct:.1f} CH₄) GERG-2008 (ISO 20765-1), gaz iletimi ve "
                    "proses soğutmasında uluslararası referans durum denklemidir. Entalpi değişiminde CoolProp HEOS ile "
                    "%0.024 uyuma sahiptir."
                ),
                "alternative_engine": "🔥 CoolProp",
                "alternative_eos": "PR",
                "alternative_label": "⚡ Peng-Robinson",
                "alternative_reason": "Milisaniye hızında analitik ön-boyutlandırma.",
                "fluid_type": "dogal_gaz",
            }
        else:
            return {
                "recommended_engine": "🔥 CoolProp",
                "recommended_eos": "HEOS",
                "recommended_label": "🏆 HEOS (Yüksek Doğruluk)",
                "badge": "🏆 Yüksek Hassasiyet (Gold Standard)",
                "title": f"Doğal Gaz Soğutma (%{ch4_pct:.1f} CH₄) — CoolProp / HEOS Önerilir",
                "reason": (
                    f"Doğal gaz karışımlarında (%{ch4_pct:.1f} CH₄) CoolProp HEOS çok parametreli Helmholtz formülasyonu "
                    "ile maksimum termodinamik hassasiyet sağlar. Hızlı ön boyutlandırma için Peng-Robinson (PR) da seçilebilir."
                ),
                "alternative_engine": "🔥 CoolProp",
                "alternative_eos": "PR",
                "alternative_label": "⚡ Peng-Robinson",
                "alternative_reason": "Milisaniye hızında analitik kübik hesaplama.",
                "fluid_type": "dogal_gaz",
            }

    # 7. Genel Gaz Karışımı
    return {
        "recommended_engine": "🔥 CoolProp",
        "recommended_eos": "PR",
        "recommended_label": "⚡ Peng-Robinson",
        "badge": "⚡ Genel Amaçlı Model",
        "title": "Gaz Karışımı — Peng-Robinson (PR) Önerilir",
        "reason": "Standart gaz ve hidrokarbon karışımlarında genel amaçlı en güvenilir ve hızlı endüstri standardı modeldir.",
        "alternative_engine": "🔥 CoolProp",
        "alternative_eos": "HEOS",
        "alternative_label": "🏆 HEOS (Yüksek Doğruluk)",
        "alternative_reason": "Kübik olmayan referans hassasiyet.",
        "fluid_type": "genel",
    }


def _ensure_jvm():
    if not _JVM_STARTED:
        _try_import_neqsim()
        if not _JVM_STARTED:
            raise RuntimeError(
                "JVM not started. Call start_jvm() first or "
                "set JAVA_HOME environment variable."
            )


class NeqSimFluid:
    """Wrapper around neqsim fluid that mimics CoolProp AbstractState interface.

    Provides hmass(), rhomass(), keyed_output(), phase(), T()
    methods compatible with the existing AirFinnedGasCooler code.
    """

    def __init__(self, backend: str, components: list[str], fractions: list[float]):
        _ensure_jvm()
        self._backend = backend
        self._components = components
        self._fractions = fractions
        self._fluid = None
        self._phase_index = 0
        self._temperature_K = 298.15
        self._pressure_Pa = 101325.0

    def _create_fluid(self):
        from neqsim.thermo import fluid
        from neqsim.thermo.thermoTools import TPflash

        nq_eos = NEQSIM_EOS_DISPLAY_TO_MODEL.get(self._backend, "GERG-2008")
        f = fluid(nq_eos)
        total = sum(self._fractions)
        for cname, frac in zip(self._components, self._fractions):
            nq_name = _resolve_name(cname)
            if frac > 0 and total > 0:
                f.addComponent(nq_name, frac / total)
        return f

    # CoolProp phase constants for compatibility
    _CP_PHASE_MAP = {
        "gas": 5,        # CP.iphase_gas
        "liquid": 0,     # CP.iphase_liquid
        "twophase": 6,   # CP.iphase_twophase
        "supercritical": 1,  # CP.iphase_supercritical
    }

    # CoolProp input type constants
    _PT_INPUTS = 9
    _PQ_INPUTS = 2

    def update(self, input_type, P_Pa, T_or_Q):
        _ensure_jvm()
        if input_type != self._PT_INPUTS:
            raise NotImplementedError(f"NeqSimFluid only supports PT_INPUTS (got {input_type})")
        from neqsim.thermo.thermoTools import TPflash

        T_K = T_or_Q
        self._fluid = self._create_fluid()
        self._fluid.setTemperature(T_K, "K")
        self._fluid.setPressure(P_Pa / 1e5, "bara")
        TPflash(self._fluid)

        self._temperature_K = T_K
        self._pressure_Pa = P_Pa
        n_phases = self._fluid.getNumberOfPhases()
        if n_phases > 1:
            self._phase_index = self._CP_PHASE_MAP["twophase"]
        elif self._fluid.hasPhaseType("gas"):
            self._phase_index = self._CP_PHASE_MAP["gas"]
        elif self._fluid.hasPhaseType("liquid"):
            self._phase_index = self._CP_PHASE_MAP["liquid"]
        else:
            self._phase_index = self._CP_PHASE_MAP["gas"]

    def hmass(self):
        return self._fluid.getEnthalpy("kJ/kg") * 1000.0

    def rhomass(self):
        return self._fluid.getDensity("kg/m3")

    def keyed_output(self, key):
        if key == 72:  # CP.iZ
            return self._fluid.getZ()
        if key == 39:  # CP.iDmass
            return self._fluid.getDensity("kg/m3")
        if key in (42, 29):  # CP.iCpmass, CP.iCpmolar
            return self._fluid.getCp("kJ/kgK") * 1000.0
        if key == 40:  # CP.iHmass
            return self._fluid.getEnthalpy("kJ/kg") * 1000.0
        raise NotImplementedError(f"keyed_output({key}) not implemented for NeqSimFluid")

    def phase(self):
        return self._phase_index

    def T(self):
        if self._fluid is not None:
            return self._fluid.getTemperature("K")
        return self._temperature_K

    def get_phase_name(self):
        return NEQSIM_PHASE_NAMES.get(self._phase_index, "Bilinmiyor")

    def cp0mass(self):
        return self.keyed_output(42)  # CP.iCpmass

    def cpmass(self):
        return self.keyed_output(42)  # CP.iCpmass

    def hmolar(self):
        return self._fluid.getEnthalpy("kJ/kg") * 1000.0


def _create_neqsim_fluid_wrapper(backend: str, components: list, fractions: list):
    return NeqSimFluid(backend, components, fractions)
