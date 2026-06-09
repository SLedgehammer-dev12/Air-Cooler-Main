import numpy as np
import CoolProp.CoolProp as CP
from CoolProp.CoolProp import AbstractState
from pint import UnitRegistry
import ht
import fluids
from fluids.geometry import AirCooledExchanger
import hashlib
import os
import json
from pathlib import Path

APP_DISPLAY_NAME = "Air Cooler Main"
APP_VERSION = "3.7.1"
DEFAULT_ATM_PRESSURE_PA = 101325.0
SATURATION_TOLERANCE_K = 0.25

ureg = UnitRegistry()
ureg.define("Sm3 = meter**3")
ureg.define("Am3 = meter**3")
ureg.define("scf = foot**3")
ureg.define("MMscf = 1e6 * scf")
ureg.define("MMscfd = MMscf / day")
ureg.define("MMscmd = 1e6 * meter**3 / day")
Q_ = ureg.Quantity

TEMP_UNIT_MAP = {"°C": "degC", "K": "K", "°F": "degF"}

def generate_salt():
    return os.urandom(16).hex()

def hash_password(password, salt):
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

def initialize_users_db(db_path):
    path = Path(db_path)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    admin_salt = generate_salt()
    user_salt = generate_salt()
    
    users = {
        "admin": {
            "salt": admin_salt,
            "hash": hash_password("admin123", admin_salt),
            "role": "admin"
        },
        "user": {
            "salt": user_salt,
            "hash": hash_password("user123", user_salt),
            "role": "user"
        }
    }
    
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
        
    return users

def authenticate_user(username, password, users_db):
    user_info = users_db.get(username.strip())
    if not user_info:
        return False, None
    
    salt = user_info["salt"]
    stored_hash = user_info["hash"]
    computed_hash = hash_password(password, salt)
    
    if computed_hash == stored_hash:
        return True, user_info["role"]
    return False, None


COOLPROP_COMPONENTS = {
    "METHANE": "Metan (C1)",
    "ETHANE": "Etan (C2)",
    "PROPANE": "Propan (C3)",
    "N-BUTANE": "n-Bütan (nC4)",
    "ISOBUTANE": "i-Bütan (iC4)",
    "N-PENTANE": "n-Pentan (nC5)",
    "ISOPENTANE": "i-Pentan (iC5)",
    "CYCLOPENTANE": "Siklopentan",
    "HEXANE": "Hekzan (C6)",
    "HEPTANE": "Heptan (C7)",
    "OCTANE": "Oktan (C8)",
    "NITROGEN": "Azot (N2)",
    "CARBONDIOXIDE": "Karbondioksit (CO2)",
    "WATER": "Su (H2O)",
    "HYDROGEN": "Hidrojen (H2)",
    "OXYGEN": "Oksijen (O2)",
    "ARGON": "Argon (Ar)",
}

COOLPROP_ALIASES = {
    "I-BUTANE": "ISOBUTANE",
    "I-PENTANE": "ISOPENTANE",
}

def resolve_fluid_name(name):
    return COOLPROP_ALIASES.get(name, name)

EOS_OPTIONS = {
    "🏆 Yüksek Doğruluk (HEOS) - Tüm Akışkanlar": "HEOS",
    "⚡ Hızlı Hesaplama (Peng-Robinson)": "PR",
    "⚡ Hızlı Hesaplama (Soave-Redlich-Kwong)": "SRK",
    "🔬 Doğalgaz (HEOS/GERG Korelasyonları)": "HEOS",
}

UNITS = {
    "Basınç": ["bar(a)", "bar(g)", "psi(a)", "psi(g)", "kPa", "MPa", "atm"],
    "Sıcaklık": ["°C", "K", "°F"],
    "Akış Miktarı": ["Sm3/h", "kg/s", "kg/h", "MMscmd", "MMscfd", "Am3/h"],
}


class AirCoolerError(Exception):
    pass


class AmbiguousTwoPhaseInputError(AirCoolerError):
    pass


class HeatExchangerSizingError(AirCoolerError):
    pass


def get_pressure_type(unit_str):
    if "(g)" in unit_str.lower():
        return "gauge"
    return "absolute"


def clean_pressure_unit(raw_unit):
    return raw_unit.replace("(a)", "").replace("(g)", "").strip()


def clean_temp_unit(raw_unit):
    return TEMP_UNIT_MAP.get(raw_unit.strip(), raw_unit.strip())


class AirFinnedGasCooler:
    def __init__(
        self,
        akiskan_kompozisyon,
        eos_secimi,
        raw_p_unit,
        atmospheric_pressure_pa=DEFAULT_ATM_PRESSURE_PA,
        logger=None,
    ):
        self.eos_secimi = eos_secimi
        self.raw_p_unit = raw_p_unit
        self.atmospheric_pressure_pa = atmospheric_pressure_pa
        self.logger = logger or (lambda level, message, exception=None: None)
        self.ara_sonuclar = {}
        self.kompozisyon_raw = akiskan_kompozisyon.copy()
        raw_total = sum(v["yuzde"] for v in self.kompozisyon_raw.values()) if self.kompozisyon_raw else 0.0
        self.mol_kompozisyon_coolprop = self._kutlesel_mol_cevir(self.kompozisyon_raw)
        if raw_total and abs(raw_total - 100.0) > 0.01:
            self.ara_sonuclar["normalize_edildi"] = True
            self.ara_sonuclar["orijinal_toplam"] = raw_total
        self.bilesen_keys = list(self.mol_kompozisyon_coolprop.keys())
        self.karisim_str_names_only = self._coolprop_karisim_str_olustur(with_concentrations=False)
        self._log("INFO", f"Cooler sınıfı başlatıldı. EOS: {eos_secimi}")

    def _log(self, level, message, exception=None):
        self.logger(level, message, exception)

    def _init_abstract_state(self, backend=None):
        selected_backend = backend or self.eos_secimi
        resolved_keys = [resolve_fluid_name(k) for k in self.bilesen_keys]
        num_components = len(resolved_keys)
        fractions = [self.mol_kompozisyon_coolprop[k] for k in self.bilesen_keys]
        try:
            if selected_backend == "HEOS" and num_components == 1:
                return AbstractState("HEOS", resolved_keys[0])

            state = AbstractState(selected_backend, "&".join(resolved_keys))
            state.set_mole_fractions(fractions)
            return state
        except Exception as exc:
            if selected_backend != "HEOS":
                self._log("WARNING", f"{selected_backend} başlatılamadı, HEOS'a düşüldü.", exc)
                return self._init_abstract_state("HEOS")
            raise

    def _kutlesel_mol_cevir(self, kompozisyon):
        if not kompozisyon:
            return {}

        girdi_tipi = list(kompozisyon.values())[0]["tip"]
        if girdi_tipi == "Molar":
            toplam = sum(v["yuzde"] for v in kompozisyon.values())
            return {k: v["yuzde"] / toplam for k, v in kompozisyon.items()}

        self._log("INFO", "Kütlesel yüzde -> mol kesri dönüşümü")
        mol_komp = {}
        toplam_mol = 0.0
        for bilesen, val in kompozisyon.items():
            resolved = resolve_fluid_name(bilesen)
            mol_i = (val["yuzde"] / 100.0) / CP.PropsSI("M", resolved)
            mol_komp[bilesen] = mol_i
            toplam_mol += mol_i

        return {b: n / toplam_mol for b, n in mol_komp.items()}

    def _coolprop_karisim_str_olustur(self, with_concentrations=True):
        if len(self.bilesen_keys) == 1:
            return self.bilesen_keys[0]

        if with_concentrations:
            return "&".join([f"{b}[{self.mol_kompozisyon_coolprop[b]:.8f}]" for b in self.bilesen_keys])
        return "&".join(self.bilesen_keys)

    def _birim_cevir_P_T(self, P_girdi, T_girdi):
        P_SI = P_girdi.to("pascal").m
        if get_pressure_type(self.raw_p_unit) == "gauge":
            P_SI += self.atmospheric_pressure_pa
        T_SI = T_girdi.to("kelvin").m
        return P_SI, T_SI

    def _birim_cevir_m_dot(self, m_dot_val, m_dot_unit, P_giris_SI, T_giris_SI):
        unit = m_dot_unit.lower()
        if "kg/s" in unit:
            return Q_(m_dot_val, "kg/s").to("kg/s").m
        if "kg/h" in unit:
            return Q_(m_dot_val, "kg/h").to("kg/s").m
        if "sm3/h" in unit or "mmscmd" in unit or "mmscfd" in unit:
            if "sm3/h" in unit or "mmscmd" in unit:
                P_ref = 101325.0
                T_ref = Q_(15, "degC").to("kelvin").m
            else:
                P_ref = Q_(14.73, "psi").to("pascal").m
                T_ref = Q_(60, "degF").to("kelvin").m

            state = self._init_abstract_state()
            state.update(CP.PT_INPUTS, P_ref, T_ref)
            d_std = state.rhomass()

            if "sm3/h" in unit:
                vol_s = Q_(m_dot_val, "m**3/h").to("m**3/s").m
            elif "mmscfd" in unit:
                vol_s = Q_(m_dot_val, "MMscfd").to("m**3/s").m
            else:
                vol_s = Q_(m_dot_val, "MMscmd").to("m**3/s").m
            return vol_s * d_std

        if "am3/h" in unit:
            state = self._init_abstract_state()
            state.update(CP.PT_INPUTS, P_giris_SI, T_giris_SI)
            d_act = state.rhomass()
            return Q_(m_dot_val, "m**3/h").to("m**3/s").m * d_act

        raise ValueError(f"Birim {m_dot_unit} desteklenmiyor.")

    def _gercek_faz_belirle(self, state):
        cp_phase_idx = state.phase()
        rho = state.rhomass()
        if cp_phase_idx == CP.iphase_twophase:
            return "İki Faz"

        try:
            z_factor = state.keyed_output(CP.iZ)
        except Exception:
            z_factor = None

        if z_factor is not None and z_factor > 0.6 and rho < 300:
            if cp_phase_idx in [CP.iphase_supercritical, CP.iphase_supercritical_gas]:
                return "Süperkritik Gaz"
            return "Gaz"

        faz_isim = {
            CP.iphase_liquid: "Sıvı",
            CP.iphase_supercritical: "Süperkritik",
            CP.iphase_supercritical_gas: "Süperkritik Gaz",
            CP.iphase_supercritical_liquid: "Süperkritik Sıvı",
            CP.iphase_critical_point: "Kritik Nokta",
            CP.iphase_gas: "Gaz",
            CP.iphase_twophase: "İki Faz",
            CP.iphase_unknown: "Bilinmiyor",
            CP.iphase_not_imposed: "Atanmamış",
        }.get(cp_phase_idx, "Bilinmiyor")

        if cp_phase_idx == CP.iphase_liquid and rho < 300:
            return "Gaz (Yoğun)"
        return faz_isim

    def _get_saturation_properties(self, P_Pa):
        for backend in dict.fromkeys([self.eos_secimi, "HEOS"]):
            try:
                state = self._init_abstract_state(backend)
                state.update(CP.PQ_INPUTS, P_Pa, 0.0)
                t_bubble = state.T()
                h_bubble = state.hmass()
                state.update(CP.PQ_INPUTS, P_Pa, 1.0)
                t_dew = state.T()
                h_dew = state.hmass()
                return {
                    "backend": backend,
                    "T_dew": t_dew,
                    "T_bubble": t_bubble,
                    "H_dew": h_dew,
                    "H_bubble": h_bubble,
                }
            except Exception:
                continue
        return None

    def _update_state_at_pt(self, state, P_Pa, T_K):
        sat = self._get_saturation_properties(P_Pa)
        if sat and sat["T_bubble"] + SATURATION_TOLERANCE_K < T_K < sat["T_dew"] - SATURATION_TOLERANCE_K:
            raise AmbiguousTwoPhaseInputError(
                "Verilen P-T noktası iki faz bölgesine düşüyor. "
                "Bu bölge yalnızca basınç ve sıcaklık ile tekil olarak tanımlanamaz; "
                "ek olarak kalite veya faz oranı gerekir."
            )

        for dT in (0.0, 0.05, -0.05, 0.25, -0.25, 0.5, -0.5):
            try:
                state.update(CP.PT_INPUTS, P_Pa, T_K + dT)
                return
            except Exception:
                continue

        raise ValueError(f"P-T noktası çözülemedi. P={P_Pa:.3f} Pa, T={T_K:.3f} K")

    def _build_state_from_pt(self, P_Pa, T_K):
        state = self._init_abstract_state()
        self._update_state_at_pt(state, P_Pa, T_K)
        return state

    def _h_at_pt(self, P_Pa, T_K):
        return self._build_state_from_pt(P_Pa, T_K).hmass()

    def _ideal_gas_reference(self, m_dot_SI, T_in_SI, T_out_SI):
        T_avg = (T_in_SI + T_out_SI) / 2.0
        for backend in dict.fromkeys(["HEOS", self.eos_secimi]):
            try:
                state = self._init_abstract_state(backend)
                state.update(CP.PT_INPUTS, 101325.0, T_avg)
                cp0 = state.cp0mass()
                return m_dot_SI * cp0 * (T_in_SI - T_out_SI), cp0 / 1000.0
            except Exception:
                continue
        return None, None

    def _calculate_lmtd(self, delta_t_1, delta_t_2):
        if delta_t_1 <= 0 or delta_t_2 <= 0:
            raise HeatExchangerSizingError(
                "LMTD hesabı için her iki terminal sıcaklık farkı da pozitif olmalıdır."
            )

        if np.isclose(delta_t_1, delta_t_2, atol=1e-9):
            return float(delta_t_1)

        return float((delta_t_1 - delta_t_2) / np.log(delta_t_1 / delta_t_2))

    def hesapla_esanjor_boyutlandirma(
        self,
        q_watt,
        process_t_in_k,
        process_t_out_k,
        air_t_in_k,
        air_t_out_k,
        overall_u_w_m2k,
        correction_factor,
    ):
        if overall_u_w_m2k <= 0:
            raise HeatExchangerSizingError("Genel ısı transfer katsayısı (U) 0'dan büyük olmalıdır.")

        if correction_factor <= 0 or correction_factor > 1:
            raise HeatExchangerSizingError("Düzeltme faktörü F, 0 ile 1 arasında olmalıdır.")

        if air_t_out_k <= air_t_in_k:
            raise HeatExchangerSizingError("Hava çıkış sıcaklığı hava giriş sıcaklığından büyük olmalıdır.")

        delta_t_hot_end = process_t_in_k - air_t_out_k
        delta_t_cold_end = process_t_out_k - air_t_in_k
        lmtd_k = self._calculate_lmtd(delta_t_hot_end, delta_t_cold_end)
        effective_lmtd_k = correction_factor * lmtd_k

        if effective_lmtd_k <= 0:
            raise HeatExchangerSizingError("Efektif LMTD pozitif olmalıdır.")

        q_abs_watt = abs(q_watt)
        ua_required_w_k = q_abs_watt / effective_lmtd_k
        required_area_m2 = ua_required_w_k / overall_u_w_m2k

        return {
            "air_in_C": air_t_in_k - 273.15,
            "air_out_C": air_t_out_k - 273.15,
            "delta_t_hot_end_K": delta_t_hot_end,
            "delta_t_cold_end_K": delta_t_cold_end,
            "min_terminal_delta_t_K": min(delta_t_hot_end, delta_t_cold_end),
            "lmtd_K": lmtd_k,
            "correction_factor": correction_factor,
            "effective_lmtd_K": effective_lmtd_k,
            "overall_u_W_m2K": overall_u_w_m2k,
            "ua_required_W_K": ua_required_w_k,
            "required_area_m2": required_area_m2,
        }

    def hesapla_sogutma_bolgeleri(self, m_dot_SI, P_in_SI, P_out_SI, T_in_SI, T_out_SI, H_in, H_out):
        P_avg = (P_in_SI + P_out_SI) / 2.0
        Q_total_W = m_dot_SI * (H_in - H_out)
        sat = self._get_saturation_properties(P_avg)

        bolgeler = []
        cooling_curve = []

        def add_curve_segment(T_start, T_end, P_Pa, n=20):
            for temp_k in np.linspace(T_start, T_end, n):
                try:
                    hmass = self._h_at_pt(P_Pa, temp_k)
                except Exception:
                    continue
                cooling_curve.append((temp_k - 273.15, hmass / 1000.0))

        def make_bolge(ad, T_start, T_end, h_start, h_end, renk):
            q_w = m_dot_SI * (h_start - h_end)
            q_frac = q_w / Q_total_W if abs(Q_total_W) > 1e-12 else 0.0
            return {
                "bolge_adi": ad,
                "T_in_C": T_start - 273.15,
                "T_out_C": T_end - 273.15,
                "H_in_kJ_kg": h_start / 1000.0,
                "H_out_kJ_kg": h_end / 1000.0,
                "Q_kW": q_w / 1000.0,
                "Q_frac": q_frac,
                "renk": renk,
            }

        if not sat:
            add_curve_segment(T_in_SI, T_out_SI, P_avg)
            return [make_bolge("🌡️ Tek Bölge Soğutma", T_in_SI, T_out_SI, H_in, H_out, "#3498db")], cooling_curve

        T_dew = sat["T_dew"]
        T_bubble = sat["T_bubble"]
        H_dew = sat["H_dew"]
        H_bubble = sat["H_bubble"]

        if T_bubble + SATURATION_TOLERANCE_K < T_in_SI < T_dew - SATURATION_TOLERANCE_K:
            raise AmbiguousTwoPhaseInputError("Giriş noktası iki faz bölgesinde. Kalite bilgisi olmadan hesap yapılamaz.")
        if T_bubble + SATURATION_TOLERANCE_K < T_out_SI < T_dew - SATURATION_TOLERANCE_K:
            raise AmbiguousTwoPhaseInputError("Çıkış noktası iki faz bölgesinde. Kalite bilgisi olmadan hesap yapılamaz.")

        if T_in_SI >= T_dew - SATURATION_TOLERANCE_K and T_out_SI >= T_dew - SATURATION_TOLERANCE_K:
            add_curve_segment(T_in_SI, T_out_SI, P_avg)
            return [make_bolge("🌬️ Gaz Soğutma", T_in_SI, T_out_SI, H_in, H_out, "#3498db")], cooling_curve

        if T_in_SI <= T_bubble + SATURATION_TOLERANCE_K and T_out_SI <= T_bubble + SATURATION_TOLERANCE_K:
            add_curve_segment(T_in_SI, T_out_SI, P_avg)
            return [make_bolge("🧊 Sıvı Soğutma", T_in_SI, T_out_SI, H_in, H_out, "#27ae60")], cooling_curve

        if T_in_SI > T_dew - SATURATION_TOLERANCE_K and T_out_SI < T_bubble + SATURATION_TOLERANCE_K:
            if T_in_SI > T_dew + SATURATION_TOLERANCE_K:
                add_curve_segment(T_in_SI, T_dew, P_avg)
                bolgeler.append(
                    make_bolge("🌬️ Gaz Soğutma (Desuperheating)", T_in_SI, T_dew, H_in, H_dew, "#3498db")
                )

            sat_state = self._init_abstract_state(sat["backend"])
            for quality in np.linspace(1.0, 0.0, 20):
                try:
                    sat_state.update(CP.PQ_INPUTS, P_avg, quality)
                except Exception:
                    continue
                cooling_curve.append((sat_state.T() - 273.15, sat_state.hmass() / 1000.0))

            bolgeler.append(
                make_bolge("💧 Yoğuşma (Condensing)", T_dew, T_bubble, H_dew, H_bubble, "#e74c3c")
            )

            if T_out_SI < T_bubble - SATURATION_TOLERANCE_K:
                add_curve_segment(T_bubble, T_out_SI, P_avg)
                bolgeler.append(
                    make_bolge("🧊 Sıvı Soğutma (Subcooling)", T_bubble, T_out_SI, H_bubble, H_out, "#27ae60")
                )

            return bolgeler, cooling_curve

        add_curve_segment(T_in_SI, T_out_SI, P_avg)
        self._log("WARNING", "Bölgesel analiz tek bölgeye indirildi; sıcaklık yolu beklenen faz geçiş şablonuna uymuyor.")
        return [make_bolge("🌡️ Tek Bölge Soğutma", T_in_SI, T_out_SI, H_in, H_out, "#3498db")], cooling_curve

    def hesapla_isi_yuku(
        self,
        m_dot_val,
        m_dot_unit,
        P_in_Q,
        P_out_Q,
        T_in_Q,
        T_out_Q,
        air_sizing_inputs=None,
    ):
        self._log("INFO", "--- HESAPLAMA BAŞLATILDI ---")
        P_in_SI, T_in_SI = self._birim_cevir_P_T(P_in_Q, T_in_Q)
        P_out_SI, _ = self._birim_cevir_P_T(P_out_Q, T_in_Q)
        T_out_SI = T_out_Q.to("kelvin").m

        m_dot_SI = self._birim_cevir_m_dot(m_dot_val, m_dot_unit, P_in_SI, T_in_SI)

        inlet_state = self._build_state_from_pt(P_in_SI, T_in_SI)
        outlet_state = self._build_state_from_pt(P_out_SI, T_out_SI)

        H_in = inlet_state.hmass()
        H_out = outlet_state.hmass()
        rho_in = inlet_state.rhomass()
        rho_out = outlet_state.rhomass()
        faz_in = self._gercek_faz_belirle(inlet_state)
        faz_out = self._gercek_faz_belirle(outlet_state)

        Q_watt = m_dot_SI * (H_in - H_out)

        self.ara_sonuclar = {
            "m_dot_kg_s": m_dot_SI,
            "P_in_Pa": P_in_SI,
            "P_out_Pa": P_out_SI,
            "T_in_K": T_in_SI,
            "T_out_K": T_out_SI,
            "H_in_kJ_kg": H_in / 1000.0,
            "H_out_kJ_kg": H_out / 1000.0,
            "rho_in": rho_in,
            "rho_out": rho_out,
            "faz_in": faz_in,
            "faz_out": faz_out,
            "delta_P_bar": (P_in_SI - P_out_SI) / 1e5,
        }

        Q_ideal_watt, cp0_kj_kgk = self._ideal_gas_reference(m_dot_SI, T_in_SI, T_out_SI)
        if cp0_kj_kgk is not None:
            self.ara_sonuclar["Cp_ideal"] = cp0_kj_kgk

        bolgeler, cooling_curve = self.hesapla_sogutma_bolgeleri(
            m_dot_SI, P_in_SI, P_out_SI, T_in_SI, T_out_SI, H_in, H_out
        )
        self.ara_sonuclar["bolgeler"] = bolgeler
        self.ara_sonuclar["cooling_curve"] = cooling_curve
        self.ara_sonuclar["faz_degisimi_var"] = any("Yoğuşma" in b["bolge_adi"] for b in bolgeler)

        if air_sizing_inputs:
            air_t_in_k = air_sizing_inputs["air_in_q"].to("kelvin").m
            air_t_out_k = air_sizing_inputs["air_out_q"].to("kelvin").m
            self.ara_sonuclar["tasarim"] = self.hesapla_esanjor_boyutlandirma(
                q_watt=Q_watt,
                process_t_in_k=T_in_SI,
                process_t_out_k=T_out_SI,
                air_t_in_k=air_t_in_k,
                air_t_out_k=air_t_out_k,
                overall_u_w_m2k=air_sizing_inputs["overall_u_w_m2k"],
                correction_factor=air_sizing_inputs["correction_factor"],
            )

        faz_uyari = None
        if self.ara_sonuclar["faz_degisimi_var"]:
            faz_uyari = f"Yoğuşma tespit edildi! ({faz_in} -> {faz_out})"

        q_ideal_quantity = Q_(Q_ideal_watt, "watt") if Q_ideal_watt is not None else None
        return Q_(Q_watt, "watt"), q_ideal_quantity, faz_uyari

    def get_mixture_transport_properties(self, P_Pa, T_K):
        mw_mix = 0.0
        visc_sum = 0.0
        cond_sum = 0.0
        for b, y_frac in self.mol_kompozisyon_coolprop.items():
            resolved_b = resolve_fluid_name(b)
            try:
                M = CP.PropsSI("M", resolved_b)
                mw_mix += y_frac * M
                v = CP.PropsSI("V", "P", P_Pa, "T", T_K, resolved_b)
                c = CP.PropsSI("L", "P", P_Pa, "T", T_K, resolved_b)
                visc_sum += y_frac * v
                cond_sum += y_frac * c
            except Exception:
                mw = CP.PropsSI("M", resolved_b)
                mw_mix += y_frac * mw
                visc_sum += y_frac * 1.5e-5
                cond_sum += y_frac * 0.025
        
        state = self._init_abstract_state()
        state.update(CP.PT_INPUTS, P_Pa, T_K)
        rho = state.rhomass()
        cp = state.cpmass()
        
        return {
            "viscosity": visc_sum if visc_sum > 0 else 1.5e-5,
            "conductivity": cond_sum if cond_sum > 0 else 0.025,
            "density": rho,
            "cp": cp,
            "mw": mw_mix
        }

    def hesapla_detayli_dizayn(
        self,
        m_dot_val,
        m_dot_unit,
        P_in_Q,
        P_out_Q,
        T_in_Q,
        T_out_Q,
        air_in_Q,
        air_out_Q,
        geom_params
    ):
        P_in_SI, T_in_SI = self._birim_cevir_P_T(P_in_Q, T_in_Q)
        P_out_SI, _ = self._birim_cevir_P_T(P_out_Q, T_in_Q)
        T_out_SI = T_out_Q.to("kelvin").m
        m_dot_SI = self._birim_cevir_m_dot(m_dot_val, m_dot_unit, P_in_SI, T_in_SI)
        
        air_in_SI = air_in_Q.to("kelvin").m
        air_out_SI = air_out_Q.to("kelvin").m
        
        T_avg_SI = (T_in_SI + T_out_SI) / 2.0
        P_avg_SI = (P_in_SI + P_out_SI) / 2.0
        
        props_in = self.get_mixture_transport_properties(P_in_SI, T_in_SI)
        props_out = self.get_mixture_transport_properties(P_out_SI, T_out_SI)
        props_avg = self.get_mixture_transport_properties(P_avg_SI, T_avg_SI)
        
        H_in = self._h_at_pt(P_in_SI, T_in_SI)
        H_out = self._h_at_pt(P_out_SI, T_out_SI)
        Q_total_W = m_dot_SI * (H_in - H_out)
        
        T_air_avg = (air_in_SI + air_out_SI) / 2.0
        rho_air = 101325.0 / (287.05 * T_air_avg)
        Cp_air = 1007.0
        mu_air = 1.85e-5
        k_air = 0.0263
        
        m_dot_air = Q_total_W / (Cp_air * (air_out_SI - air_in_SI)) if (air_out_SI > air_in_SI) else 0.0
        
        AC = AirCooledExchanger(
            tube_rows=geom_params['tube_rows'],
            tube_passes=geom_params['tube_passes'],
            tubes_per_row=geom_params['tubes_per_row'],
            tube_length=geom_params['tube_length'],
            tube_diameter=geom_params['tube_od'],
            fin_thickness=geom_params['fin_thickness'],
            fin_density=geom_params['fin_density'],
            pitch=geom_params['pitch'],
            angle=geom_params['angle'],
            fin_height=geom_params['fin_height'],
            tube_thickness=geom_params['tube_thickness']
        )
        
        N_tubes_total = geom_params['tube_rows'] * geom_params['tubes_per_row']
        
        D_i = geom_params['tube_od'] - 2 * geom_params['tube_thickness']
        A_flow_per_pass = (np.pi * D_i**2 / 4.0) * (N_tubes_total / geom_params['tube_passes'])
        
        G_process = m_dot_SI / A_flow_per_pass
        v_process = G_process / props_avg['density']
        
        Re_process = G_process * D_i / props_avg['viscosity']
        Pr_process = props_avg['cp'] * props_avg['viscosity'] / props_avg['conductivity']
        
        if Re_process < 2100:
            Nu_process = 4.36
        elif Re_process > 4000:
            Nu_process = 0.023 * (Re_process**0.8) * (Pr_process**0.3)
        else:
            Nu_lam = 4.36
            Nu_turb = 0.023 * (4000.0**0.8) * (Pr_process**0.3)
            frac = (Re_process - 2100.0) / (4000.0 - 2100.0)
            Nu_process = Nu_lam + frac * (Nu_turb - Nu_lam)
            
        h_inside = Nu_process * props_avg['conductivity'] / D_i
        
        h_o_bare_basis = ht.air_cooler.h_Briggs_Young(
            m=m_dot_air,
            A=AC.A,
            A_min=AC.A_min,
            A_increase=AC.A_increase,
            A_fin=AC.A_fin,
            A_tube_showing=AC.A_tube_showing,
            tube_diameter=AC.tube_diameter,
            fin_diameter=AC.fin_diameter,
            bare_length=AC.bare_length,
            fin_thickness=AC.fin_thickness,
            rho=rho_air,
            Cp=Cp_air,
            mu=mu_air,
            k=k_air,
            k_fin=geom_params['fin_k']
        )
        
        h_o_actual = h_o_bare_basis / AC.A_increase
        
        eta_fin = ht.air_cooler.fin_efficiency_Kern_Kraus(
            Do=geom_params['tube_od'],
            D_fin=AC.fin_diameter,
            t_fin=geom_params['fin_thickness'],
            k_fin=geom_params['fin_k'],
            h=h_o_actual
        )
        
        eta_o = 1.0 - (AC.A_fin / AC.A) * (1.0 - eta_fin)
        
        R_wall = (geom_params['tube_od'] * np.log(geom_params['tube_od'] / D_i) / (2.0 * geom_params['tube_k'])) * AC.A_increase
        R_in = (geom_params['tube_od'] * AC.A_increase / (D_i * h_inside))
        R_in_fouling = geom_params['fouling_in'] * (geom_params['tube_od'] * AC.A_increase / D_i)
        R_out_fouling = geom_params['fouling_out']
        R_out = 1.0 / (eta_o * h_o_actual)
        
        U_outside = 1.0 / (R_in + R_in_fouling + R_wall + R_out_fouling + R_out)
        
        try:
            Ft = ht.air_cooler.Ft_aircooler(
                Thi=T_in_SI,
                Tho=T_out_SI,
                Tci=air_in_SI,
                Tco=air_out_SI,
                Ntp=geom_params['tube_passes'],
                rows=geom_params['tube_rows']
            )
            if np.isnan(Ft) or Ft <= 0:
                Ft = 0.90
        except Exception:
            Ft = 0.90
            
        dT_hot = T_in_SI - air_out_SI
        dT_cold = T_out_SI - air_in_SI
        lmtd = self._calculate_lmtd(dT_hot, dT_cold)
        effective_lmtd = Ft * lmtd
        
        UA_required = Q_total_W / effective_lmtd
        Area_required = UA_required / U_outside
        overdesign = (AC.A - Area_required) / Area_required * 100.0 if Area_required > 0 else 0.0
        
        dP_air = ht.air_cooler.dP_ESDU_high_fin(
            m=m_dot_air,
            A_min=AC.A_min,
            A_increase=AC.A_increase,
            flow_area_contraction_ratio=AC.flow_area_contraction_ratio,
            tube_diameter=AC.tube_diameter,
            pitch_parallel=AC.pitch_parallel,
            pitch_normal=AC.pitch_normal,
            tube_rows=AC.tube_rows,
            rho=rho_air,
            mu=mu_air
        )
        
        V_air_m3_s = m_dot_air / rho_air
        fan_power_W = (V_air_m3_s * dP_air) / geom_params['fan_efficiency']
        
        roughness = 4.5e-5
        relative_roughness = roughness / D_i
        f_friction = fluids.friction_factor(Re_process, eD=relative_roughness)
        
        L_total = geom_params['tube_length'] * geom_params['tube_passes']
        dP_process_friction = f_friction * (L_total / D_i) * (props_avg['density'] * v_process**2 / 2.0)
        K_minor = 1.5 * (geom_params['tube_passes'] - 1)
        dP_process_minor = K_minor * (props_avg['density'] * v_process**2 / 2.0)
        dP_process_total_Pa = dP_process_friction + dP_process_minor
        
        return {
            "Q_kW": Q_total_W / 1000.0,
            "U_W_m2K": U_outside,
            "actual_area_m2": AC.A,
            "required_area_m2": Area_required,
            "overdesign_pct": overdesign,
            "lmtd_K": lmtd,
            "Ft": Ft,
            "effective_lmtd_K": effective_lmtd,
            "m_dot_air_kg_s": m_dot_air,
            "V_air_m3_h": V_air_m3_s * 3600.0,
            "dP_air_Pa": dP_air,
            "fan_power_kW": fan_power_W / 1000.0,
            "h_inside_W_m2K": h_inside,
            "h_outside_actual_W_m2K": h_o_actual,
            "fin_efficiency": eta_fin,
            "surface_efficiency": eta_o,
            "gas_velocity_m_s": v_process,
            "gas_Re": Re_process,
            "gas_dP_bar": dP_process_total_Pa / 1e5,
            "gas_in_phase": self._gercek_faz_belirle(self._build_state_from_pt(P_in_SI, T_in_SI)),
            "gas_out_phase": self._gercek_faz_belirle(self._build_state_from_pt(P_out_SI, T_out_SI))
        }

    def hesapla_degerlendirme_rating(
        self,
        m_dot_val,
        m_dot_unit,
        P_in_Q,
        P_out_Q,
        T_in_Q,
        air_in_Q,
        V_air_m3_h,
        geom_params
    ):
        P_in_SI, T_in_SI = self._birim_cevir_P_T(P_in_Q, T_in_Q)
        P_out_SI, _ = self._birim_cevir_P_T(P_out_Q, T_in_Q)
        m_dot_SI = self._birim_cevir_m_dot(m_dot_val, m_dot_unit, P_in_SI, T_in_SI)
        air_in_SI = air_in_Q.to("kelvin").m
        
        rho_air = 101325.0 / (287.05 * air_in_SI)
        Cp_air = 1007.0
        mu_air = 1.85e-5
        k_air = 0.0263
        
        m_dot_air = (V_air_m3_h / 3600.0) * rho_air
        
        props_in = self.get_mixture_transport_properties(P_in_SI, T_in_SI)
        
        C_gas = m_dot_SI * props_in['cp']
        C_air = m_dot_air * Cp_air
        
        C_min = min(C_gas, C_air)
        C_max = max(C_gas, C_air)
        Cr = C_min / C_max if C_max > 0 else 0.0
        
        AC = AirCooledExchanger(
            tube_rows=geom_params['tube_rows'],
            tube_passes=geom_params['tube_passes'],
            tubes_per_row=geom_params['tubes_per_row'],
            tube_length=geom_params['tube_length'],
            tube_diameter=geom_params['tube_od'],
            fin_thickness=geom_params['fin_thickness'],
            fin_density=geom_params['fin_density'],
            pitch=geom_params['pitch'],
            angle=geom_params['angle'],
            fin_height=geom_params['fin_height'],
            tube_thickness=geom_params['tube_thickness']
        )
        
        N_tubes_total = geom_params['tube_rows'] * geom_params['tubes_per_row']
        
        D_i = geom_params['tube_od'] - 2 * geom_params['tube_thickness']
        A_flow_per_pass = (np.pi * D_i**2 / 4.0) * (N_tubes_total / geom_params['tube_passes'])
        G_process = m_dot_SI / A_flow_per_pass
        Re_process = G_process * D_i / props_in['viscosity']
        Pr_process = props_in['cp'] * props_in['viscosity'] / props_in['conductivity']
        
        if Re_process < 2100:
            Nu_process = 4.36
        elif Re_process > 4000:
            Nu_process = 0.023 * (Re_process**0.8) * (Pr_process**0.3)
        else:
            Nu_lam = 4.36
            Nu_turb = 0.023 * (4000.0**0.8) * (Pr_process**0.3)
            frac = (Re_process - 2100.0) / (4000.0 - 2100.0)
            Nu_process = Nu_lam + frac * (Nu_turb - Nu_lam)
            
        h_inside = Nu_process * props_in['conductivity'] / D_i
        
        h_o_bare_basis = ht.air_cooler.h_Briggs_Young(
            m=m_dot_air,
            A=AC.A,
            A_min=AC.A_min,
            A_increase=AC.A_increase,
            A_fin=AC.A_fin,
            A_tube_showing=AC.A_tube_showing,
            tube_diameter=AC.tube_diameter,
            fin_diameter=AC.fin_diameter,
            bare_length=AC.bare_length,
            fin_thickness=AC.fin_thickness,
            rho=rho_air,
            Cp=Cp_air,
            mu=mu_air,
            k=k_air,
            k_fin=geom_params['fin_k']
        )
        h_o_actual = h_o_bare_basis / AC.A_increase
        
        eta_fin = ht.air_cooler.fin_efficiency_Kern_Kraus(
            Do=geom_params['tube_od'],
            D_fin=AC.fin_diameter,
            t_fin=geom_params['fin_thickness'],
            k_fin=geom_params['fin_k'],
            h=h_o_actual
        )
        eta_o = 1.0 - (AC.A_fin / AC.A) * (1.0 - eta_fin)
        
        R_wall = (geom_params['tube_od'] * np.log(geom_params['tube_od'] / D_i) / (2.0 * geom_params['tube_k'])) * AC.A_increase
        R_in = (geom_params['tube_od'] * AC.A_increase / (D_i * h_inside))
        R_in_fouling = geom_params['fouling_in'] * (geom_params['tube_od'] * AC.A_increase / D_i)
        R_out_fouling = geom_params['fouling_out']
        R_out = 1.0 / (eta_o * h_o_actual)
        
        U_outside = 1.0 / (R_in + R_in_fouling + R_wall + R_out_fouling + R_out)
        
        NTU = U_outside * AC.A / C_min if C_min > 0 else 0.0
        
        if NTU > 0 and C_min > 0:
            epsilon = ht.effectiveness_from_NTU(NTU, Cr, subtype='crossflow approximate')
        else:
            epsilon = 0.0
            
        Q_actual_W = epsilon * C_min * (T_in_SI - air_in_SI)
        
        T_gas_out_SI = T_in_SI - Q_actual_W / C_gas if C_gas > 0 else T_in_SI
        T_air_out_SI = air_in_SI + Q_actual_W / C_air if C_air > 0 else air_in_SI
        
        T_gas_avg = (T_in_SI + T_gas_out_SI) / 2.0
        T_air_avg = (air_in_SI + T_air_out_SI) / 2.0
        
        P_avg_SI = (P_in_SI + P_out_SI) / 2.0
        props_avg = self.get_mixture_transport_properties(P_avg_SI, T_gas_avg)
        rho_air_avg = 101325.0 / (287.05 * T_air_avg)
        
        C_gas = m_dot_SI * props_avg['cp']
        C_min = min(C_gas, C_air)
        C_max = max(C_gas, C_air)
        Cr = C_min / C_max if C_max > 0 else 0.0
        
        Re_process = G_process * D_i / props_avg['viscosity']
        Pr_process = props_avg['cp'] * props_avg['viscosity'] / props_avg['conductivity']
        
        if Re_process < 2100:
            Nu_process = 4.36
        elif Re_process > 4000:
            Nu_process = 0.023 * (Re_process**0.8) * (Pr_process**0.3)
        else:
            Nu_lam = 4.36
            Nu_turb = 0.023 * (4000.0**0.8) * (Pr_process**0.3)
            frac = (Re_process - 2100.0) / (4000.0 - 2100.0)
            Nu_process = Nu_lam + frac * (Nu_turb - Nu_lam)
            
        h_inside = Nu_process * props_avg['conductivity'] / D_i
        
        h_o_bare_basis = ht.air_cooler.h_Briggs_Young(
            m=m_dot_air,
            A=AC.A,
            A_min=AC.A_min,
            A_increase=AC.A_increase,
            A_fin=AC.A_fin,
            A_tube_showing=AC.A_tube_showing,
            tube_diameter=AC.tube_diameter,
            fin_diameter=AC.fin_diameter,
            bare_length=AC.bare_length,
            fin_thickness=AC.fin_thickness,
            rho=rho_air_avg,
            Cp=Cp_air,
            mu=mu_air,
            k=k_air,
            k_fin=geom_params['fin_k']
        )
        h_o_actual = h_o_bare_basis / AC.A_increase
        
        eta_fin = ht.air_cooler.fin_efficiency_Kern_Kraus(
            Do=geom_params['tube_od'],
            D_fin=AC.fin_diameter,
            t_fin=geom_params['fin_thickness'],
            k_fin=geom_params['fin_k'],
            h=h_o_actual
        )
        eta_o = 1.0 - (AC.A_fin / AC.A) * (1.0 - eta_fin)
        
        R_wall = (geom_params['tube_od'] * np.log(geom_params['tube_od'] / D_i) / (2.0 * geom_params['tube_k'])) * AC.A_increase
        R_in = (geom_params['tube_od'] * AC.A_increase / (D_i * h_inside))
        R_in_fouling = geom_params['fouling_in'] * (geom_params['tube_od'] * AC.A_increase / D_i)
        R_out_fouling = geom_params['fouling_out']
        R_out = 1.0 / (eta_o * h_o_actual)
        
        U_outside = 1.0 / (R_in + R_in_fouling + R_wall + R_out_fouling + R_out)
        
        NTU = U_outside * AC.A / C_min if C_min > 0 else 0.0
        if NTU > 0 and C_min > 0:
            epsilon = ht.effectiveness_from_NTU(NTU, Cr, subtype='crossflow approximate')
        else:
            epsilon = 0.0
            
        Q_actual_W = epsilon * C_min * (T_in_SI - air_in_SI)
        T_gas_out_SI = T_in_SI - Q_actual_W / C_gas if C_gas > 0 else T_in_SI
        T_air_out_SI = air_in_SI + Q_actual_W / C_air if C_air > 0 else air_in_SI
        
        dP_air = ht.air_cooler.dP_ESDU_high_fin(
            m=m_dot_air,
            A_min=AC.A_min,
            A_increase=AC.A_increase,
            flow_area_contraction_ratio=AC.flow_area_contraction_ratio,
            tube_diameter=AC.tube_diameter,
            pitch_parallel=AC.pitch_parallel,
            pitch_normal=AC.pitch_normal,
            tube_rows=AC.tube_rows,
            rho=rho_air_avg,
            mu=mu_air
        )
        
        roughness = 4.5e-5
        relative_roughness = roughness / D_i
        v_process = G_process / props_avg['density']
        f_friction = fluids.friction_factor(Re_process, eD=relative_roughness)
        L_total = geom_params['tube_length'] * geom_params['tube_passes']
        dP_process_friction = f_friction * (L_total / D_i) * (props_avg['density'] * v_process**2 / 2.0)
        K_minor = 1.5 * (geom_params['tube_passes'] - 1)
        dP_process_minor = K_minor * (props_avg['density'] * v_process**2 / 2.0)
        dP_process_total_Pa = dP_process_friction + dP_process_minor
        
        return {
            "Q_kW": Q_actual_W / 1000.0,
            "T_gas_out_C": T_gas_out_SI - 273.15,
            "T_air_out_C": T_air_out_SI - 273.15,
            "U_W_m2K": U_outside,
            "effectiveness": epsilon,
            "NTU": NTU,
            "dP_air_Pa": dP_air,
            "gas_dP_bar": dP_process_total_Pa / 1e5,
            "gas_velocity_m_s": v_process,
            "gas_Re": Re_process,
            "h_inside_W_m2K": h_inside,
            "h_outside_actual_W_m2K": h_o_actual,
            "fin_efficiency": eta_fin,
            "surface_efficiency": eta_o,
            "gas_out_phase": self._gercek_faz_belirle(self._build_state_from_pt(P_out_SI, T_gas_out_SI))
        }
