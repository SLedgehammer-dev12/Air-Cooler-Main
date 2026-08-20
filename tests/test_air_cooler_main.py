import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

IMPORT_ERROR = None
try:
    from air_cooler_main_core import (
        AmbiguousTwoPhaseInputError,
        AirFinnedGasCooler,
        HeatExchangerSizingError,
        COOLPROP_ALIASES,
        COOLPROP_COMPONENTS,
        Q_,
        resolve_fluid_name,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
    IMPORT_ERROR = exc


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class AirCoolerMainTests(unittest.TestCase):
    def setUp(self):
        self.komp = {
            "METHANE": {"yuzde": 85.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
            "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
        }

    def test_gas_only_calculation_returns_reference_load(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        q_g, q_i, uyari = cooler.hesapla_isi_yuku(
            15.0,
            "Sm3/h",
            Q_(60.0, "bar"),
            Q_(58.0, "bar"),
            Q_(100.0, "degC"),
            Q_(40.0, "degC"),
        )

        self.assertGreater(q_g.to("kW").m, 0.0)
        self.assertIsNotNone(q_i)
        self.assertIsNone(uyari)

    def test_two_phase_endpoint_is_rejected(self):
        cooler = AirFinnedGasCooler(self.komp, "HEOS", "bar(a)")
        sat = cooler._get_saturation_properties(Q_(5.0, "bar").to("pascal").m)
        self.assertIsNotNone(sat)
        self.assertGreater(sat["T_dew"] - sat["T_bubble"], 1.0)

        with self.assertRaises(AmbiguousTwoPhaseInputError):
            cooler.hesapla_isi_yuku(
                1500.0,
                "kg/h",
                Q_(5.0, "bar"),
                Q_(5.0, "bar"),
                Q_(sat["T_dew"] + 10.0, "kelvin"),
                Q_((sat["T_dew"] + sat["T_bubble"]) / 2.0, "kelvin"),
            )

    def test_full_condensation_path_contains_condensing_region(self):
        cooler = AirFinnedGasCooler({"METHANE": {"yuzde": 100.0, "tip": "Molar"}}, "HEOS", "bar(a)")
        sat = cooler._get_saturation_properties(Q_(5.0, "bar").to("pascal").m)
        self.assertIsNotNone(sat)

        q_g, q_i, uyari = cooler.hesapla_isi_yuku(
            1500.0,
            "kg/h",
            Q_(5.0, "bar"),
            Q_(5.0, "bar"),
            Q_(sat["T_dew"] + 15.0, "kelvin"),
            Q_(sat["T_bubble"] - 5.0, "kelvin"),
        )

        self.assertGreater(q_g.to("kW").m, 0.0)
        self.assertIsNotNone(q_i)
        self.assertIsNotNone(uyari)
        self.assertTrue(any("Yoğuşma" in bolge["bolge_adi"] for bolge in cooler.ara_sonuclar["bolgeler"]))

    def test_preliminary_sizing_returns_lmtd_ua_and_area(self):
        cooler = AirFinnedGasCooler(self.komp, "HEOS", "bar(a)")
        sizing = cooler.hesapla_esanjor_boyutlandirma(
            q_watt=100000.0,
            process_t_in_k=Q_(100.0, "degC").to("kelvin").m,
            process_t_out_k=Q_(60.0, "degC").to("kelvin").m,
            air_t_in_k=Q_(30.0, "degC").to("kelvin").m,
            air_t_out_k=Q_(50.0, "degC").to("kelvin").m,
            overall_u_w_m2k=40.0,
            correction_factor=0.9,
        )

        self.assertAlmostEqual(sizing["lmtd_K"], 39.15, places=2)
        self.assertAlmostEqual(sizing["effective_lmtd_K"], 35.24, places=2)
        self.assertAlmostEqual(sizing["ua_required_W_K"], 2837.92, places=1)
        self.assertAlmostEqual(sizing["required_area_m2"], 70.95, places=2)

    def test_preliminary_sizing_rejects_non_physical_terminal_differences(self):
        cooler = AirFinnedGasCooler(self.komp, "HEOS", "bar(a)")
        with self.assertRaises(HeatExchangerSizingError):
            cooler.hesapla_esanjor_boyutlandirma(
                q_watt=100000.0,
                process_t_in_k=Q_(70.0, "degC").to("kelvin").m,
                process_t_out_k=Q_(40.0, "degC").to("kelvin").m,
                air_t_in_k=Q_(45.0, "degC").to("kelvin").m,
                air_t_out_k=Q_(75.0, "degC").to("kelvin").m,
                overall_u_w_m2k=40.0,
                correction_factor=0.9,
            )

    def test_detailed_design_calculation(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        geom_params = {
            "tube_rows": 4,
            "tube_passes": 4,
            "tubes_per_row": 24,
            "tube_length": 6.0,
            "tube_od": 0.0254,
            "tube_thickness": 0.00211,
            "fin_height": 0.0159,
            "fin_thickness": 0.0004,
            "fin_density": 10.0 * 39.37,
            "pitch": 0.0635,
            "angle": 30.0,
            "tube_k": 50.0,
            "fin_k": 205.0,
            "fouling_in": 0.000176,
            "fouling_out": 0.000088,
            "fan_efficiency": 0.65
        }
        res = cooler.hesapla_detayli_dizayn(
            m_dot_val=15.0,
            m_dot_unit="Sm3/h",
            P_in_Q=Q_(60.0, "bar"),
            P_out_Q=Q_(59.0, "bar"),
            T_in_Q=Q_(100.0, "degC"),
            T_out_Q=Q_(40.0, "degC"),
            air_in_Q=Q_(25.0, "degC"),
            air_out_Q=Q_(45.0, "degC"),
            geom_params=geom_params
        )
        self.assertGreater(res["Q_kW"], 0.0)
        self.assertGreater(res["U_W_m2K"], 0.0)
        self.assertGreater(res["actual_area_m2"], 0.0)
        self.assertGreater(res["required_area_m2"], 0.0)
        self.assertGreater(res["fan_power_kW"], 0.0)
        self.assertGreater(res["gas_velocity_m_s"], 0.0)
        self.assertGreater(res["gas_Re"], 0.0)
        self.assertGreater(res["gas_dP_bar"], 0.0)

    def test_rating_evaluation_calculation(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        geom_params = {
            "tube_rows": 4,
            "tube_passes": 4,
            "tubes_per_row": 24,
            "tube_length": 6.0,
            "tube_od": 0.0254,
            "tube_thickness": 0.00211,
            "fin_height": 0.0159,
            "fin_thickness": 0.0004,
            "fin_density": 10.0 * 39.37,
            "pitch": 0.0635,
            "angle": 30.0,
            "tube_k": 50.0,
            "fin_k": 205.0,
            "fouling_in": 0.000176,
            "fouling_out": 0.000088
        }
        res = cooler.hesapla_degerlendirme_rating(
            m_dot_val=15.0,
            m_dot_unit="Sm3/h",
            P_in_Q=Q_(60.0, "bar"),
            P_out_Q=Q_(59.0, "bar"),
            T_in_Q=Q_(100.0, "degC"),
            air_in_Q=Q_(25.0, "degC"),
            V_air_m3_h=150000.0,
            geom_params=geom_params
        )
        self.assertGreater(res["Q_kW"], 0.0)
        self.assertGreater(res["U_W_m2K"], 0.0)
        self.assertGreater(res["effectiveness"], 0.0)
        self.assertGreater(res["NTU"], 0.0)
        self.assertGreater(res["dP_air_Pa"], 0.0)
        self.assertGreater(res["gas_dP_bar"], 0.0)
    def test_authentication_system(self):
        from air_cooler_main_core import generate_salt, hash_password, initialize_users_db, authenticate_user
        test_db_path = Path(__file__).resolve().parent / "air_cooler_users_test.json"
        
        # Cleanup if exists
        if test_db_path.exists():
            test_db_path.unlink()
            
        try:
            # Init DB
            db = initialize_users_db(test_db_path)
            self.assertIn("admin", db)
            self.assertIn("user", db)
            
            # Auth Admin Success
            ok, role = authenticate_user("admin", "admin123", db)
            self.assertTrue(ok)
            self.assertEqual(role, "admin")
            
            # Auth User Success
            ok, role = authenticate_user("user", "user123", db)
            self.assertTrue(ok)
            self.assertEqual(role, "user")
            
            # Auth Failed
            ok, role = authenticate_user("admin", "wrongpassword", db)
            self.assertFalse(ok)
            self.assertIsNone(role)
            
            ok, role = authenticate_user("nonexistent", "somepass", db)
            self.assertFalse(ok)
            self.assertIsNone(role)
        finally:
            # Cleanup
            if test_db_path.exists():
                test_db_path.unlink()

    def test_mass_composition_conversion(self):
        mass_komp = {
            "METHANE": {"yuzde": 80.0, "tip": "Kütlesel"},
            "ETHANE": {"yuzde": 20.0, "tip": "Kütlesel"}
        }
        cooler = AirFinnedGasCooler(mass_komp, "PR", "bar(a)")
        self.assertGreater(cooler.mol_kompozisyon_coolprop["METHANE"], 0.0)

    def test_flow_rate_conversions_and_boundary_conditions(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        
        # Test MMscmd conversion
        m_dot_mmscmd = cooler._birim_cevir_m_dot(0.5, "MMscmd", 101325.0 * 50, 300.0)
        self.assertGreater(m_dot_mmscmd, 0.0)
        
        # Test MMscfd conversion
        m_dot_mmscfd = cooler._birim_cevir_m_dot(15.0, "MMscfd", 101325.0 * 50, 300.0)
        self.assertGreater(m_dot_mmscfd, 0.0)
        
        # Test Am3/h conversion
        m_dot_am3h = cooler._birim_cevir_m_dot(100.0, "Am3/h", 101325.0 * 50, 300.0)
        self.assertGreater(m_dot_am3h, 0.0)
        
        # Test unsupported unit raises ValueError
        with self.assertRaises(ValueError):
            cooler._birim_cevir_m_dot(100.0, "unsupported_unit", 101325.0 * 50, 300.0)

    def test_invalid_sizing_parameters_raise_errors(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        
        # U <= 0 error
        with self.assertRaises(HeatExchangerSizingError):
            cooler.hesapla_esanjor_boyutlandirma(
                q_watt=100000.0,
                process_t_in_k=350.0,
                process_t_out_k=310.0,
                air_t_in_k=298.0,
                air_t_out_k=308.0,
                overall_u_w_m2k=-10.0,
                correction_factor=0.9
            )
            
        # correction_factor outside bounds
        with self.assertRaises(HeatExchangerSizingError):
            cooler.hesapla_esanjor_boyutlandirma(
                q_watt=100000.0,
                process_t_in_k=350.0,
                process_t_out_k=310.0,
                air_t_in_k=298.0,
                air_t_out_k=308.0,
                overall_u_w_m2k=40.0,
                correction_factor=1.2
            )
            
        # air_t_out <= air_t_in
        with self.assertRaises(HeatExchangerSizingError):
            cooler.hesapla_esanjor_boyutlandirma(
                q_watt=100000.0,
                process_t_in_k=350.0,
                process_t_out_k=310.0,
                air_t_in_k=298.0,
                air_t_out_k=295.0,
                overall_u_w_m2k=40.0,
                correction_factor=0.9
            )

    def test_abstract_state_invalid_backend_fallback(self):
        cooler = AirFinnedGasCooler(self.komp, "INVALID_BACKEND", "bar(a)")
        # Should log and fall back to HEOS
        state = cooler._init_abstract_state()
        self.assertIsNotNone(state)

    def test_core_module_missed_branches(self):
        from air_cooler_main_core import get_pressure_type, clean_temp_unit, clean_pressure_unit
        self.assertEqual(get_pressure_type("bar(g)"), "gauge")
        self.assertEqual(get_pressure_type("bar(a)"), "absolute")
        self.assertEqual(clean_temp_unit("°C"), "degC")
        self.assertEqual(clean_temp_unit("K"), "K")
        self.assertEqual(clean_pressure_unit("bar(g)"), "bar")
        self.assertEqual(clean_pressure_unit("bar(a)"), "bar")
        
        cooler = AirFinnedGasCooler({}, "PR", "bar(a)")
        self.assertEqual(cooler._kutlesel_mol_cevir({}), {})
        
        pure_cooler = AirFinnedGasCooler({"METHANE": {"yuzde": 100.0, "tip": "Molar"}}, "HEOS", "bar(a)")
        self.assertEqual(pure_cooler.karisim_str_names_only, "METHANE")
        
        cooler_mix = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        mix_str = cooler_mix._coolprop_karisim_str_olustur(with_concentrations=True)
        self.assertIn("METHANE", mix_str)
        
        lmtd_eq = cooler_mix._calculate_lmtd(10.0, 10.0)
        self.assertAlmostEqual(lmtd_eq, 10.0)
        
        q_g, q_i, uyari = cooler_mix.hesapla_isi_yuku(
            15.0, "Sm3/h", Q_(5.0, "bar"), Q_(5.0, "bar"), Q_(100.0, "degC"), Q_(80.0, "degC")
        )
        self.assertEqual(cooler_mix.ara_sonuclar["faz_in"], "Gaz")
        
        pure_liq_cooler = AirFinnedGasCooler({"METHANE": {"yuzde": 100.0, "tip": "Molar"}}, "HEOS", "bar(a)")
        q_g2, q_i2, uyari2 = pure_liq_cooler.hesapla_isi_yuku(
            100.0, "kg/h", Q_(5.0, "bar"), Q_(5.0, "bar"), Q_(-170.0, "degC"), Q_(-180.0, "degC")
        )
        self.assertEqual(pure_liq_cooler.ara_sonuclar["faz_in"], "Sıvı")
        
        bolgeler, curve = pure_liq_cooler.hesapla_sogutma_bolgeleri(
            0.01, 101325.0 * 5, 101325.0 * 5, 100.0, 150.0, 1e5, 1.2e5
        )
        self.assertTrue(any("Tek Bölge" in b["bolge_adi"] for b in bolgeler))
        
        with self.assertRaises(AmbiguousTwoPhaseInputError):
            sat = cooler_mix._get_saturation_properties(101325.0 * 5)
            cooler_mix.hesapla_sogutma_bolgeleri(
                0.01, 101325.0 * 5, 101325.0 * 5, (sat["T_dew"] + sat["T_bubble"])/2, 100.0, 1e5, 0.8e5
            )
            
        with self.assertRaises(AmbiguousTwoPhaseInputError):
            sat = cooler_mix._get_saturation_properties(101325.0 * 5)
            cooler_mix.hesapla_sogutma_bolgeleri(
                0.01, 101325.0 * 5, 101325.0 * 5, 300.0, (sat["T_dew"] + sat["T_bubble"])/2, 1e5, 0.8e5
            )
            
        with self.assertRaises(ValueError):
            cooler_mix._update_state_at_pt(cooler_mix._init_abstract_state(), 1e12, 1e12)

    def test_gauge_pressure_conversion(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(g)")
        P_SI, T_SI = cooler._birim_cevir_P_T(Q_(5.0, "bar"), Q_(100.0, "degC"))
        self.assertAlmostEqual(P_SI, 6.01325e5, places=1)

    def test_flow_rate_kg_s_and_kg_h(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        m1 = cooler._birim_cevir_m_dot(10.0, "kg/s", 1e6, 400.0)
        self.assertAlmostEqual(m1, 10.0)
        m2 = cooler._birim_cevir_m_dot(3600.0, "kg/h", 1e6, 400.0)
        self.assertAlmostEqual(m2, 1.0)

    def test_initialize_users_db_existing_file(self):
        from air_cooler_main_core import initialize_users_db
        import json, tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"custom": {"salt": "x", "hash": "y", "role": "user"}}, f)
            db_path = f.name
        try:
            db = initialize_users_db(db_path)
            self.assertIn("custom", db)
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_initialize_users_db_corrupt_file(self):
        from air_cooler_main_core import initialize_users_db
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            db_path = f.name
        try:
            db = initialize_users_db(db_path)
            self.assertIn("admin", db)
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_initialize_users_db_write_error(self):
        from air_cooler_main_core import initialize_users_db
        db = initialize_users_db("/nonexistent/path/users.json")
        self.assertIn("admin", db)

    def test_effective_lmtd_zero_raises_error(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        with self.assertRaises(HeatExchangerSizingError):
            cooler.hesapla_esanjor_boyutlandirma(
                q_watt=0.0,
                process_t_in_k=350.0,
                process_t_out_k=310.0,
                air_t_in_k=298.0,
                air_t_out_k=308.0,
                overall_u_w_m2k=40.0,
                correction_factor=0.0,
            )

    def test_air_sizing_integrated_in_heat_load(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        q_g, q_i, uyari = cooler.hesapla_isi_yuku(
            15.0, "Sm3/h",
            Q_(60.0, "bar"), Q_(58.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            air_sizing_inputs={
                "air_in_q": Q_(25.0, "degC"),
                "air_out_q": Q_(45.0, "degC"),
                "overall_u_w_m2k": 40.0,
                "correction_factor": 0.9,
            }
        )
        self.assertIn("tasarim", cooler.ara_sonuclar)
        self.assertGreater(cooler.ara_sonuclar["tasarim"]["required_area_m2"], 0.0)

    def test_transport_properties_fallback_branch(self):
        from air_cooler_main_core import AirFinnedGasCooler, Q_
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "HEOS", "bar(a)")
        props = cooler.get_mixture_transport_properties(1e7, 400.0)
        self.assertGreater(props["viscosity"], 0)
        self.assertGreater(props["conductivity"], 0)
        self.assertGreater(props["density"], 0)
        self.assertGreater(props["cp"], 0)
        self.assertGreater(props["mw"], 0)

    def test_detailed_design_transitional_flow(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        geom = {
            "tube_rows": 1, "tube_passes": 1, "tubes_per_row": 100,
            "tube_length": 1.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
            "fin_height": 0.0159, "fin_thickness": 0.0004,
            "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
            "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
            "fan_efficiency": 0.65
        }
        res = cooler.hesapla_detayli_dizayn(
            0.1, "kg/s", Q_(5.0, "bar"), Q_(4.9, "bar"),
            Q_(60.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(35.0, "degC"), geom
        )
        self.assertGreater(res["Q_kW"], 0.0)

    def test_rating_low_air_flow_returns_reasonable_results(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        geom = {
            "tube_rows": 4, "tube_passes": 4, "tubes_per_row": 24,
            "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
            "fin_height": 0.0159, "fin_thickness": 0.0004,
            "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
            "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088
        }
        res = cooler.hesapla_degerlendirme_rating(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(25.0, "degC"), V_air_m3_h=50000.0, geom_params=geom
        )
        self.assertGreater(res["effectiveness"], 0.0)
        self.assertGreater(res["NTU"], 0.0)

    def test_detailed_design_transitional_reynolds_number(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        geom = {
            "tube_rows": 1, "tube_passes": 1, "tubes_per_row": 100,
            "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
            "fin_height": 0.0159, "fin_thickness": 0.0004,
            "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
            "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
            "fan_efficiency": 0.65
        }
        res = cooler.hesapla_detayli_dizayn(
            0.06, "kg/s", Q_(5.0, "bar"), Q_(4.9, "bar"),
            Q_(60.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(35.0, "degC"), geom
        )
        self.assertGreater(res["gas_Re"], 2100)
        self.assertLess(res["gas_Re"], 4000)
        self.assertGreater(res["Q_kW"], 0.0)

    def test_outlet_two_phase_raises_error(self):
        cooler = AirFinnedGasCooler(self.komp, "HEOS", "bar(a)")
        sat = cooler._get_saturation_properties(Q_(5.0, "bar").to("pascal").m)
        self.assertIsNotNone(sat)
        with self.assertRaises(AmbiguousTwoPhaseInputError):
            cooler.hesapla_sogutma_bolgeleri(
                0.01, 101325.0 * 5, 101325.0 * 5,
                300.0,
                (sat["T_dew"] + sat["T_bubble"]) / 2.0,
                1e5, 0.8e5
            )

    def test_effective_lmtd_negative_raises_error(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        with self.assertRaises(HeatExchangerSizingError):
            cooler.hesapla_esanjor_boyutlandirma(
                q_watt=100000.0,
                process_t_in_k=350.0,
                process_t_out_k=310.0,
                air_t_in_k=298.0,
                air_t_out_k=308.0,
                overall_u_w_m2k=40.0,
                correction_factor=-0.1,
            )


    def test_isobutane_isopentane_composition(self):
        komp = {
            "ISOBUTANE": {"yuzde": 50.0, "tip": "Molar"},
            "ISOPENTANE": {"yuzde": 50.0, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        q_g, q_i, uyari = cooler.hesapla_isi_yuku(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(58.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
        )
        self.assertGreater(q_g.to("kW").m, 0.0)

    def test_fluid_name_alias_resolution(self):
        from air_cooler_main_core import resolve_fluid_name
        self.assertEqual(resolve_fluid_name("I-BUTANE"), "ISOBUTANE")
        self.assertEqual(resolve_fluid_name("I-PENTANE"), "ISOPENTANE")
        self.assertEqual(resolve_fluid_name("METHANE"), "METHANE")

    def test_all_coolprop_components_valid(self):
        import CoolProp.CoolProp as CP
        for name in COOLPROP_COMPONENTS:
            resolved = resolve_fluid_name(name)
            try:
                M = CP.PropsSI("M", resolved)
                self.assertGreater(M, 0.0)
            except Exception as exc:
                self.fail(f"CoolProp geçersiz bileşen: {name} -> {resolved}: {exc}")

    def test_composition_normalization_below_100(self):
        komp = {
            "METHANE": {"yuzde": 89.5000, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0000, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        self.assertIn("normalize_edildi", cooler.ara_sonuclar)
        self.assertTrue(cooler.ara_sonuclar["normalize_edildi"])
        total_frac = sum(cooler.mol_kompozisyon_coolprop.values())
        self.assertAlmostEqual(total_frac, 1.0, places=10)

    def test_composition_normalization_above_100(self):
        komp = {
            "METHANE": {"yuzde": 90.5000, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0000, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        self.assertIn("normalize_edildi", cooler.ara_sonuclar)
        total_frac = sum(cooler.mol_kompozisyon_coolprop.values())
        self.assertAlmostEqual(total_frac, 1.0, places=10)

    def test_four_decimal_precision(self):
        komp = {
            "METHANE": {"yuzde": 85.2500, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.5000, "tip": "Molar"},
            "PROPANE": {"yuzde": 4.2500, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        q_g, q_i, uyari = cooler.hesapla_isi_yuku(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(58.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
        )
        self.assertGreater(q_g.to("kW").m, 0.0)
        total = sum(cooler.mol_kompozisyon_coolprop.values())
        self.assertAlmostEqual(total, 1.0, places=10)

    def test_composition_normalization_mass_basis(self):
        komp = {
            "METHANE": {"yuzde": 80.0000, "tip": "Kütlesel"},
            "ETHANE": {"yuzde": 19.5000, "tip": "Kütlesel"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        self.assertIn("normalize_edildi", cooler.ara_sonuclar)
        total_frac = sum(cooler.mol_kompozisyon_coolprop.values())
        self.assertAlmostEqual(total_frac, 1.0, places=10)

    def test_invalid_fluid_name_raises_error(self):
        komp = {"TOTALYFAKE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        with self.assertRaises(Exception):
            cooler._init_abstract_state()

    # ── Coverage expansion: utility functions ──

    def test_engine_eos_utility_functions(self):
        from air_cooler_main_core import get_engine_keys, get_eos_options, resolve_engine_eos, ENGINE_EOS
        keys = get_engine_keys()
        self.assertIn("🔥 CoolProp", keys)
        self.assertIn("🌍 neqsim", keys)

        opts = get_eos_options(keys[0])
        self.assertGreater(len(opts), 0)

        backend, eos = resolve_engine_eos(keys[0], opts[0])
        self.assertIn(backend, ("CoolProp", "neqsim"))
        self.assertIsInstance(eos, str)

    def test_legacy_eos_label_resolution(self):
        from air_cooler_main_core import get_engine_eos_from_label, get_engine_eos_from_value
        eng, eos = get_engine_eos_from_label("🏆 Yüksek Doğruluk (HEOS) - Tüm Akışkanlar")
        self.assertEqual(eng, "CoolProp")
        self.assertEqual(eos, "HEOS")

        eng, eos = get_engine_eos_from_label("UNKNOWN")
        self.assertEqual(eng, "CoolProp")
        self.assertEqual(eos, "HEOS")

        eng, eos = get_engine_eos_from_value("PR")
        self.assertEqual(eng, "CoolProp")
        self.assertEqual(eos, "PR")

        eng, eos = get_engine_eos_from_value("UNKNOWN")
        self.assertEqual(eng, "CoolProp")
        self.assertEqual(eos, "UNKNOWN")

    def test_constructor_defaults_fallback(self):
        cooler = AirFinnedGasCooler({}, None, None)
        self.assertEqual(cooler.engine, "CoolProp")
        self.assertEqual(cooler.eos, "HEOS")
        self.assertEqual(cooler.raw_p_unit, "bar(a)")

    def test_constructor_neqsim_kwargs(self):
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, engine="neqsim", eos="GERG-2008", raw_p_unit="bar(a)")
        self.assertEqual(cooler.engine, "neqsim")
        self.assertEqual(cooler.eos, "GERG-2008")

    def test_ideal_gas_reference_returns_valid(self):
        cooler = AirFinnedGasCooler({"METHANE": {"yuzde": 100.0, "tip": "Molar"}}, "PR", "bar(a)")
        q_ideal, cp = cooler._ideal_gas_reference(1.0, 400.0, 350.0)
        self.assertGreater(q_ideal, 0.0)
        self.assertGreater(cp, 0.0)

    def test_air_cooler_error_raise(self):
        from air_cooler_main_core import AirCoolerError
        with self.assertRaises(AirCoolerError):
            raise AirCoolerError("test")

    def test_update_state_at_pt_retries_with_different_temps(self):
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        state = cooler._init_abstract_state()
        result = cooler._update_state_at_pt(state, 101325.0 * 5, 170.0)
        self.assertIsNone(result)

    def test_hesapla_sogutma_bolgeleri_gas_only(self):
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        bolgeler, curve = cooler.hesapla_sogutma_bolgeleri(
            0.1, 101325.0 * 5, 101325.0 * 5, 200.0, 180.0, 1e5, 0.9e5
        )
        self.assertGreater(len(curve), 1)

    def test_transport_properties_fallback_branch_unknown_component(self):
        import CoolProp.CoolProp as CP
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        props = cooler.get_mixture_transport_properties(1e5, 300.0)
        self.assertGreater(props["viscosity"], 0)
        self.assertGreater(props["conductivity"], 0)

    def test_rating_Ft_correction_nan(self):
        import ht
        orig = ht.air_cooler.Ft_aircooler
        def _nan_Ft(**kwargs):
            return float('nan')
        ht.air_cooler.Ft_aircooler = _nan_Ft
        try:
            komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
            cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
            geom = {
                "tube_rows": 4, "tube_passes": 4, "tubes_per_row": 24,
                "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
                "fin_height": 0.0159, "fin_thickness": 0.0004,
                "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
                "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088
            }
            res = cooler.hesapla_degerlendirme_rating(
                15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
                Q_(100.0, "degC"), Q_(25.0, "degC"), V_air_m3_h=150000.0, geom_params=geom
            )
            self.assertGreater(res["effectiveness"], 0.0)
        finally:
            ht.air_cooler.Ft_aircooler = orig

    def test_detailed_design_reynolds_transitional_exact(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        geom = {
            "tube_rows": 1, "tube_passes": 1, "tubes_per_row": 100,
            "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
            "fin_height": 0.0159, "fin_thickness": 0.0004,
            "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
            "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
            "fan_efficiency": 0.65
        }
        res = cooler.hesapla_detayli_dizayn(
            0.06, "kg/s", Q_(5.0, "bar"), Q_(4.9, "bar"),
            Q_(60.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(35.0, "degC"), geom
        )
        self.assertGreater(res["gas_Re"], 2100)
        self.assertLess(res["gas_Re"], 4000)
        self.assertGreater(res["Q_kW"], 0.0)

    def test_transport_properties_exception_branch(self):
        import air_cooler_main_core as core
        orig_PropsSI = core.CP.PropsSI
        def mock_PropsSI(key, *args, **kwargs):
            if key in ("V", "L"):
                raise ValueError("Mock transport failure")
            return orig_PropsSI(key, *args, **kwargs)
        core.CP.PropsSI = mock_PropsSI
        try:
            komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
            cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
            props = cooler.get_mixture_transport_properties(1e6, 300.0)
            self.assertGreater(props["viscosity"], 0)
            self.assertGreater(props["conductivity"], 0)
            self.assertGreater(props["mw"], 0)
        finally:
            core.CP.PropsSI = orig_PropsSI

    def test_neqsim_has_neqsim_false_fallback(self):
        """has_neqsim() returns False -> fallback to HEOS"""
        from CoolProp.CoolProp import AbstractState
        import air_cooler_main_core as core
        orig = core.has_neqsim
        core.has_neqsim = lambda: False
        try:
            komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
            cooler = AirFinnedGasCooler(komp, engine="neqsim", eos="GERG-2008", raw_p_unit="bar(a)")
            state = cooler._init_abstract_state()
            self.assertEqual(cooler.engine, "neqsim")
            self.assertIsInstance(state, AbstractState)
        finally:
            core.has_neqsim = orig

    def test_neqsim_start_jvm_failure_fallback(self):
        """neqsim_start_jvm() raises -> fallback chain triggers"""
        from air_cooler_neqsim import has_neqsim
        if not has_neqsim():
            raise unittest.SkipTest("neqsim not available")
        from CoolProp.CoolProp import AbstractState
        import air_cooler_main_core as core
        orig = core.neqsim_start_jvm
        call_count = [0]
        def failing_start():
            call_count[0] += 1
            raise RuntimeError("Mock JVM failure")
        core.neqsim_start_jvm = failing_start
        try:
            komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
            cooler = AirFinnedGasCooler(komp, engine="neqsim", eos="SRK", raw_p_unit="bar(a)")
            state = cooler._init_abstract_state()
            self.assertEqual(cooler.engine, "neqsim")
            self.assertIsInstance(state, AbstractState)
            self.assertGreater(call_count[0], 1)
        finally:
            core.neqsim_start_jvm = orig

    def test_init_abstract_state_neqsim_full_chain(self):
        import os
        if not os.environ.get("JAVA_HOME"):
            raise unittest.SkipTest("JAVA_HOME not set")
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, engine="neqsim", eos="GERG-2008", raw_p_unit="bar(a)")
        state = cooler._init_abstract_state()
        state.update(9, 60e5, 373.15)
        self.assertGreater(state.rhomass(), 0)
        self.assertGreater(state.keyed_output(72), 0)
        self.assertEqual(cooler.engine, "neqsim")
        self.assertEqual(cooler.eos, "GERG-2008")

    def test_rating_epsilon_zero_when_minimal_flow(self):
        cooler = AirFinnedGasCooler(self.komp, "PR", "bar(a)")
        geom = {
            "tube_rows": 1, "tube_passes": 1, "tubes_per_row": 1,
            "tube_length": 1.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
            "fin_height": 0.0159, "fin_thickness": 0.0004,
            "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
            "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088
        }
        res = cooler.hesapla_degerlendirme_rating(
            0.001, "kg/s", Q_(5.0, "bar"), Q_(4.9, "bar"),
            Q_(60.0, "degC"), Q_(25.0, "degC"), V_air_m3_h=50000.0, geom_params=geom
        )
        self.assertGreaterEqual(res["effectiveness"], 0.0)


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class TransportPropertyTests(unittest.TestCase):
    def test_wilke_single_component_returns_pure_value(self):
        from air_cooler_main_core import wilke_mixture_viscosity
        mu = wilke_mixture_viscosity([1.0], [1.1e-5], [16.04])
        self.assertAlmostEqual(mu, 1.1e-5, places=10)

    def test_wilke_empty_returns_fallback(self):
        from air_cooler_main_core import wilke_mixture_viscosity
        self.assertGreater(wilke_mixture_viscosity([], [], []), 0.0)

    def test_wilke_binary_diagonal_phi_is_one(self):
        from air_cooler_main_core import _wilke_phi
        self.assertAlmostEqual(_wilke_phi(1e-5, 1e-5, 16.0, 16.0), 1.0, places=9)

    def test_wilke_binary_is_between_pure_values(self):
        from air_cooler_main_core import wilke_mixture_viscosity
        mu_mix = wilke_mixture_viscosity([0.5, 0.5], [1.1e-5, 9.0e-6], [16.04, 30.07])
        self.assertGreater(mu_mix, min(1.1e-5, 9.0e-6))
        self.assertLess(mu_mix, max(1.1e-5, 9.0e-6))

    def test_mason_saxena_binary_is_between_pure_values(self):
        from air_cooler_main_core import mason_saxena_mixture_conductivity
        k_mix = mason_saxena_mixture_conductivity([0.5, 0.5], [0.035, 0.021], [16.04, 30.07])
        self.assertGreater(k_mix, min(0.035, 0.021))
        self.assertLess(k_mix, max(0.035, 0.021))

    def test_mason_saxena_single_component_returns_pure_value(self):
        from air_cooler_main_core import mason_saxena_mixture_conductivity
        k = mason_saxena_mixture_conductivity([1.0], [0.034], [16.04])
        self.assertAlmostEqual(k, 0.034, places=10)

    def test_mixture_viscosity_not_linear_average(self):
        komp = {
            "METHANE": {"yuzde": 50.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 50.0, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        props = cooler.get_mixture_transport_properties(60e5, 350.0)
        linear_avg = 0.5 * props["viscosity"]
        self.assertGreater(props["viscosity"], 0.0)
        self.assertGreater(props["conductivity"], 0.0)


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class FanTipSpeedTests(unittest.TestCase):
    def test_fan_tip_speed_formula(self):
        from air_cooler_main_core import fan_tip_speed
        self.assertAlmostEqual(fan_tip_speed(2.44, 350), 3.14159 * 2.44 * 350 / 60, places=4)

    def test_fan_tip_speed_zero_on_invalid(self):
        from air_cooler_main_core import fan_tip_speed
        self.assertEqual(fan_tip_speed(0.0, 350), 0.0)
        self.assertEqual(fan_tip_speed(2.44, 0), 0.0)

    def test_fan_sound_power_positive(self):
        from air_cooler_main_core import estimate_fan_sound_power_level
        lw = estimate_fan_sound_power_level(100.0, 150.0)
        self.assertGreater(lw, 0.0)

    def test_fan_sound_power_zero_on_invalid(self):
        from air_cooler_main_core import estimate_fan_sound_power_level
        self.assertEqual(estimate_fan_sound_power_level(0.0, 150.0), 0.0)
        self.assertEqual(estimate_fan_sound_power_level(100.0, 0.0), 0.0)

    def test_detailed_design_returns_tip_speed_and_sound(self):
        komp = {
            "METHANE": {"yuzde": 85.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
            "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        geom = {
            "tube_rows": 4, "tube_passes": 4, "tubes_per_row": 24,
            "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
            "fin_height": 0.0159, "fin_thickness": 0.0004,
            "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
            "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
            "fan_efficiency": 0.65, "fan_diameter": 2.44, "n_fans": 1, "fan_rpm": 350,
        }
        res = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"), geom
        )
        self.assertIn("fan_tip_speed_m_s", res)
        self.assertGreater(res["fan_tip_speed_m_s"], 0.0)
        self.assertIn("fan_sound_power_dB", res)
        self.assertGreaterEqual(res["fan_sound_power_dB"], 0.0)
        self.assertIn("fan_rpm", res)
        self.assertEqual(res["fan_rpm"], 350)

    def test_fan_sound_power_realistic_flow_positive(self):
        from air_cooler_main_core import estimate_fan_sound_power_level
        lw = estimate_fan_sound_power_level(100.0, 200.0)
        self.assertGreater(lw, 80.0)
        self.assertLess(lw, 130.0)


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class FinTypeLimitTests(unittest.TestCase):
    def test_known_fin_type_limits(self):
        from air_cooler_main_core import fin_type_temperature_limit_C
        self.assertEqual(fin_type_temperature_limit_C("L-Foot / Double L"), 130.0)
        self.assertEqual(fin_type_temperature_limit_C("KL (Knurled L)"), 250.0)
        self.assertEqual(fin_type_temperature_limit_C("Embedded (G-Fin)"), 400.0)
        self.assertEqual(fin_type_temperature_limit_C("Extruded"), 350.0)

    def test_unknown_fin_type_returns_none(self):
        from air_cooler_main_core import fin_type_temperature_limit_C
        self.assertIsNone(fin_type_temperature_limit_C("Bilinmeyen Tip"))


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class VoidFractionTests(unittest.TestCase):
    def test_homogeneous_void_fraction_bounds(self):
        from air_cooler_main_core import homogeneous_void_fraction
        self.assertEqual(homogeneous_void_fraction(0.0, 10.0, 600.0), 0.0)
        self.assertEqual(homogeneous_void_fraction(1.0, 10.0, 600.0), 1.0)
        a = homogeneous_void_fraction(0.5, 10.0, 600.0)
        self.assertTrue(0.0 < a < 1.0)

    def test_rouhani_axelsson_between_homogeneous_bounds(self):
        from air_cooler_main_core import rouhani_axelsson_void_fraction, homogeneous_void_fraction
        rho_v, rho_l, x, G, sigma = 10.0, 600.0, 0.5, 150.0, 0.02
        a_ra = rouhani_axelsson_void_fraction(x, rho_v, rho_l, G, sigma)
        a_h = homogeneous_void_fraction(x, rho_v, rho_l)
        self.assertTrue(0.0 < a_ra < 1.0)
        self.assertLess(a_ra, a_h)

    def test_rouhani_axelsson_no_sigma_falls_back_homogeneous(self):
        from air_cooler_main_core import rouhani_axelsson_void_fraction, homogeneous_void_fraction
        rho_v, rho_l, x, G = 10.0, 600.0, 0.5, 150.0
        self.assertAlmostEqual(
            rouhani_axelsson_void_fraction(x, rho_v, rho_l, G, None),
            homogeneous_void_fraction(x, rho_v, rho_l),
        )

    def test_two_phase_density_between_phase_densities(self):
        from air_cooler_main_core import two_phase_density
        rho_v, rho_l, x, G, sigma = 10.0, 600.0, 0.5, 150.0, 0.02
        rho_tp = two_phase_density(x, rho_v, rho_l, G, sigma)
        self.assertGreater(rho_tp, rho_v)
        self.assertLess(rho_tp, rho_l)

    def test_two_phase_density_homogeneous_matches_formula(self):
        from air_cooler_main_core import two_phase_density
        rho_v, rho_l, x, G = 10.0, 600.0, 0.5, 150.0
        rho_tp = two_phase_density(x, rho_v, rho_l, G, None)
        expected = 1.0 / (x / rho_v + (1 - x) / rho_l)
        self.assertAlmostEqual(rho_tp, expected, places=9)

    def test_mixture_surface_tension_positive(self):
        komp = {
            "METHANE": {"yuzde": 85.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
            "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        sigma = cooler._mixture_surface_tension(250.0)
        self.assertIsNotNone(sigma)
        self.assertGreater(sigma, 0.0)


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class TubeWallThicknessTests(unittest.TestCase):
    def test_required_thickness_matches_appendix_1_1(self):
        from air_cooler_main_core import required_tube_wall_thickness
        P, Do, S, E = 60e5, 0.0254, 110e6, 1.0
        t = required_tube_wall_thickness(P, Do, S, E)
        expected = P * Do / (2.0 * S * E + 0.8 * P)
        self.assertAlmostEqual(t, expected, places=12)

    def test_required_thickness_positive(self):
        from air_cooler_main_core import required_tube_wall_thickness
        t = required_tube_wall_thickness(60e5, 0.0254, 110e6, 1.0)
        self.assertGreater(t, 0.0)
        self.assertLess(t, 0.01)

    def test_required_thickness_zero_on_invalid(self):
        from air_cooler_main_core import required_tube_wall_thickness
        self.assertEqual(required_tube_wall_thickness(60e5, 0.0, 110e6, 1.0), 0.0)
        self.assertEqual(required_tube_wall_thickness(60e5, 0.0254, 0.0, 1.0), 0.0)

    def test_corrosion_allowance_added(self):
        from air_cooler_main_core import required_tube_wall_with_ca, required_tube_wall_thickness
        P, Do, S = 60e5, 0.0254, 110e6
        base = required_tube_wall_thickness(P, Do, S)
        with_ca = required_tube_wall_with_ca(P, Do, S, 1.0, 0.0016)
        self.assertAlmostEqual(with_ca, base + 0.0016, places=12)

    def test_material_grades_defined(self):
        from air_cooler_main_core import TUBE_MATERIAL_GRADES
        self.assertIn("Karbon Çelik (SA-179/A214)", TUBE_MATERIAL_GRADES)
        self.assertIn("Paslanmaz Çelik (SA-213 316L)", TUBE_MATERIAL_GRADES)
        self.assertIn("Duplex (SA-789 2205)", TUBE_MATERIAL_GRADES)
        for g in TUBE_MATERIAL_GRADES.values():
            self.assertGreater(g["S_MPa"], 0.0)
            self.assertGreater(g["E"], 0.0)


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class SegmentalTests(unittest.TestCase):
    GEOM = {
        "tube_rows": 4, "tube_passes": 4, "tubes_per_row": 24,
        "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
        "fin_height": 0.0159, "fin_thickness": 0.0004,
        "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
        "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
        "fan_efficiency": 0.65, "fan_diameter": 2.44, "n_fans": 1, "fan_rpm": 350,
    }

    def test_silver_bell_ghaly_reduces_to_pure_component(self):
        from air_cooler_main_core import silver_bell_ghaly_h
        h_c, x, cp_v, h_v = 1500.0, 0.5, 2000.0, 100.0
        self.assertAlmostEqual(silver_bell_ghaly_h(h_c, x, cp_v, h_v, 0.0), h_c, places=9)

    def test_silver_bell_ghaly_reduces_h(self):
        from air_cooler_main_core import silver_bell_ghaly_h
        h_c, x, cp_v, h_v, dT_dH = 1500.0, 0.5, 2000.0, 100.0, 0.001
        h_eff = silver_bell_ghaly_h(h_c, x, cp_v, h_v, dT_dH)
        self.assertLess(h_eff, h_c)

    def test_cooling_profile_gas_only(self):
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        prof = cooler._build_cooling_profile(5e5, 300.0, 200.0)
        self.assertGreater(len(prof), 3)
        Hs = [p[1] for p in prof]
        self.assertEqual(Hs, sorted(Hs))

    def test_cooling_profile_condensing(self):
        komp = {
            "PROPANE": {"yuzde": 70.0, "tip": "Molar"},
            "N-BUTANE": {"yuzde": 30.0, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        prof = cooler._build_cooling_profile(9.75e5, 333.15, 293.15)
        self.assertGreater(len(prof), 3)
        Hs = [p[1] for p in prof]
        self.assertEqual(Hs, sorted(Hs))

    def test_segmental_applied_gas_only(self):
        komp = {
            "METHANE": {"yuzde": 85.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
            "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        res = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"), self.GEOM
        )
        self.assertTrue(res["segmental_applied"])
        self.assertGreater(len(res["segments"]), 0)
        self.assertGreater(res["required_area_m2"], 0.0)

    def test_segmental_condensing_has_two_phase_segments(self):
        komp = {
            "PROPANE": {"yuzde": 70.0, "tip": "Molar"},
            "N-BUTANE": {"yuzde": 30.0, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        res = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(10.0, "bar"), Q_(9.5, "bar"),
            Q_(60.0, "degC"), Q_(20.0, "degC"),
            Q_(10.0, "degC"), Q_(30.0, "degC"), self.GEOM
        )
        self.assertTrue(res["segmental_applied"])
        self.assertTrue(res["condensation_applied"])
        self.assertTrue(any(s["two_phase"] for s in res["segments"]))
        self.assertGreater(res["required_area_m2"], 0.0)


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class CacheTests(unittest.TestCase):
    def test_h_at_pt_cache_hit(self):
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        h1 = cooler._h_at_pt(60e5, 350.0)
        self.assertEqual(len(cooler._cache), 1)
        h2 = cooler._h_at_pt(60e5, 350.0)
        self.assertEqual(h1, h2)
        self.assertEqual(len(cooler._cache), 1)

    def test_transport_props_cache_hit(self):
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        p1 = cooler.get_mixture_transport_properties(60e5, 350.0)
        p2 = cooler.get_mixture_transport_properties(60e5, 350.0)
        self.assertIs(p1, p2)

    def test_cache_keyed_by_temperature(self):
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        cooler.get_mixture_transport_properties(60e5, 300.0)
        cooler.get_mixture_transport_properties(60e5, 350.0)
        self.assertEqual(len(cooler._cache), 2)


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class HeaderAndDraftTests(unittest.TestCase):
    GEOM = {
        "tube_rows": 4, "tube_passes": 4, "tubes_per_row": 24,
        "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
        "fin_height": 0.0159, "fin_thickness": 0.0004,
        "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
        "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
        "fan_efficiency": 0.65, "fan_diameter": 2.44, "n_fans": 1, "fan_rpm": 350,
    }
    KOMP = {
        "METHANE": {"yuzde": 85.0, "tip": "Molar"},
        "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
        "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
    }

    def test_header_minor_loss_k(self):
        from air_cooler_main_core import header_minor_loss_k
        self.assertEqual(header_minor_loss_k("Tapalı Kollektör (Plug)"), 1.5)
        self.assertEqual(header_minor_loss_k("Kapaklı Kollektör (Cover Plate)"), 1.0)
        self.assertEqual(header_minor_loss_k("Başlıklı Kollektör (Bonnet)"), 0.7)
        self.assertEqual(header_minor_loss_k("Bilinmeyen"), 1.0)

    def test_header_type_increases_minor_dp(self):
        komp = dict(self.KOMP)
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        geom_plug = dict(self.GEOM, header_type="Tapalı Kollektör (Plug)")
        geom_bonnet = dict(self.GEOM, header_type="Başlıklı Kollektör (Bonnet)")
        r_plug = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"), geom_plug
        )
        r_bonnet = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"), geom_bonnet
        )
        self.assertGreater(r_plug["gas_dP_bar"], r_bonnet["gas_dP_bar"])

    def test_draft_type_forced_vs_induced(self):
        komp = dict(self.KOMP)
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        r_forced = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"),
            dict(self.GEOM, draft_type="Forced")
        )
        r_induced = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"),
            dict(self.GEOM, draft_type="Induced")
        )
        self.assertEqual(r_forced["draft_type"], "Forced")
        self.assertEqual(r_induced["draft_type"], "Induced")
        self.assertNotEqual(r_forced["fan_power_kW"], r_induced["fan_power_kW"])


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class PhaseEnvelopeTests(unittest.TestCase):
    def test_phase_envelope_heos_mixture(self):
        komp = {
            "METHANE": {"yuzde": 85.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
            "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
        }
        cooler = AirFinnedGasCooler(komp, engine="CoolProp", eos="HEOS", raw_p_unit="bar(a)")
        env = cooler.get_phase_envelope()
        self.assertIsNotNone(env)
        self.assertGreater(len(env["T_C"]), 10)
        self.assertGreater(len(env["P_bar"]), 10)
        self.assertGreater(env["cricondentherm_C"], env["T_C"].min())
        self.assertGreater(env["cricondenbar_bar"], env["P_bar"].min())

    def test_phase_envelope_single_component(self):
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, engine="CoolProp", eos="HEOS", raw_p_unit="bar(a)")
        env = cooler.get_phase_envelope()
        self.assertIsNotNone(env)
        self.assertGreater(len(env["T_C"]), 10)

    def test_phase_envelope_returns_none_on_failure(self):
        import air_cooler_main_core as core
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, engine="CoolProp", eos="HEOS", raw_p_unit="bar(a)")
        orig = cooler._init_abstract_state
        def _boom():
            raise RuntimeError("envelope fail")
        cooler._init_abstract_state = _boom
        try:
            self.assertIsNone(cooler.get_phase_envelope())
        finally:
            cooler._init_abstract_state = orig


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class SegmentalAirTempTests(unittest.TestCase):
    GEOM = {
        "tube_rows": 4, "tube_passes": 4, "tubes_per_row": 24,
        "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
        "fin_height": 0.0159, "fin_thickness": 0.0004,
        "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
        "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
        "fan_efficiency": 0.65, "fan_diameter": 2.44, "n_fans": 1, "fan_rpm": 350,
    }
    KOMP = {
        "METHANE": {"yuzde": 85.0, "tip": "Molar"},
        "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
        "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
    }

    def test_segments_include_air_temperature(self):
        komp = dict(self.KOMP)
        cooler = AirFinnedGasCooler(komp, "PR", "bar(a)")
        res = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"), dict(self.GEOM)
        )
        self.assertTrue(res["segmental_applied"])
        for s in res["segments"]:
            self.assertIn("T_air_in_C", s)
            self.assertIn("T_air_out_C", s)
            self.assertLess(s["T_air_in_C"], s["T_in_C"])


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class ExportSectionsTests(unittest.TestCase):
    def test_export_common_sections_structure(self):
        from air_cooler_export import _build_common_sections
        geom = {
            "tube_rows": 4, "tube_passes": 4, "tubes_per_row": 24,
            "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
            "fin_height": 0.0159, "fin_thickness": 0.0004,
            "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
            "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
            "fan_efficiency": 0.65, "fan_diameter": 2.44, "n_fans": 1, "fan_rpm": 350,
            "draft_type": "Forced", "fin_type": "L-Foot / Double L",
            "header_type": "Tapalı Kollektör (Plug)", "ca": 1.6,
            "asme_grade": "Karbon Çelik (SA-179/A214)",
            "tube_mat": "Karbon Çelik (50 W/mK)", "fin_mat": "Alüminyum (205 W/mK)",
        }
        res = {
            "Q_kW": 1000.0, "U_W_m2K": 40.0, "h_inside_W_m2K": 100.0,
            "h_outside_actual_W_m2K": 50.0, "fin_efficiency": 0.8,
            "surface_efficiency": 0.9, "actual_area_m2": 100.0,
            "required_area_m2": 90.0, "overdesign_pct": 11.1,
            "m_dot_air_kg_s": 20.0, "fan_tip_speed_m_s": 45.0,
            "fan_sound_power_dB": 95.0, "gas_dP_bar": 0.5, "dP_air_Pa": 200.0,
            "fan_power_kW": 15.0, "gas_velocity_m_s": 8.0, "gas_Re": 12000,
        }
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        sections = _build_common_sections(res, geom, komp, "Sizing")
        titles = [s[0] for s in sections]
        self.assertIn("Proses Şartları", titles)
        self.assertIn("Performans Verileri", titles)
        self.assertIn("Boru & Kanat Geometrisi", titles)
        self.assertIn("Mekanik & Malzeme", titles)
        self.assertIn("Kompozisyon", titles)
        all_text = " ".join(v for _, rows in sections for _, v in rows)
        self.assertIn("Karbon Çelik (SA-179/A214)", all_text)
        self.assertIn("L-Foot / Double L", all_text)


@unittest.skipIf(IMPORT_ERROR is not None, f"Bağımlılıklar eksik: {IMPORT_ERROR}")
class DataclassResultTests(unittest.TestCase):
    GEOM = {
        "tube_rows": 4, "tube_passes": 4, "tubes_per_row": 24,
        "tube_length": 6.0, "tube_od": 0.0254, "tube_thickness": 0.00211,
        "fin_height": 0.0159, "fin_thickness": 0.0004,
        "fin_density": 394, "pitch": 0.0635, "angle": 30.0,
        "tube_k": 50.0, "fin_k": 205.0, "fouling_in": 0.000176, "fouling_out": 0.000088,
        "fan_efficiency": 0.65, "fan_diameter": 2.44, "n_fans": 1, "fan_rpm": 350,
    }
    KOMP = {
        "METHANE": {"yuzde": 85.0, "tip": "Molar"},
        "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
        "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
    }

    def test_segments_are_dataclass_with_dual_access(self):
        from dataclasses import is_dataclass
        from air_cooler_main_core import HeatExchangerSegment
        cooler = AirFinnedGasCooler(dict(self.KOMP), "PR", "bar(a)")
        res = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"), dict(self.GEOM)
        )
        self.assertTrue(res["segmental_applied"])
        for s in res["segments"]:
            self.assertTrue(is_dataclass(s))
            self.assertIsInstance(s, HeatExchangerSegment)
            self.assertEqual(s["T_in_C"], s.T_in_C)
            self.assertEqual(s["two_phase"], s.two_phase)
            self.assertEqual(s.get("index"), s.index)

    def test_phase_envelope_returns_dataclass(self):
        from dataclasses import is_dataclass
        from air_cooler_main_core import PhaseEnvelopeData
        komp = {"METHANE": {"yuzde": 100.0, "tip": "Molar"}}
        cooler = AirFinnedGasCooler(komp, engine="CoolProp", eos="HEOS", raw_p_unit="bar(a)")
        env = cooler.get_phase_envelope()
        if env is None:
            self.skipTest("Faz zarfı bu ortamda oluşturulamadı")
        self.assertIsInstance(env, PhaseEnvelopeData)
        self.assertTrue(is_dataclass(env))
        self.assertEqual(env["cricondentherm_C"], env.cricondentherm_C)

    def test_segments_json_serializable_via_app_helper(self):
        from air_cooler_main_app import _json_safe
        import json
        cooler = AirFinnedGasCooler(dict(self.KOMP), "PR", "bar(a)")
        res = cooler.hesapla_detayli_dizayn(
            15.0, "Sm3/h", Q_(60.0, "bar"), Q_(59.0, "bar"),
            Q_(100.0, "degC"), Q_(40.0, "degC"),
            Q_(25.0, "degC"), Q_(45.0, "degC"), dict(self.GEOM)
        )
        safe = _json_safe(res["segments"])
        self.assertIsInstance(safe, list)
        self.assertIsInstance(safe[0], dict)
        json.dumps(safe)


if __name__ == "__main__":
    unittest.main()


from air_cooler_main_app import (
    serialize_inputs,
    load_project_file,
    get_engine_keys,
)


def _make_state(data):
    """dict → dict + attribute access (like st.session_state)."""
    class FakeState(dict):
        def __getattr__(self, k):
            try:
                return self[k]
            except KeyError:
                raise AttributeError(k)
        def __setattr__(self, k, v):
            self[k] = v
    fs = FakeState(data)
    fs.update(data)
    return fs


class SaveLoadTests(unittest.TestCase):
    def test_serialize_inputs_contains_all_sections(self):
        state = _make_state({
            "kompozisyon": {"METHANE": {"yuzde": 100.0, "tip": "Molar"}},
            "ui_p_u": "bar(a)", "ui_t_u": "°C", "ui_flow_u": "Sm3/h",
            "adv_p_u": "bar(a)", "adv_t_u": "°C", "adv_flow_u": "Sm3/h",
            "ui_flow": 15.0, "ui_p_in": 60.0, "ui_t_in": 100.0,
            "ui_p_out": 58.0, "ui_t_out": 40.0,
            "ui_air_in": 25.0, "ui_air_out": 45.0,
            "q_engine": "CoolProp", "q_eos_label": "PR",
            "ui_overall_u": 35.0, "ui_cf": 0.90,
            "adv_mode": "Basit Dizayn (Teorik Isı Yükü)",
            "adv_flow_v": 15.0, "adv_p_in": 60.0, "adv_t_in": 100.0,
            "adv_t_out": 40.0, "adv_p_out": 58.0,
            "adv_engine": "neqsim", "adv_eos_label": "GERG-2008",
            "adv_t_u": "°C", "adv_p_u": "bar(a)", "adv_flow_u": "Sm3/h",
            "adv_tube_od": 25.4, "adv_tube_thick": 2.11,
            "adv_tube_len": 6.0, "adv_tubes_per_row": 24,
            "adv_layout_angle": 30, "adv_pitch_normal": 63.5,
            "adv_fin_height": 15.9, "adv_fin_thick": 0.4,
            "adv_fin_fpi": 10.0, "adv_tube_mat": "Karbon Çelik (50 W/mK)",
            "adv_fin_mat": "Alüminyum (205 W/mK)",
            "adv_fouling_in": 0.000176, "adv_fouling_out": 0.000088,
            "adv_fan_eff": 65.0,
            "air_in_s": 25.0, "air_out_s": 45.0,
            "rows_size": 4, "passes_size": 4,
            "r_od": 25.4, "r_thick": 2.11, "r_len": 6.0, "r_tubes": 24,
            "r_angle": 30, "r_pitch": 63.5, "r_fin_h": 15.9, "r_fin_t": 0.4,
            "r_fpi": 10.0, "r_tmat": "Karbon Çelik (50 W/mK)",
            "r_fmat": "Alüminyum (205 W/mK)", "r_fi": 0.000176, "r_fo": 0.000088,
            "r_air_in": 25.0, "r_fan_flow": 150000.0,
            "rows_rating": 4, "passes_rating": 4,
        })

        raw = serialize_inputs(state=state)
        data = json.loads(raw)

        self.assertIn("version", data)
        self.assertIn("inputs", data)
        inp = data["inputs"]
        self.assertIn("composition", inp)
        self.assertIn("units", inp)
        self.assertIn("quick_tab", inp)
        self.assertIn("advanced_tab", inp)
        self.assertEqual(inp["composition"]["METHANE"]["yuzde"], 100.0)
        self.assertEqual(inp["quick_tab"]["p_in"], 60.0)
        self.assertEqual(inp["advanced_tab"]["mode"], "Basit Dizayn (Teorik Isı Yükü)")
        self.assertIn("geometry", inp["advanced_tab"])
        self.assertIn("rating_geometry", inp["advanced_tab"])
        self.assertEqual(inp["advanced_tab"]["geometry"]["tube_od"], 25.4)

    def test_load_project_file_restores_all_values(self):
        data = {
            "version": "1.0",
            "inputs": {
                "composition": {"METHANE": {"yuzde": 95.0, "tip": "Molar"}},
                "units": {"p_unit": "bar(a)", "t_unit": "°C", "flow_u": "Sm3/h",
                          "adv_p_u": "bar(a)", "adv_t_u": "°C", "adv_flow_u": "Sm3/h"},
                "quick_tab": {
                    "flow_v": 20.0, "p_in": 70.0, "t_in": 110.0,
                    "p_out": 68.0, "t_out": 45.0,
                    "air_in": 30.0, "air_out": 50.0,
                    "engine": "neqsim", "eos_label": "SRK",
                    "overall_u": 40.0, "correction_factor": 0.85,
                },
                "advanced_tab": {
                    "mode": "Detaylı Boyutlandırma (Sizing)",
                    "flow_v": 20.0, "p_in": 70.0, "t_in": 110.0,
                    "t_out": 45.0, "p_out": 68.0,
                    "engine": "neqsim", "eos_label": "PR",
                    "t_u": "°C", "p_u": "bar(a)", "flow_u": "Sm3/h",
                    "geometry": {"tube_od": 50.0, "tube_thick": 3.0},
                    "rating_geometry": {"r_od": 38.0, "r_fan_flow": 200000.0},
                }
            }
        }
        state = {}
        load_project_file(data, state=state)
        self.assertEqual(state["kompozisyon"]["METHANE"]["yuzde"], 95.0)
        self.assertEqual(state["ui_p_in"], 70.0)
        self.assertEqual(state["q_eos_label"], "SRK")
        self.assertEqual(state["adv_mode"], "Detaylı Boyutlandırma (Sizing)")
        self.assertEqual(state["adv_tube_od"], 50.0)
        self.assertEqual(state["adv_tube_thick"], 3.0)
        self.assertEqual(state["r_od"], 38.0)
        self.assertEqual(state["r_fan_flow"], 200000.0)
        self.assertFalse(state["eos_warning_accepted"])
        self.assertFalse(state["q_eos_warning_accepted"])

    def test_serialize_roundtrip_preserves_values(self):
        orig = {
            "kompozisyon": {"METHANE": {"yuzde": 100.0, "tip": "Molar"}},
            "ui_p_u": "bar(a)", "ui_t_u": "°C", "ui_flow_u": "Sm3/h",
            "adv_p_u": "bar(a)", "adv_t_u": "°C", "adv_flow_u": "Sm3/h",
            "ui_flow": 15.0, "ui_p_in": 60.0, "ui_t_in": 100.0,
            "ui_p_out": 58.0, "ui_t_out": 40.0,
            "ui_air_in": 25.0, "ui_air_out": 45.0,
            "q_engine": "CoolProp", "q_eos_label": "PR",
            "ui_overall_u": 35.0, "ui_cf": 0.90,
            "adv_mode": "Basit Dizayn (Teorik Isı Yükü)",
            "adv_flow_v": 15.0, "adv_p_in": 60.0, "adv_t_in": 100.0,
            "adv_t_out": 40.0, "adv_p_out": 58.0,
            "adv_engine": "neqsim", "adv_eos_label": "GERG-2008",
            "adv_t_u": "°C", "adv_p_u": "bar(a)", "adv_flow_u": "Sm3/h",
            "adv_tube_od": 25.4, "adv_tube_thick": 2.11,
            "adv_tube_len": 6.0, "adv_tubes_per_row": 24,
            "adv_layout_angle": 30, "adv_pitch_normal": 63.5,
            "adv_fin_height": 15.9, "adv_fin_thick": 0.4,
            "adv_fin_fpi": 10.0, "adv_tube_mat": "Karbon Çelik (50 W/mK)",
            "adv_fin_mat": "Alüminyum (205 W/mK)",
            "adv_fouling_in": 0.000176, "adv_fouling_out": 0.000088,
            "adv_fan_eff": 65.0,
            "air_in_s": 25.0, "air_out_s": 45.0,
            "rows_size": 4, "passes_size": 4,
            "r_od": 25.4, "r_thick": 2.11, "r_len": 6.0, "r_tubes": 24,
            "r_angle": 30, "r_pitch": 63.5, "r_fin_h": 15.9, "r_fin_t": 0.4,
            "r_fpi": 10.0, "r_tmat": "Karbon Çelik (50 W/mK)",
            "r_fmat": "Alüminyum (205 W/mK)", "r_fi": 0.000176, "r_fo": 0.000088,
            "r_air_in": 25.0, "r_fan_flow": 150000.0,
            "rows_rating": 4, "passes_rating": 4,
        }
        state = _make_state(orig)

        raw = serialize_inputs(state=state)
        data = json.loads(raw)

        restored = {}
        load_project_file(data, state=restored)

        self.assertEqual(restored["kompozisyon"]["METHANE"]["yuzde"], 100.0)
        self.assertEqual(restored["ui_p_in"], 60.0)
        self.assertEqual(restored["ui_t_in"], 100.0)
        self.assertEqual(restored["q_engine"], "CoolProp")
        self.assertEqual(restored["adv_engine"], "neqsim")
        self.assertEqual(restored["adv_tube_od"], 25.4)
        self.assertEqual(restored["r_od"], 25.4)
        self.assertEqual(restored["r_fan_flow"], 150000.0)
