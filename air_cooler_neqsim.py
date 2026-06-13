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
_neqsim = None
_jpype = None
_NEQSIM_JAR_PATH = None


def _try_import_neqsim():
    global _HAS_NEQSIM, _neqsim, _jpype, _NEQSIM_JAR_PATH
    if _HAS_NEQSIM:
        return True
    # Ensure JAVA_HOME is set so neqsim's auto JVM start works
    _java_home = os.environ.get("JAVA_HOME") or ""
    if not _java_home or not os.path.exists(os.path.join(_java_home, "bin", "java")):
        # Try known locations
        for candidate in [
            "/tmp/java21_arm/jdk-21.0.11+10/Contents/Home",
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

    def hmolar(self):
        return self._fluid.getEnthalpy("kJ/kg") * 1000.0


def _create_neqsim_fluid_wrapper(backend: str, components: list, fractions: list):
    return NeqSimFluid(backend, components, fractions)
