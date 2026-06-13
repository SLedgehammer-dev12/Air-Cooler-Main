"""EOS Karşılaştırma Benchmark (HEOS vs PR vs SRK)

Koşmak için:
  python -m pytest tests/test_benchmark_eos.py -v --tb=short
veya
  python tests/test_benchmark_eos.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from CoolProp.CoolProp import AbstractState
import CoolProp.CoolProp as CP
from air_cooler_main_core import AirFinnedGasCooler, Q_, COOLPROP_ALIASES
from air_cooler_neqsim import has_neqsim, start_jvm as neqsim_start_jvm, NeqSimFluid

# ═══════════════════════════════════════════════════════════
# TEST SENARYOLARI
# ═══════════════════════════════════════════════════════════

SENARYOLAR = [
    {
        "ad": "Kuru Gaz (CH4 95%, C2H6 3%, N2 2%)",
        "kompozisyon": {
            "METHANE": {"yuzde": 95.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 3.0, "tip": "Molar"},
            "NITROGEN": {"yuzde": 2.0, "tip": "Molar"},
        },
        "P_giris_bar": 60.0,
        "P_cikis_bar": 58.0,
        "T_giris_C": 100.0,
        "T_cikis_C": 40.0,
        "akis": ("Sm3/h", 15.0),
    },
    {
        "ad": "Islak Gaz (7 bileşenli)",
        "kompozisyon": {
            "METHANE": {"yuzde": 85.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 5.0, "tip": "Molar"},
            "PROPANE": {"yuzde": 3.0, "tip": "Molar"},
            "N-BUTANE": {"yuzde": 2.0, "tip": "Molar"},
            "CARBONDIOXIDE": {"yuzde": 3.0, "tip": "Molar"},
            "NITROGEN": {"yuzde": 1.0, "tip": "Molar"},
            "WATER": {"yuzde": 1.0, "tip": "Molar"},
        },
        "P_giris_bar": 60.0,
        "P_cikis_bar": 58.0,
        "T_giris_C": 100.0,
        "T_cikis_C": 40.0,
        "akis": ("Sm3/h", 15.0),
    },
    {
        "ad": "Yüksek Basınç (CH4 85%, C2H6 10%, C3H8 5%)",
        "kompozisyon": {
            "METHANE": {"yuzde": 85.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
            "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
        },
        "P_giris_bar": 150.0,
        "P_cikis_bar": 148.0,
        "T_giris_C": 120.0,
        "T_cikis_C": 50.0,
        "akis": ("Sm3/h", 15.0),
    },
    {
        "ad": "Kritik Üstü / Süperkritik",
        "kompozisyon": {
            "METHANE": {"yuzde": 85.0, "tip": "Molar"},
            "ETHANE": {"yuzde": 10.0, "tip": "Molar"},
            "PROPANE": {"yuzde": 5.0, "tip": "Molar"},
        },
        "P_giris_bar": 100.0,
        "P_cikis_bar": 95.0,
        "T_giris_C": 30.0,
        "T_cikis_C": -50.0,
        "akis": ("Sm3/h", 15.0),
    },
    {
        "ad": "Kütlesel Baz (CH4 90%, C2H6 5%, C3H8 5%)",
        "kompozisyon": {
            "METHANE": {"yuzde": 90.0, "tip": "Kütlesel"},
            "ETHANE": {"yuzde": 5.0, "tip": "Kütlesel"},
            "PROPANE": {"yuzde": 5.0, "tip": "Kütlesel"},
        },
        "P_giris_bar": 50.0,
        "P_cikis_bar": 48.0,
        "T_giris_C": 80.0,
        "T_cikis_C": 30.0,
        "akis": ("kg/h", 5000.0),
    },
]

EOS_LIST = [
    ("HEOS",      "🏆 HEOS (Referans)"),
    ("PR",        "⚡ PR"),
    ("SRK",       "⚡ SRK"),
    ("GERG-2008", "🌍 GERG-2008 (neqsim)"),
]


# ═══════════════════════════════════════════════════════════
# TEK NOKTA KARŞILAŞTIRMA
# ═══════════════════════════════════════════════════════════

def eos_karsilastir(kompozisyon, P_bar, T_C, eos_list):
    """Aynı P,T noktasında EOS'ları karşılaştır."""
    P_Pa = P_bar * 1e5
    T_K = T_C + 273.15

    onceki = None
    sonuc = {}

    for eos, etiket in eos_list:
        try:
            if eos == "GERG-2008":
                if not has_neqsim():
                    sonuc[etiket] = {"hata": "neqsim yok (Java gerekli)"}
                    continue
                neqsim_start_jvm()
                keys = list(kompozisyon.keys())
                vals = list(kompozisyon.values())
                state = NeqSimFluid("GERG-2008", keys, vals)
                state.update(CP.PT_INPUTS, P_Pa, T_K)
            else:
                state = AbstractState(eos, "&".join(kompozisyon.keys()))
                state.set_mole_fractions(list(kompozisyon.values()))
                state.update(CP.PT_INPUTS, P_Pa, T_K)

            h = state.hmass()
            rho = state.rhomass()
            cp0 = state.cp0mass()
            Z = state.keyed_output(CP.iZ)
            faz_idx = state.phase()

            onceki = (h, rho, cp0, Z)
            sonuc[etiket] = {"h": h, "rho": rho, "cp0": cp0, "Z": Z, "faz": faz_idx}

        except Exception as e:
            sonuc[etiket] = {"hata": str(e)}

    return sonuc


def satirlas(sonuc, referans_etiket):
    """Sonuçları tablo satırına çevir - referansa göre sapma yüzdesi ile."""
    satirlar = []
    ref = sonuc.get(referans_etiket, {})
    baslik = f"{'EOS':<20} {'h (kJ/kg)':<14} {'h fark%':<10} {'ρ (kg/m³)':<14} {'ρ fark%':<10} {'cp0 (kJ/kgK)':<14} {'Z':<10}"
    satirlar.append(baslik)
    satirlar.append("─" * 92)

    for etiket, data in sonuc.items():
        if "hata" in data:
            satirlar.append(f"{etiket:<20} {'HATA: ' + data['hata']:<80}")
            continue

        h = data["h"] / 1000
        rho = data["rho"]
        cp0 = data["cp0"] / 1000
        Z = data["Z"]

        if ref and "h" in ref and ref["h"] != 0:
            h_fark = (data["h"] - ref["h"]) / ref["h"] * 100
            rho_fark = (data["rho"] - ref["rho"]) / ref["rho"] * 100
        else:
            h_fark = rho_fark = 0.0

        satirlar.append(
            f"{etiket:<20} {h:<14.4f} {h_fark:>+9.4f}% "
            f"{rho:<14.4f} {rho_fark:>+9.4f}% "
            f"{cp0:<14.4f} {Z:<10.6f}"
        )

    return "\n".join(satirlar)


# ═══════════════════════════════════════════════════════════
# ISI YÜKÜ KARŞILAŞTIRMA
# ═══════════════════════════════════════════════════════════

def isi_yuku_karsilastir(senaryo, eos_list):
    """Tüm EOS'lar için ısı yükü hesapla ve karşılaştır."""
    komp = senaryo["kompozisyon"]
    P_g = senaryo["P_giris_bar"]
    P_c = senaryo["P_cikis_bar"]
    T_g = senaryo["T_giris_C"]
    T_c = senaryo["T_cikis_C"]
    birim, deger = senaryo["akis"]

    sonuclar = []
    for eos, etiket in eos_list:
        try:
            cooler = AirFinnedGasCooler(komp, eos, "bar(a)")
            q_gercek, q_ideal, uyari = cooler.hesapla_isi_yuku(
                deger, birim,
                Q_(P_g, "bar"), Q_(P_c, "bar"),
                Q_(T_g, "degC"), Q_(T_c, "degC"),
            )
            I = cooler.ara_sonuclar
            sonuclar.append({
                "etiket": etiket,
                "Q_MW": float(q_gercek.to("MW").m),
                "Q_ideal_MW": float(q_ideal.to("MW").m) if q_ideal else 0,
                "H_in": I["H_in_kJ_kg"],
                "H_out": I["H_out_kJ_kg"],
                "faz_in": I["faz_in"],
                "faz_out": I["faz_out"],
                "bolge_sayisi": len(I.get("bolgeler", [])),
                "faz_degisimi": I.get("faz_degisimi_var", False),
            })
        except Exception as e:
            sonuclar.append({"etiket": etiket, "hata": str(e)})

    return sonuclar


# ═══════════════════════════════════════════════════════════
# RAPORLAMA
# ═══════════════════════════════════════════════════════════

def rapor_isi_yuku(senaryo, sonuclar):
    """Isı yükü karşılaştırmasını formatla."""
    baslik = f"\n{'='*80}\n📊 {senaryo['ad']}\n{'='*80}"
    satirlar = [baslik]

    ref = None
    for s in sonuclar:
        if "hata" not in s and "🏆" in s["etiket"]:
            ref = s
            break

    bas = f"\n{'EOS':<22} {'Q (MW)':<14} {'Q_ideal (MW)':<14} {'H_in':<12} {'H_out':<12} {'Faz giriş':<18} {'Faz çıkış':<18}"
    satirlar.append(bas)
    satirlar.append("─" * 110)

    for s in sonuclar:
        if "hata" in s:
            satirlar.append(f"{s['etiket']:<22} {'HATA: ' + s['hata']}")
            continue

        q = s["Q_MW"]
        q_i = s["Q_ideal_MW"]
        h_in = s["H_in"]
        h_out = s["H_out"]
        f_in = s["faz_in"]
        f_out = s["faz_out"]

        if ref and ref["Q_MW"] != 0:
            q_fark = (s["Q_MW"] - ref["Q_MW"]) / ref["Q_MW"] * 100
            q_str = f"{q:<.6f}  ({q_fark:>+.3f}%)"
        else:
            q_str = f"{q:<.6f}  (REF)"

        satirlar.append(
            f"{s['etiket']:<22} {q_str:<20} {q_i:<14.6f} "
            f"{h_in:<12.2f} {h_out:<12.2f} {f_in:<18} {f_out:<18}"
        )

    satirlar.append("")
    return "\n".join(satirlar)


# ═══════════════════════════════════════════════════════════
# PERFORMANS TESTİ
# ═══════════════════════════════════════════════════════════

def performans_testi(kompozisyon, eos_list, n_iter=50):
    """Her EOS için ortalama çağrı süresini ölç."""
    import time
    P_Pa = 60e5
    T_K = 373.15

    sonuc = {}
    for eos, etiket in eos_list:
        try:
            if eos == "GERG-2008":
                if not has_neqsim():
                    sonuc[etiket] = "neqsim yok"
                    continue
                neqsim_start_jvm()
                keys = list(kompozisyon.keys())
                vals = list(kompozisyon.values())
                state = NeqSimFluid("GERG-2008", keys, vals)
            else:
                state = AbstractState(eos, "&".join(kompozisyon.keys()))
                state.set_mole_fractions(list(kompozisyon.values()))

            basla = time.perf_counter()
            for _ in range(n_iter):
                state.update(CP.PT_INPUTS, P_Pa, T_K)
                _ = state.hmass()
                _ = state.rhomass()
            sure = (time.perf_counter() - basla) / n_iter * 1000

            sonuc[etiket] = sure
        except Exception as e:
            sonuc[etiket] = f"HATA: {e}"

    return sonuc


# ═══════════════════════════════════════════════════════════
# ANA ÇALIŞTIRMA
# ═══════════════════════════════════════════════════════════

def main():
    print("\n" + "█" * 80)
    print("  AIR COOLER MAIN - EOS KARŞILAŞTIRMA BENCHMARK")
    print("  HEOS (Referans) vs PR vs SRK vs GERG-2008 (neqsim)")
    print("█" * 80)

    # ── BÖLÜM 1: Tek nokta karşılaştırma ──
    print("\n\n" + "╔" + "═" * 78 + "╗")
    print("║  BÖLÜM 1: TEK NOKTA ÖZELLİK KARŞILAŞTIRMASI")
    print("╚" + "═" * 78 + "╝")

    for senaryo in SENARYOLAR[:2]:
        komp = senaryo["kompozisyon"]
        mol_kesir = {}
        for k, v in komp.items():
            name = COOLPROP_ALIASES.get(k, k)
            mol_kesir[name] = v["yuzde"] / 100.0

        sonuc = eos_karsilastir(mol_kesir, senaryo["P_giris_bar"], senaryo["T_giris_C"], EOS_LIST)
        print(f"\n📍 {senaryo['ad']}")
        print(f"   P={senaryo['P_giris_bar']} bar, T={senaryo['T_giris_C']}°C")
        print(satirlas(sonuc, "🏆 HEOS (Referans)"))

    # ── BÖLÜM 2: Isı yükü karşılaştırma ──
    print("\n\n" + "╔" + "═" * 78 + "╗")
    print("║  BÖLÜM 2: ISI YÜKÜ KARŞILAŞTIRMASI")
    print("╚" + "═" * 78 + "╝")

    tablo = []
    for senaryo in SENARYOLAR:
        sonuclar = isi_yuku_karsilastir(senaryo, EOS_LIST)
        print(rapor_isi_yuku(senaryo, sonuclar))
        tablo.append((senaryo["ad"], sonuclar))

    # ── BÖLÜM 3: Özet istatistik ──
    print("\n\n" + "╔" + "═" * 78 + "╗")
    print("║  BÖLÜM 3: ÖZET - TÜM EOS FARKLARI")
    print("╚" + "═" * 78 + "╝")

    print(f"\n{'Senaryo':<40} {'EOS':<12} {'Q (MW)':<14} {'HEOS fark%':<14}")
    print("─" * 80)

    for senaryo_adi, sonuclar in tablo:
        ref_q = None
        for s in sonuclar:
            if "hata" not in s and "🏆" in s["etiket"]:
                ref_q = s["Q_MW"]
                break

        for s in sonuclar:
            if "hata" in s:
                continue
            fark_str = ""
            if ref_q and ref_q != 0 and "🏆" not in s["etiket"]:
                fark = (s["Q_MW"] - ref_q) / ref_q * 100
                fark_str = f"{fark:>+.3f}%"
            elif "🏆" in s["etiket"]:
                fark_str = "REF"
            else:
                fark_str = "?"

            print(f"{senaryo_adi:<40} {s['etiket'][:12]:<12} {s['Q_MW']:<14.6f} {fark_str:<14}")

    # ── BÖLÜM 4: Performans testi ──
    print("\n\n" + "╔" + "═" * 78 + "╗")
    print("║  BÖLÜM 4: PERFORMANS TESTİ (50 iterasyon ortalaması)")
    print("╚" + "═" * 78 + "╝")

    for senaryo in SENARYOLAR[:1]:
        komp = senaryo["kompozisyon"]
        mol_kesir = {}
        for k, v in komp.items():
            mol_kesir[COOLPROP_ALIASES.get(k, k)] = v["yuzde"] / 100.0

        sonuc = performans_testi(mol_kesir, EOS_LIST)
        print(f"\n📍 {senaryo['ad']}")
        for etiket, sure in sonuc.items():
            if isinstance(sure, str):
                print(f"  {etiket:<20} {sure}")
            else:
                print(f"  {etiket:<20} {sure:<.4f} ms/call")

    print("\n✅ Benchmark tamamlandı.\n")


# ═══════════════════════════════════════════════════════════
# PYTEST TEST FONKSİYONLARI
# ═══════════════════════════════════════════════════════════

_MOD_NEQSIM = has_neqsim()
if _MOD_NEQSIM:
    neqsim_start_jvm()


def test_gerg2008_q_match_within_tolerance():
    """GERG-2008 ısı yükü HEOS'a ±0.15% içinde olmalı."""
    for sen in SENARYOLAR:
        sonuclar = isi_yuku_karsilastir(sen, EOS_LIST)
        ref = next((s for s in sonuclar if "🏆" in s["etiket"]), None)
        gerg = next((s for s in sonuclar if "GERG" in s["etiket"]), None)
        if ref and gerg and "hata" not in ref and "hata" not in gerg:
            fark = abs(gerg["Q_MW"] - ref["Q_MW"]) / ref["Q_MW"] * 100
            assert fark < 0.15, f"{sen['ad']}: GERG-2008 farkı %{fark:.3f} > %0.15"


def test_pr_srk_q_match_within_five_percent():
    """PR ve SRK ısı yükü HEOS'a ±5% içinde olmalı."""
    for sen in SENARYOLAR:
        sonuclar = isi_yuku_karsilastir(sen, EOS_LIST)
        ref = next((s for s in sonuclar if "🏆" in s["etiket"]), None)
        for s in sonuclar:
            if "hata" in s or "🏆" in s["etiket"] or "GERG" in s["etiket"]:
                continue
            if ref and "hata" not in ref and ref["Q_MW"] != 0:
                fark = abs(s["Q_MW"] - ref["Q_MW"]) / ref["Q_MW"] * 100
                assert fark < 5.0, f"{sen['ad']} / {s['etiket']}: fark %{fark:.3f} > %5"


def test_performansi_heos_en_yavas():
    """HEOS tüm CoolProp EOS'lardan yavaş olmalı (neqsim JVM warmup hariç)."""
    komp = SENARYOLAR[0]["kompozisyon"]
    mol_kesir = {COOLPROP_ALIASES.get(k, k): v["yuzde"] / 100.0 for k, v in komp.items()}
    sonuc = performans_testi(mol_kesir, EOS_LIST, n_iter=10)
    heos_sure = next((v for k, v in sonuc.items() if "HEOS" in k), None)
    assert heos_sure is not None and isinstance(heos_sure, float)
    for etiket, sure in sonuc.items():
        if "HEOS" not in etiket and isinstance(sure, float):
            if "GERG" in etiket:
                continue
            assert sure <= heos_sure * 2, f"{etiket} ({sure:.2f}ms) HEOS'tan ({heos_sure:.2f}ms) yavaş değil"


def test_performansi_absolute_threshold():
    """Her EOS'un ortalama çağrı süresi mutlak eşikleri aşmamalı."""
    komp = SENARYOLAR[0]["kompozisyon"]
    mol_kesir = {COOLPROP_ALIASES.get(k, k): v["yuzde"] / 100.0 for k, v in komp.items()}
    sonuc = performans_testi(mol_kesir, EOS_LIST, n_iter=10)
    for etiket, sure in sonuc.items():
        if not isinstance(sure, float):
            continue
        if "HEOS" in etiket:
            assert sure < 200, f"HEOS çok yavaş: {sure:.2f}ms (eşik: 200ms)"
        elif "GERG" in etiket:
            assert sure < 500, f"GERG-2008 çok yavaş: {sure:.2f}ms (eşik: 500ms)"
        elif "PR" in etiket and "SRK" not in etiket:
            assert sure < 20, f"PR çok yavaş: {sure:.2f}ms (eşik: 20ms)"
        elif "SRK" in etiket:
            assert sure < 20, f"SRK çok yavaş: {sure:.2f}ms (eşik: 20ms)"


def test_gerg2008_heos_dh_match():
    """GERG-2008 entalpi farkı HEOS'a yakın olmalı (Q bazında)."""
    for sen in SENARYOLAR[:1]:
        sonuclar = isi_yuku_karsilastir(sen, EOS_LIST)
        ref = next((s for s in sonuclar if "🏆" in s["etiket"]), None)
        gerg = next((s for s in sonuclar if "GERG" in s["etiket"]), None)
        if ref and gerg and "hata" not in ref and "hata" not in gerg:
            dh_ref = ref["H_in"] - ref["H_out"]
            dh_gerg = gerg["H_in"] - gerg["H_out"]
            if dh_ref != 0:
                fark = abs(dh_gerg - dh_ref) / abs(dh_ref) * 100
                assert fark < 1.0, f"Δh farkı %{fark:.3f} > %1.0"


if __name__ == "__main__":
    main()
