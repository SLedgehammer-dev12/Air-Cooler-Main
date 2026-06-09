import sys
import unittest
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
        Q_,
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


if __name__ == "__main__":
    unittest.main()
