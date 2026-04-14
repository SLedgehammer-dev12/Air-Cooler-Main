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


if __name__ == "__main__":
    unittest.main()
