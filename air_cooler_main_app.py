import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import ht

from air_cooler_main_core import (
    APP_DISPLAY_NAME,
    APP_VERSION,
    DEFAULT_ATM_PRESSURE_PA,
    AmbiguousTwoPhaseInputError,
    AirFinnedGasCooler,
    COOLPROP_COMPONENTS,
    EOS_OPTIONS,
    HeatExchangerSizingError,
    Q_,
    UNITS,
    clean_pressure_unit,
    clean_temp_unit,
    initialize_users_db,
    authenticate_user,
)

APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"
LOCAL_PREFS_SEED = APP_DIR / "air_cooler_main_prefs.json"
TEMPLATES_FILE = APP_DIR / "air_cooler_main_templates.json"
SCHEMATIC_FILE = ASSETS_DIR / "gas_cooler_schematic.svg"
USER_DATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_DISPLAY_NAME
PREFS_FILE = USER_DATA_DIR / "air_cooler_main_prefs.json"
USERS_FILE = USER_DATA_DIR / "air_cooler_users.json"
DEFAULT_PREFS = {"theme": "Otomatik", "hide_release_notes_version": ""}
GLOBAL_CSS = """
    <style>
    [data-testid="stMetric"] {
        border-radius: 18px;
    }
    .ac-card-header {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        margin-bottom: 0.55rem;
    }
    .ac-marker {
        min-width: 2.3rem;
        height: 2.3rem;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 0.95rem;
        color: #ffffff;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.16);
    }
    .ac-card-header.gas-in .ac-marker {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    }
    .ac-card-header.gas-out .ac-marker {
        background: linear-gradient(135deg, #ef4444 0%, #d9465f 100%);
    }
    .ac-card-header.air-in .ac-marker,
    .ac-card-header.air-out .ac-marker {
        background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
    }
    .ac-card-header.design .ac-marker {
        background: linear-gradient(135deg, #334155 0%, #0f172a 100%);
    }
    .ac-card-title {
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.2;
        margin: 0;
    }
    .ac-card-note {
        font-size: 0.82rem;
        opacity: 0.82;
        line-height: 1.35;
        margin-top: 0.12rem;
    }
    .ac-schematic-title {
        font-size: 1.04rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .ac-schematic-note {
        font-size: 0.85rem;
        line-height: 1.45;
        opacity: 0.84;
        margin-top: 0.4rem;
    }
    .ac-inline-tag {
        display: inline-block;
        padding: 0.18rem 0.52rem;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.14);
        font-size: 0.76rem;
        font-weight: 700;
        margin-right: 0.25rem;
        margin-bottom: 0.22rem;
    }
    .ac-spacer-sm {
        height: 1.25rem;
    }
    .ac-spacer-md {
        height: 2.5rem;
    }
    </style>
"""
THEME_CSS = {
    "Açık": """
        <style>
        .stApp { background: linear-gradient(180deg, #f5f7fb 0%, #eef3f9 100%); color: #0f172a; }
        [data-testid="stSidebar"] { background: #ffffff; }
        .stMetric { background: rgba(255, 255, 255, 0.82); border-radius: 16px; }
        </style>
    """,
    "Koyu": """
        <style>
        .stApp { background: linear-gradient(180deg, #0f172a 0%, #111827 100%); color: #e5eef7; }
        [data-testid="stSidebar"] { background: #111827; }
        .stMetric { background: rgba(30, 41, 59, 0.75); border-radius: 16px; }
        </style>
    """,
}

st.set_page_config(
    page_title=f"{APP_DISPLAY_NAME} | Gaz Soğutucu",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "kompozisyon" not in st.session_state:
    st.session_state.kompozisyon = {}
if "P_ATM_PA" not in st.session_state:
    st.session_state.P_ATM_PA = DEFAULT_ATM_PRESSURE_PA
if "log_records" not in st.session_state:
    st.session_state.log_records = []

users_db = initialize_users_db(USERS_FILE)


def log_message(level, message, exception=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level.upper()}] {message}"
    if exception:
        log_entry += f" -> Hata Detayı: {exception}"
    st.session_state.log_records.append(log_entry)


def log_info(message):
    log_message("INFO", message)


def log_warning(message, exception=None):
    log_message("WARNING", message, exception)


def log_error(message, exception=None):
    log_message("ERROR", message, exception)


def load_json(filepath):
    path = Path(filepath)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log_warning(f"JSON okunamadı: {path}", exc)
        return {}


def load_preferences():
    prefs = load_json(PREFS_FILE)
    if prefs:
        return {**DEFAULT_PREFS, **prefs}

    seed = load_json(LOCAL_PREFS_SEED)
    return {**DEFAULT_PREFS, **seed}


def save_preferences(prefs):
    try:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        PREFS_FILE.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log_warning("Tercihler kaydedilemedi.", exc)


def get_theme_preference():
    return load_preferences().get("theme", "Otomatik")


def set_theme_preference(theme):
    prefs = load_preferences()
    if prefs.get("theme") != theme:
        prefs["theme"] = theme
        save_preferences(prefs)
        return True
    return False


def should_show_release_notes():
    return load_preferences().get("hide_release_notes_version", "") != APP_VERSION


def hide_release_notes():
    prefs = load_preferences()
    prefs["hide_release_notes_version"] = APP_VERSION
    save_preferences(prefs)


def apply_theme(theme):
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    css = THEME_CSS.get(theme)
    if css:
        st.markdown(css, unsafe_allow_html=True)


def draw_station_header(marker, title, note, tone):
    st.markdown(
        f"""
        <div class="ac-card-header {tone}">
            <span class="ac-marker">{marker}</span>
            <div>
                <div class="ac-card-title">{title}</div>
                <div class="ac-card-note">{note}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def draw_gas_cooler_schematic():
    with st.container(border=True):
        st.markdown('<div class="ac-schematic-title">Gaz Cooler Yerleşim Şeması</div>', unsafe_allow_html=True)
        if SCHEMATIC_FILE.exists():
            schematic_svg = SCHEMATIC_FILE.read_text(encoding="utf-8").replace(
                "<svg ",
                '<svg style="width: 100%; height: auto;" ',
                1,
            )
            st.markdown(schematic_svg, unsafe_allow_html=True)
        else:
            st.warning("Şema dosyası bulunamadı. assets/gas_cooler_schematic.svg kontrol edilmeli.")

        st.markdown(
            """
            <div class="ac-schematic-note">
                <span class="ac-inline-tag">A1</span> Gaz girişi
                <span class="ac-inline-tag">A2</span> Gaz çıkışı
                <span class="ac-inline-tag">B1</span> Alt hava girişi
                <span class="ac-inline-tag">B2</span> Üst hava çıkışı
                <span class="ac-inline-tag">C1</span> Bundle / UA bölgesi
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Giriş kartları şemadaki A1/A2/B1/B2/C1 işaretlerine göre çevresel olarak yerleştirildi.")


def validate_inputs(flow_v, p_in, p_out, t_in, t_out, t_unit, air_in, air_out, overall_u, correction_factor):
    if not st.session_state.get("kompozisyon"):
        return "Lütfen en az bir gaz bileşeni ekleyin."

    total = sum(v["yuzde"] for v in st.session_state["kompozisyon"].values())
    if abs(total - 100.0) > 0.001:
        return "Bileşenlerin toplamı tam olarak %100.00 olmalıdır."

    if flow_v <= 0:
        return "Debi 0'dan büyük olmalıdır."

    if p_out > p_in:
        return "Çıkış basıncı giriş basıncından yüksek olamaz."

    if t_in <= t_out:
        return "Giriş sıcaklığı çıkış sıcaklığından büyük olmalıdır."

    absolute_zero = {"°C": -273.15, "K": 0.0, "°F": -459.67}[t_unit]
    if t_in < absolute_zero or t_out < absolute_zero or air_in < absolute_zero or air_out < absolute_zero:
        return f"{t_unit} birimi için mutlak sıfırın altına inilemez."

    if air_out <= air_in:
        return "Hava çıkış sıcaklığı hava giriş sıcaklığından büyük olmalıdır."

    if overall_u <= 0:
        return "Genel ısı transfer katsayısı U, 0'dan büyük olmalıdır."

    if correction_factor <= 0 or correction_factor > 1:
        return "LMTD düzeltme faktörü F, 0 ile 1 arasında olmalıdır."

    if (t_in - air_out) <= 0 or (t_out - air_in) <= 0:
        return "Seçilen proses/hava sıcaklıkları LMTD için fiziksel değil. Th,in > Tc,out ve Th,out > Tc,in olmalıdır."

    return None


def draw_sidebar():
    st.sidebar.title(f"🛠️ {APP_DISPLAY_NAME}")
    with st.sidebar.expander("ℹ️ Hakkında & Teknik", expanded=False):
        st.markdown(
            f"**Sürüm:** {APP_VERSION}\n\n"
            "Termodinamik motor: **CoolProp 6.x**\n"
            "Birim yöneticisi: **Pint**\n"
            "Arayüz: **Streamlit**"
        )

    st.sidebar.divider()
    st.sidebar.subheader("🎨 Görünüm")
    current_theme = get_theme_preference()
    theme_options = ["Otomatik", "Açık", "Koyu"]
    theme_idx = theme_options.index(current_theme) if current_theme in theme_options else 0
    selected_theme = st.sidebar.selectbox("Uygulama Teması", theme_options, index=theme_idx)
    if set_theme_preference(selected_theme):
        st.toast(f"Tema tercihi '{selected_theme}' olarak kaydedildi.")
    apply_theme(selected_theme)

    st.sidebar.divider()
    st.sidebar.subheader("🌍 Ortam Koşulları")
    p_atm = st.sidebar.number_input(
        "Atmosfer Basıncı (mbar)",
        min_value=800.0,
        max_value=1100.0,
        value=1013.25,
        step=1.0,
        help="Deniz seviyesi için tipik değer: 1013.25 mbar",
    )
    st.session_state.P_ATM_PA = Q_(p_atm, "mbar").to("pascal").m

    if st.session_state.authenticated:
        st.sidebar.divider()
        st.sidebar.subheader("👤 Kullanıcı")
        st.sidebar.write(f"**Giriş yapan:** {st.session_state.username}")
        st.sidebar.write(f"**Rol:** {st.session_state.role.upper()}")
        if st.sidebar.button("🚪 Çıkış Yap"):
            st.session_state.authenticated = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.rerun()


def draw_zone_analysis(ara):
    bolgeler = ara.get("bolgeler", [])
    cooling_curve = ara.get("cooling_curve", [])
    if not bolgeler:
        return

    with st.expander("🔬 Soğutma Bölge Analizi", expanded=ara.get("faz_degisimi_var", False)):
        st.markdown("Soğutma yükünün faz bölgelerine göre dağılımı aşağıda gösterilmektedir.")

        rows = []
        for bolge in bolgeler:
            rows.append(
                {
                    "Bölge": bolge["bolge_adi"],
                    "T Giriş (°C)": f"{bolge['T_in_C']:.1f}",
                    "T Çıkış (°C)": f"{bolge['T_out_C']:.1f}",
                    "ΔH (kJ/kg)": f"{bolge['H_in_kJ_kg'] - bolge['H_out_kJ_kg']:.1f}",
                    "Q (kW)": f"{bolge['Q_kW']:.2f}",
                    "Q Payı (%)": f"{bolge['Q_frac'] * 100:.1f}%",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if cooling_curve:
            fig = go.Figure()
            temperatures = [point[0] for point in cooling_curve]
            enthalpies = [point[1] for point in cooling_curve]

            for bolge in bolgeler:
                fig.add_vrect(
                    x0=min(bolge["T_out_C"], bolge["T_in_C"]),
                    x1=max(bolge["T_out_C"], bolge["T_in_C"]),
                    fillcolor=bolge["renk"],
                    opacity=0.10,
                    layer="below",
                    line_width=0,
                    annotation_text=bolge["bolge_adi"].split("(")[0].strip(),
                    annotation_position="top left",
                    annotation_font_size=10,
                )

            fig.add_trace(
                go.Scatter(
                    x=temperatures,
                    y=enthalpies,
                    mode="lines+markers",
                    line=dict(color="#2ecc71", width=3),
                    marker=dict(size=4),
                    name="Soğutma Eğrisi",
                )
            )

            fig.update_layout(
                title="T-H Soğutma Eğrisi",
                xaxis_title="Sıcaklık (°C)",
                yaxis_title="Spesifik Entalpi (kJ/kg)",
                height=380,
                hovermode="x unified",
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)


def draw_preliminary_sizing(ara):
    sizing = ara.get("tasarim")
    if not sizing:
        return

    with st.expander("📐 Ön Boyutlandırma (UA / LMTD)", expanded=True):
        st.caption("Karşı-akış eşdeğeri ve kullanıcı tanımlı düzeltme faktörü ile ön alan tahmini")

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        with metric_col1:
            st.metric("LMTD", f"{sizing['lmtd_K']:.2f} K", border=True)
        with metric_col2:
            st.metric("Efektif LMTD", f"{sizing['effective_lmtd_K']:.2f} K", border=True)
        with metric_col3:
            st.metric("Gerekli UA", f"{sizing['ua_required_W_K'] / 1000:.2f} kW/K", border=True)
        with metric_col4:
            st.metric("Gerekli Alan", f"{sizing['required_area_m2']:.2f} m²", border=True)

        detail_col1, detail_col2, detail_col3 = st.columns(3)
        with detail_col1:
            with st.container(border=True):
                st.markdown("**Hava Tarafı**")
                st.write(f"**Hava Giriş:** {sizing['air_in_C']:.2f} °C")
                st.write(f"**Hava Çıkış:** {sizing['air_out_C']:.2f} °C")
                st.write(f"**U:** {sizing['overall_u_W_m2K']:.2f} W/(m²·K)")
                st.write(f"**F:** {sizing['correction_factor']:.3f}")
        with detail_col2:
            with st.container(border=True):
                st.markdown("**Terminal Farklar**")
                st.write(f"**ΔT₁ = Th,in - Tc,out:** {sizing['delta_t_hot_end_K']:.2f} K")
                st.write(f"**ΔT₂ = Th,out - Tc,in:** {sizing['delta_t_cold_end_K']:.2f} K")
                st.write(f"**Minimum Yaklaşım:** {sizing['min_terminal_delta_t_K']:.2f} K")
        with detail_col3:
            with st.container(border=True):
                st.markdown("**Alan Özeti**")
                st.write(f"**UA:** {sizing['ua_required_W_K']:.2f} W/K")
                st.write(f"**Alan:** {sizing['required_area_m2']:.2f} m²")
                st.write("**Varsayım:** karşı-akış eşdeğeri + kullanıcı F faktörü")


def draw_release_notes():
    if not should_show_release_notes():
        return

    @st.dialog(f"🚀 {APP_DISPLAY_NAME} {APP_VERSION} Yenilikleri")
    def show_notes():
        st.markdown(
            """
            ### Main 3.6.0
            - Giriş ekranı, gas cooler şeması etrafına yerleştirilen A1/A2/B1/B2/C1 kartları ile yeniden düzenlendi.
            - Operatör artık proses ve hava verilerini ekipman üzerindeki fiziksel konuma daha yakın şekilde giriyor.
            - Şematik SVG görseli uygulamaya eklendi ve veri giriş bölgeleriyle eşleştirildi.
            - UA / LMTD / gerekli alan ön boyutlandırması korunarak yeni arayüze taşındı.
            """
        )
        if st.button("Anladım"):
            hide_release_notes()
            st.rerun()

    show_notes()


def draw_login_page():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div style='height: 4rem;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center;'>🔐 Gaz Soğutucu Girişi</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; opacity: 0.8;'>Lütfen kullanıcı adı ve şifrenizle giriş yapın.</p>", unsafe_allow_html=True)
            st.divider()
            
            username_input = st.text_input("Kullanıcı Adı", placeholder="admin veya user")
            password_input = st.text_input("Şifre", type="password", placeholder="••••••••")
            
            if st.button("Giriş Yap", type="primary", use_container_width=True):
                success, role = authenticate_user(username_input, password_input, users_db)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.username = username_input.strip()
                    st.session_state.role = role
                    st.success("Giriş başarılı! Yönlendiriliyorsunuz...")
                    st.rerun()
                else:
                    st.error("Hatalı kullanıcı adı veya şifre!")


def draw_advanced_design():
    st.subheader("📐 Gelişmiş 3-Kademeli Tasarım & Değerlendirme")
    st.caption("Doğal gaz karışımları için çapraz akış (cross-flow) modellemesi, Briggs-Young ısı geçişi ve ESDU basınç kaybı hesaplama motoru.")
    
    if not st.session_state.get("kompozisyon"):
        st.warning("⚠️ Akışkan bileşimi henüz girilmedi. Lütfen '⚙️ Girişler' sekmesinden en az bir gaz bileşeni ekleyin.")
        return
        
    total_comp = sum(v["yuzde"] for v in st.session_state.kompozisyon.values())
    if abs(total_comp - 100.0) > 0.01:
        st.warning(f"⚠️ Karışım bileşeni toplamı %{total_comp:.2f}. Hesaplama yapabilmek için toplam tam %100 olmalıdır.")
        return

    # 1. Proses Girdileri (Ortak)
    with st.container(border=True):
        st.markdown("**🔄 Proses İşletme Şartları**")
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        with p_col1:
            adv_t_unit = st.selectbox("Sıcaklık Birimi", UNITS["Sıcaklık"], key="adv_t_u")
        with p_col2:
            adv_p_unit = st.selectbox("Basınç Birimi", UNITS["Basınç"], key="adv_p_u")
        with p_col3:
            adv_flow_u = st.selectbox("Debi Birimi", UNITS["Akış Miktarı"], key="adv_flow_u")
        with p_col4:
            adv_eos_str = st.selectbox("Motor (EOS)", list(EOS_OPTIONS.keys()), key="adv_eos_str")

        p_col5, p_col6, p_col7, p_col8 = st.columns(4)
        with p_col5:
            adv_flow_v = st.number_input("Gaz Debisi", min_value=0.0, value=15.0, key="adv_flow_v")
        with p_col6:
            adv_p_in = st.number_input("Giriş Basıncı", min_value=0.0, value=60.0, key="adv_p_in")
        with p_col7:
            min_temp = {"°C": -273.15, "K": 0.0, "°F": -459.67}[adv_t_unit]
            default_in = 100.0 if adv_t_unit != "K" else 373.15
            adv_t_in = st.number_input("Giriş Sıcaklığı", min_value=min_temp, value=default_in, key="adv_t_in")
        with p_col8:
            default_out = 40.0 if adv_t_unit != "K" else 313.15
            adv_t_out = st.number_input("Çıkış Sıcaklığı (Boyutlandırma için)", min_value=min_temp, value=default_out, key="adv_t_out")
            
        adv_p_out = st.number_input("Çıkış Basıncı", min_value=0.0, value=adv_p_in - 1.0, key="adv_p_out")

    # 2. Mod Seçimi ve Özel Girdiler
    mode = st.radio("Çalışma Modu Seçin", ["Basit Dizayn (Teorik Isı Yükü)", "Detaylı Boyutlandırma (Sizing)", "Eşanjör Değerlendirme (Rating)"], horizontal=True)
    
    if mode == "Basit Dizayn (Teorik Isı Yükü)":
        st.info("ℹ️ **Basit Dizayn Modu:** Bu modülde, girilen doğalgaz karışımının verilen şartlardan çıkış şartlarına soğutulması için gereken teorik ısı geçiş miktarı hesaplanır. Akış tipi **Cross-flow (Çapraz Akış - Karışmayan Akışkanlar)** olarak kabul edilir.")
        
        with st.container(border=True):
            st.markdown("**💨 Hava Tarafı ve Tasarım Parametreleri**")
            b_col1, b_col2, b_col3, b_col4 = st.columns(4)
            with b_col1:
                default_air_in = 25.0 if adv_t_unit != "K" else 298.15
                adv_air_in = st.number_input("Hava Giriş Sıc.", min_value=min_temp, value=default_air_in, key="adv_air_in_b")
            with b_col2:
                default_air_out = 45.0 if adv_t_unit != "K" else 318.15
                adv_air_out = st.number_input("Hava Çıkış Sıc.", min_value=min_temp, value=default_air_out, key="adv_air_out_b")
            with b_col3:
                adv_rows = st.number_input("Tüp Sıra Sayısı", min_value=1, max_value=8, value=4, key="adv_rows_b")
            with b_col4:
                adv_passes = st.number_input("Geçiş Sayısı", min_value=1, max_value=8, value=4, key="adv_passes_b")

        if st.button("🚀 BASİT DİZAYN HESAPLA", type="primary", use_container_width=True):
            if adv_t_in <= adv_t_out:
                st.error("Proses giriş sıcaklığı çıkış sıcaklığından büyük olmalıdır.")
                return
            if adv_air_out <= adv_air_in:
                st.error("Hava çıkış sıcaklığı giriş sıcaklığından büyük olmalıdır.")
                return
            if (adv_t_in - adv_air_out) <= 0 or (adv_t_out - adv_air_in) <= 0:
                st.error("LMTD için sıcaklıklar fiziksel değil! Giriş sıcaklıkları yaklaşım sınırını aşıyor.")
                return
                
            try:
                p_in_q = Q_(adv_p_in, clean_pressure_unit(adv_p_unit))
                p_out_q = Q_(adv_p_out, clean_pressure_unit(adv_p_unit))
                t_in_q = Q_(adv_t_in, clean_temp_unit(adv_t_unit))
                t_out_q = Q_(adv_t_out, clean_temp_unit(adv_t_unit))
                air_in_q = Q_(adv_air_in, clean_temp_unit(adv_t_unit))
                air_out_q = Q_(adv_air_out, clean_temp_unit(adv_t_unit))
                
                cooler = AirFinnedGasCooler(
                    st.session_state.kompozisyon,
                    EOS_OPTIONS[adv_eos_str],
                    adv_p_unit,
                    atmospheric_pressure_pa=st.session_state.P_ATM_PA,
                    logger=log_message,
                )
                
                q_g, q_i, uyari = cooler.hesapla_isi_yuku(
                    adv_flow_v,
                    adv_flow_u,
                    p_in_q,
                    p_out_q,
                    t_in_q,
                    t_out_q,
                    air_sizing_inputs={
                        "air_in_q": air_in_q,
                        "air_out_q": air_out_q,
                        "overall_u_w_m2k": 35.0,
                        "correction_factor": 0.9
                    }
                )
                
                Thi = t_in_q.to("kelvin").m
                Tho = t_out_q.to("kelvin").m
                Tci = air_in_q.to("kelvin").m
                Tco = air_out_q.to("kelvin").m
                Ft = ht.air_cooler.Ft_aircooler(Thi=Thi, Tho=Tho, Tci=Tci, Tco=Tco, Ntp=int(adv_passes), rows=int(adv_rows))
                
                lmtd_val = cooler.ara_sonuclar["tasarim"]["lmtd_K"]
                eff_lmtd = lmtd_val * Ft
                
                st.success("✅ Basit Dizayn Hesaplaması Tamamlandı!")
                
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Gerekli Isı Transfer Yükü", f"{q_g.to('MW').m:.4f} MW", border=True)
                col_m2.metric("LMTD", f"{lmtd_val:.2f} K", border=True)
                col_m3.metric("LMTD Düzeltme Faktörü (F)", f"{Ft:.4f}", border=True)
                
                st.metric("Efektif LMTD (F * LMTD)", f"{eff_lmtd:.2f} K", border=True)
                
                st.info(f"**Faz Durumları:** Giriş Fazı: **{cooler.ara_sonuclar['faz_in']}**, Çıkış Fazı: **{cooler.ara_sonuclar['faz_out']}**")
                
                draw_zone_analysis(cooler.ara_sonuclar)
                
            except Exception as e:
                st.error(f"Hesaplama hatası: {e}")
                log_error("Basit dizayn hesaplama hatası.", e)

    elif mode == "Detaylı Boyutlandırma (Sizing)":
        st.info("📐 **Detaylı Boyutlandırma Modu:** Bu modülde, proses debisini soğutmak için gerekli olan fiziksel alan, boru içi/hava tarafı film ısı iletim katsayıları ($h_i, h_o$), fin verimliliği, toplam ısı iletim katsayısı ($U$), gerekli hava debisi ve fan güç gereksinimleri standart geometrik parametrelere göre hesaplanır.")
        
        with st.container(border=True):
            st.markdown("**📐 Eşanjör Geometrisi & Finli Boru Girdileri**")
            g_col1, g_col2, g_col3, g_col4 = st.columns(4)
            with g_col1:
                tube_od = st.number_input("Boru Dış Çapı (mm)", min_value=5.0, max_value=100.0, value=25.4, help="API 661 standardı için minimum 25.4 mm (1 inç) veya 20 mm önerilir.")
                tube_thick = st.number_input("Boru Duvar Kalınlığı (mm)", min_value=0.5, max_value=10.0, value=2.11, help="14 BWG standardı: 2.11 mm")
            with g_col2:
                tube_len = st.number_input("Boru Boyu (m)", min_value=1.0, max_value=24.0, value=6.0)
                tubes_per_row = st.number_input("Sıra Başına Boru Sayısı", min_value=5, max_value=200, value=24)
            with g_col3:
                tube_rows = st.number_input("Boru Sıra Sayısı", min_value=1, max_value=12, value=4, key="rows_size")
                tube_passes = st.number_input("Akış Geçiş Sayısı", min_value=1, max_value=12, value=4, key="passes_size")
            with g_col4:
                layout_angle = st.selectbox("Dizilim Açısı", [30, 90], format_func=lambda x: "30° (Üçgen)" if x == 30 else "90° (Kare)")
                pitch_normal = st.number_input("Boru Eksene Adımı (mm)", min_value=10.0, max_value=200.0, value=63.5, help="Tüplerin merkezleri arasındaki mesafe. 2.5 inç standardı: 63.5 mm")

            g_col5, g_col6, g_col7, g_col8 = st.columns(4)
            with g_col5:
                fin_height = st.number_input("Kanatçık Yüksekliği (mm)", min_value=2.0, max_value=50.0, value=15.9, help="0.625 inç standardı: 15.9 mm")
                fin_thick = st.number_input("Kanatçık Kalınlığı (mm)", min_value=0.1, max_value=5.0, value=0.4)
            with g_col6:
                fin_fpi = st.number_input("İnç Başına Kanatçık (FPI)", min_value=2.0, max_value=30.0, value=10.0)
            with g_col7:
                tube_mat = st.selectbox("Boru Malzemesi (İletkenlik)", ["Karbon Çelik (50 W/mK)", "Paslanmaz Çelik (15 W/mK)", "Bakır (385 W/mK)"])
                fin_mat = st.selectbox("Kanatçık Malzemesi (İletkenlik)", ["Alüminyum (205 W/mK)", "Bakır (385 W/mK)"])
            with g_col8:
                fouling_in = st.number_input("Boru İçi Kirlenme (m²K/W)", min_value=0.0, value=0.000176, format="%.6f", help="TEMA standardı doğalgaz kirlenme katsayısı: 0.000176")
                fouling_out = st.number_input("Hava Kirlenme Katsayısı (m²K/W)", min_value=0.0, value=0.000088, format="%.6f")

            g_col9, g_col10, g_col11 = st.columns(3)
            with g_col9:
                fan_eff = st.number_input("Fan Toplam Verimi (%)", min_value=10.0, max_value=100.0, value=65.0) / 100.0
            with g_col10:
                default_air_in_s = 25.0 if adv_t_unit != "K" else 298.15
                air_in_s = st.number_input("Tasarım Hava Giriş Sıcaklığı", min_value=min_temp, value=default_air_in_s, key="air_in_s")
            with g_col11:
                default_air_out_s = 45.0 if adv_t_unit != "K" else 318.15
                air_out_s = st.number_input("Tasarım Hava Çıkış Sıcaklığı", min_value=min_temp, value=default_air_out_s, key="air_out_s")

        if st.button("🚀 BOYUTLANDIRMA HESAPLA", type="primary", use_container_width=True):
            if adv_t_in <= adv_t_out:
                st.error("Proses giriş sıcaklığı çıkış sıcaklığından büyük olmalıdır.")
                return
            if air_out_s <= air_in_s:
                st.error("Hava çıkış sıcaklığı giriş sıcaklığından büyük olmalıdır.")
                return
                
            try:
                k_tube = 50.0 if "Karbon" in tube_mat else (15.0 if "Paslanmaz" in tube_mat else 385.0)
                k_fin = 205.0 if "Alüminyum" in fin_mat else 385.0
                
                geom_params = {
                    "tube_rows": int(tube_rows),
                    "tube_passes": int(tube_passes),
                    "tubes_per_row": int(tubes_per_row),
                    "tube_length": float(tube_len),
                    "tube_od": float(tube_od / 1000.0),
                    "tube_thickness": float(tube_thick / 1000.0),
                    "fin_height": float(fin_height / 1000.0),
                    "fin_thickness": float(fin_thick / 1000.0),
                    "fin_density": float(fin_fpi * 39.37),
                    "pitch": float(pitch_normal / 1000.0),
                    "angle": float(layout_angle),
                    "tube_k": k_tube,
                    "fin_k": k_fin,
                    "fouling_in": fouling_in,
                    "fouling_out": fouling_out,
                    "fan_efficiency": fan_eff
                }
                
                cooler = AirFinnedGasCooler(
                    st.session_state.kompozisyon,
                    EOS_OPTIONS[adv_eos_str],
                    adv_p_unit,
                    atmospheric_pressure_pa=st.session_state.P_ATM_PA,
                    logger=log_message,
                )
                
                p_in_q = Q_(adv_p_in, clean_pressure_unit(adv_p_unit))
                p_out_q = Q_(adv_p_out, clean_pressure_unit(adv_p_unit))
                t_in_q = Q_(adv_t_in, clean_temp_unit(adv_t_unit))
                t_out_q = Q_(adv_t_out, clean_temp_unit(adv_t_unit))
                air_in_q = Q_(air_in_s, clean_temp_unit(adv_t_unit))
                air_out_q = Q_(air_out_s, clean_temp_unit(adv_t_unit))
                
                res = cooler.hesapla_detayli_dizayn(
                    m_dot_val=adv_flow_v,
                    m_dot_unit=adv_flow_u,
                    P_in_Q=p_in_q,
                    P_out_Q=p_out_q,
                    T_in_Q=t_in_q,
                    T_out_Q=t_out_q,
                    air_in_Q=air_in_q,
                    air_out_Q=air_out_q,
                    geom_params=geom_params
                )
                
                st.success("✅ Detaylı Boyutlandırma Hesaplaması Tamamlandı!")
                
                m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                m_col1.metric("Toplam Yük (Q)", f"{res['Q_kW'] / 1000.0:.4f} MW", border=True)
                m_col2.metric("Toplam Eşanjör Alanı", f"{res['actual_area_m2']:.2f} m²", border=True)
                m_col3.metric("Gerekli Alan", f"{res['required_area_m2']:.2f} m²", border=True)
                m_col4.metric("Overdesign %", f"{res['overdesign_pct']:.2f} %", border=True)
                
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    with st.container(border=True):
                        st.markdown("**🔬 Isı Geçiş Performansı & Dirençler**")
                        st.write(f"**U Katsayısı (Toplam):** {res['U_W_m2K']:.2f} W/(m²·K)")
                        st.write(f"**Boru İçi Film Katsayısı (hi):** {res['h_inside_W_m2K']:.2f} W/(m²·K)")
                        st.write(f"**Dış Film Katsayısı (ho - fin dahil):** {res['h_outside_actual_W_m2K']:.2f} W/(m²·K)")
                        st.write(f"**Kanatçık Verimi (Fin Efficiency):** {res['fin_efficiency'] * 100:.2f} %")
                        st.write(f"**Yüzey Verimi (Surface Efficiency):** {res['surface_efficiency'] * 100:.2f} %")
                        st.write(f"**LMTD / Ft Faktörü:** {res['lmtd_K']:.2f} K / {res['Ft']:.4f}")
                with d_col2:
                    with st.container(border=True):
                        st.markdown("**💨 Hava Tarafı & Fan Güç Hesapları**")
                        st.write(f"**Gerekli Hava Debisi:** {res['m_dot_air_kg_s']:.2f} kg/s ({res['V_air_m3_h']:.2f} m³/h)")
                        st.write(f"**Hava Basınç Kaybı (ESDU):** {res['dP_air_Pa']:.2f} Pa")
                        st.write(f"**Tahmini Fan Şaft Gücü:** {res['fan_power_kW']:.2f} kW")
                        st.write(f"**Boru İçi Gaz Akış Hızı:** {res['gas_velocity_m_s']:.2f} m/s")
                        st.write(f"**Boru İçi Gaz Reynolds:** {res['gas_Re']:.0f}")
                        st.write(f"**Gaz Tarafı Basınç Düşümü (Friction):** {res['gas_dP_bar']:.4f} bar")
                        
                if res['gas_velocity_m_s'] > 20.0:
                    st.warning("⚠️ **Gürültü ve Erozyon Riski!** Boru içi gaz hızı 20 m/s sınırının üzerinde. Akış alanını artırmak için paralel tüp sayısını artırmayı düşünebilirsiniz.")
                elif res['gas_velocity_m_s'] < 1.0:
                    st.warning("⚠️ **Kirlenme (Fouling) Riski!** Boru içi akış hızı 1.0 m/s sınırının altında. Geçiş sayısını artırarak hızı yükseltmeyi düşünebilirsiniz.")
                else:
                    st.success("✅ **Hız Sınırları Uyumlu:** Gaz hızları API 661 erozyon ve kirlenme limitleri içerisinde.")
                    
            except Exception as e:
                st.error(f"Hesaplama hatası: {e}")
                log_error("Detaylı boyutlandırma hesaplama hatası.", e)

    elif mode == "Eşanjör Değerlendirme (Rating)":
        st.info("🔍 **Eşanjör Değerlendirme Modu:** Bu modülde, var olan fiziksel bir hava soğutmalı soğutucunun verilerini ve fan hava debisini girerek, proses gazının giriş sıcaklığından itibaren ulaşılabilecek verimi (effectiveness), gaz çıkış sıcaklığını ve basınç düşümlerini hesaplarsınız.")
        
        with st.container(border=True):
            st.markdown("**🔍 Mevcut Eşanjörün Geometrik Özellikleri**")
            r_col1, r_col2, r_col3, r_col4 = st.columns(4)
            with r_col1:
                r_tube_od = st.number_input("Boru Dış Çapı (mm)", min_value=5.0, max_value=100.0, value=25.4, key="r_od")
                r_tube_thick = st.number_input("Boru Duvar Kalınlığı (mm)", min_value=0.5, max_value=10.0, value=2.11, key="r_thick")
            with r_col2:
                r_tube_len = st.number_input("Boru Boyu (m)", min_value=1.0, max_value=24.0, value=6.0, key="r_len")
                r_tubes_per_row = st.number_input("Sıra Başına Boru Sayısı", min_value=5, max_value=200, value=24, key="r_tubes")
            with r_col3:
                r_tube_rows = st.number_input("Boru Sıra Sayısı", min_value=1, max_value=12, value=4, key="rows_rating")
                r_tube_passes = st.number_input("Akış Geçiş Sayısı", min_value=1, max_value=12, value=4, key="passes_rating")
            with r_col4:
                r_layout_angle = st.selectbox("Dizilim Açısı", [30, 90], format_func=lambda x: "30° (Üçgen)" if x == 30 else "90° (Kare)", key="r_angle")
                r_pitch_normal = st.number_input("Boru Eksene Adımı (mm)", min_value=10.0, max_value=200.0, value=63.5, key="r_pitch")

            r_col5, r_col6, r_col7, r_col8 = st.columns(4)
            with r_col5:
                r_fin_height = st.number_input("Kanatçık Yüksekliği (mm)", min_value=2.0, max_value=50.0, value=15.9, key="r_fin_h")
                r_fin_thick = st.number_input("Kanatçık Kalınlığı (mm)", min_value=0.1, max_value=5.0, value=0.4, key="r_fin_t")
            with r_col6:
                r_fin_fpi = st.number_input("İnç Başına Kanatçık (FPI)", min_value=2.0, max_value=30.0, value=10.0, key="r_fpi")
            with r_col7:
                r_tube_mat = st.selectbox("Boru Malzemesi (İletkenlik)", ["Karbon Çelik (50 W/mK)", "Paslanmaz Çelik (15 W/mK)", "Bakır (385 W/mK)"], key="r_tmat")
                r_fin_mat = st.selectbox("Kanatçık Malzemesi (İletkenlik)", ["Alüminyum (205 W/mK)", "Bakır (385 W/mK)"], key="r_fmat")
            with r_col8:
                r_fouling_in = st.number_input("Boru İçi Kirlenme (m²K/W)", min_value=0.0, value=0.000176, format="%.6f", key="r_fi")
                r_fouling_out = st.number_input("Hava Kirlenme Katsayısı (m²K/W)", min_value=0.0, value=0.000088, format="%.6f", key="r_fo")

            st.markdown("**💨 İşletme Hava & Fan Parametreleri**")
            r_col9, r_col10 = st.columns(2)
            with r_col9:
                r_air_in = st.number_input("Mevcut Hava Giriş Sıcaklığı", min_value=min_temp, value=25.0 if adv_t_unit != "K" else 298.15, key="r_air_in")
            with r_col10:
                r_fan_flow = st.number_input("Mevcut Fan Volumetrik Hava Akışı (m³/h)", min_value=100.0, value=150000.0, key="r_fan_flow")

        if st.button("🚀 MEVCUT DURUM DEĞERLENDİR", type="primary", use_container_width=True):
            try:
                k_tube = 50.0 if "Karbon" in r_tube_mat else (15.0 if "Paslanmaz" in r_tube_mat else 385.0)
                k_fin = 205.0 if "Alüminyum" in r_fin_mat else 385.0
                
                geom_params = {
                    "tube_rows": int(r_tube_rows),
                    "tube_passes": int(r_tube_passes),
                    "tubes_per_row": int(r_tubes_per_row),
                    "tube_length": float(r_tube_len),
                    "tube_od": float(r_tube_od / 1000.0),
                    "tube_thickness": float(r_tube_thick / 1000.0),
                    "fin_height": float(r_fin_height / 1000.0),
                    "fin_thickness": float(r_fin_thick / 1000.0),
                    "fin_density": float(r_fin_fpi * 39.37),
                    "pitch": float(r_pitch_normal / 1000.0),
                    "angle": float(r_layout_angle),
                    "tube_k": k_tube,
                    "fin_k": k_fin,
                    "fouling_in": r_fouling_in,
                    "fouling_out": r_fouling_out
                }
                
                cooler = AirFinnedGasCooler(
                    st.session_state.kompozisyon,
                    EOS_OPTIONS[adv_eos_str],
                    adv_p_unit,
                    atmospheric_pressure_pa=st.session_state.P_ATM_PA,
                    logger=log_message,
                )
                
                p_in_q = Q_(adv_p_in, clean_pressure_unit(adv_p_unit))
                p_out_q = Q_(adv_p_out, clean_pressure_unit(adv_p_unit))
                t_in_q = Q_(adv_t_in, clean_temp_unit(adv_t_unit))
                air_in_q = Q_(r_air_in, clean_temp_unit(adv_t_unit))
                
                res = cooler.hesapla_degerlendirme_rating(
                    m_dot_val=adv_flow_v,
                    m_dot_unit=adv_flow_u,
                    P_in_Q=p_in_q,
                    P_out_Q=p_out_q,
                    T_in_Q=t_in_q,
                    air_in_Q=air_in_q,
                    V_air_m3_h=r_fan_flow,
                    geom_params=geom_params
                )
                
                st.success("✅ Eşanjör Performans Değerlendirmesi Tamamlandı!")
                
                rc_1, rc_2, rc_3 = st.columns(3)
                rc_1.metric("Gerçek Isı Aktarımı (Q)", f"{res['Q_kW'] / 1000.0:.4f} MW", border=True)
                rc_2.metric("Gaz Çıkış Sıcaklığı", f"{res['T_gas_out_C']:.2f} °C", border=True)
                rc_3.metric("Hava Çıkış Sıcaklığı", f"{res['T_air_out_C']:.2f} °C", border=True)
                
                rc_4, rc_5 = st.columns(2)
                with rc_4:
                    with st.container(border=True):
                        st.markdown("**🔬 Isı Değiştirici Etkinliği**")
                        st.write(f"**Isı Değiştirici Verimi (Effectiveness):** {res['effectiveness'] * 100:.2f} %")
                        st.write(f"**Transfer Ünitesi Sayısı (NTU):** {res['NTU']:.4f}")
                        st.write(f"**Toplam U Katsayısı:** {res['U_W_m2K']:.2f} W/(m²·K)")
                        st.write(f"**Boru İçi Film Katsayısı (hi):** {res['h_inside_W_m2K']:.2f} W/(m²·K)")
                        st.write(f"**Dış Film Katsayısı (ho):** {res['h_outside_actual_W_m2K']:.2f} W/(m²·K)")
                with rc_5:
                    with st.container(border=True):
                        st.markdown("**⚙️ Basınç Kayıpları & Akış Limiti**")
                        st.write(f"**Boru İçi Hız:** {res['gas_velocity_m_s']:.2f} m/s")
                        st.write(f"**Gaz Tarafı Basınç Düşümü (Friction):** {res['gas_dP_bar']:.4f} bar")
                        st.write(f"**Hava Tarafı Basınç Düşümü (ESDU):** {res['dP_air_Pa']:.2f} Pa")
                        st.write(f"**Çıkış Gaz Faz Durumu:** **{res['gas_out_phase']}**")
                        
            except Exception as e:
                st.error(f"Değerlendirme hatası: {e}")
                log_error("Değerlendirme hesaplama hatası.", e)

def draw_main():
    st.title(f"🌡️ {APP_DISPLAY_NAME} | Gaz Soğutucu Termal Yük Hesaplayıcı")
    st.caption("Doğal gaz ve hidrokarbon karışımları için termal yük ve ön boyutlandırma tahmini")
    draw_release_notes()

    role = st.session_state.get("role", "user")
    if role == "admin":
        tab_inputs, tab_report, tab_new_design, tab_logs = st.tabs(["⚙️ Girişler", "📊 Rapor", "📐 Gelişmiş Boyutlandırma", "📜 Kayıtlar"])
    else:
        tab_inputs, tab_report, tab_logs = st.tabs(["⚙️ Girişler", "📊 Rapor", "📜 Kayıtlar"])
        tab_new_design = None

    with tab_inputs:
        st.header("1. Akışkan Bileşimi")
        templates = load_json(TEMPLATES_FILE)
        if templates:
            with st.container(border=True):
                st.markdown("**📝 Hazır Şablonlar**")
                temp_col1, temp_col2 = st.columns([3, 1])
                with temp_col1:
                    selected_template = st.selectbox(
                        "Bir şablon seçin",
                        ["---"] + list(templates.keys()),
                        label_visibility="collapsed",
                    )
                with temp_col2:
                    if st.button("Uygula", use_container_width=True) and selected_template != "---":
                        st.session_state.kompozisyon = templates[selected_template].copy()
                        log_info(f"Şablon uygulandı: {selected_template}")
                        st.rerun()

        with st.container(border=True):
            st.markdown("**🧪 Karışım Ekle**")
            comp_col1, comp_col2, comp_col3 = st.columns([5, 3, 4])
            with comp_col1:
                b_name = st.selectbox(
                    "Bileşen",
                    list(COOLPROP_COMPONENTS.keys()),
                    format_func=lambda x: COOLPROP_COMPONENTS[x],
                    label_visibility="collapsed",
                )
            with comp_col2:
                b_val = st.number_input("Yüzde", 0.0, 100.0, 0.0, 0.1, label_visibility="collapsed")
            with comp_col3:
                b_tip = st.radio("Tip", ["Molar", "Kütlesel"], horizontal=True, label_visibility="collapsed")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("➕ Ekle", use_container_width=True):
                    if b_val > 0:
                        if st.session_state.kompozisyon and list(st.session_state.kompozisyon.values())[0]["tip"] != b_tip:
                            st.error("Karışık tipler kullanılamaz.")
                        else:
                            st.session_state.kompozisyon[b_name] = {"yuzde": b_val, "tip": b_tip}
                            st.rerun()
            with btn_col2:
                if st.button("🧹 Tümünü Temizle", use_container_width=True):
                    st.session_state.kompozisyon = {}
                    st.rerun()

        if st.session_state.get("kompozisyon"):
            with st.container(border=True):
                st.markdown("**Mevcut Karışım**")
                for key in list(st.session_state.kompozisyon.keys()):
                    val = st.session_state.kompozisyon[key]
                    row1, row2, row3, row4 = st.columns([4, 2, 2, 1])
                    row1.write(f"🧪 {COOLPROP_COMPONENTS[key]}")
                    row2.write(f"% {val['yuzde']:.2f}")
                    row3.write(val["tip"])
                    if row4.button("❌", key=f"del_{key}", help=f"{COOLPROP_COMPONENTS[key]} sil"):
                        del st.session_state.kompozisyon[key]
                        st.rerun()

            total = sum(v["yuzde"] for v in st.session_state.kompozisyon.values())
            tip = list(st.session_state.kompozisyon.values())[0]["tip"]
            if abs(total - 100.0) > 0.001:
                st.error(f"⚠️ Toplam: %{total:.2f} (Tam %100 olmalıdır.)")
            else:
                st.success(f"✅ Toplam: %100.00 ({tip})")

        st.divider()
        st.header("2. Şema Üzerinden Veri Girişi")
        st.caption("Kartlar gas cooler çizimindeki fiziksel bölgelere göre konumlandırıldı. A1/A2 proses, B1/B2 hava, C1 ise bundle ve UA girdilerini temsil eder.")

        layout_left, layout_mid, layout_right = st.columns([1.05, 1.35, 1.05], gap="medium")

        with layout_left:
            with st.container(border=True):
                draw_station_header("A1", "Gaz Girişi", "Debi, giriş basıncı ve giriş sıcaklığı", "gas-in")
                flow_col1, flow_col2 = st.columns([2, 1])
                with flow_col1:
                    flow_v = st.number_input("Debi", min_value=0.0, value=15.0, key="ui_flow")
                with flow_col2:
                    flow_u = st.selectbox("Birim", UNITS["Akış Miktarı"], key="ui_flow_u")

                p_unit = st.selectbox("Basınç Birimi", UNITS["Basınç"], key="ui_p_u")
                p_in = st.number_input("Giriş Basıncı", min_value=0.0, value=60.0, format="%.2f")

                t_unit = st.selectbox("Sıcaklık Birimi", UNITS["Sıcaklık"], key="ui_t_u")
                min_temp = {"°C": -273.15, "K": 0.0, "°F": -459.67}[t_unit]
                default_in = 107.0 if t_unit != "K" else 380.15
                default_out = 37.0 if t_unit != "K" else 310.15
                t_in = st.number_input("Giriş Sıc.", min_value=min_temp, value=default_in, format="%.2f")

            st.markdown('<div class="ac-spacer-md"></div>', unsafe_allow_html=True)

            if t_unit == "K":
                default_air_in = 298.15
                default_air_out = 318.15
            elif t_unit == "°F":
                default_air_in = 77.0
                default_air_out = 113.0
            else:
                default_air_in = 25.0
                default_air_out = 45.0

            with st.container(border=True):
                draw_station_header("B1", "Alt Hava Girişi", "Fan altından bundle içine giren hava", "air-in")
                air_in = st.number_input("Hava Giriş Sıc.", min_value=min_temp, value=default_air_in, format="%.2f")

        with layout_mid:
            draw_gas_cooler_schematic()

        with layout_right:
            with st.container(border=True):
                draw_station_header("A2", "Gaz Çıkışı", "Hedef proses çıkış basıncı ve sıcaklığı", "gas-out")
                p_out = st.number_input(
                    "Çıkış Basıncı",
                    min_value=0.0,
                    value=p_in,
                    format="%.2f",
                    help="Bilinmiyorsa giriş ile aynı bırakın.",
                )
                t_out = st.number_input("Çıkış Sıc.", min_value=min_temp, value=default_out, format="%.2f")

            with st.container(border=True):
                draw_station_header("C1", "Bundle / UA", "EOS seçimi ve ön boyutlandırma parametreleri", "design")
                eos_str = st.selectbox("Motor (Equation of State)", list(EOS_OPTIONS.keys()))
                overall_u = st.number_input(
                    "Genel U [W/(m²·K)]",
                    min_value=1.0,
                    value=35.0,
                    step=1.0,
                    help="Finned air cooler için kullanıcı tanımlı ön toplam ısı transfer katsayısı.",
                )
                correction_factor = st.number_input(
                    "LMTD Düzeltme Faktörü F",
                    min_value=0.10,
                    max_value=1.00,
                    value=0.90,
                    step=0.01,
                    format="%.2f",
                    help="Karşı-akış eşdeğeri LMTD üzerine uygulanan düzeltme faktörü.",
                )

            st.markdown('<div class="ac-spacer-sm"></div>', unsafe_allow_html=True)

            with st.container(border=True):
                draw_station_header("B2", "Üst Hava Çıkışı", "Bundle üzerinden ısınarak çıkan hava", "air-out")
                air_out = st.number_input("Hava Çıkış Sıc.", min_value=min_temp, value=default_air_out, format="%.2f")

        btn_col1, btn_col2, btn_col3 = st.columns([1, 1.2, 1])
        with btn_col2:
            if st.button("🚀 HESAPLA", use_container_width=True, type="primary"):
                validation_error = validate_inputs(
                    flow_v,
                    p_in,
                    p_out,
                    t_in,
                    t_out,
                    t_unit,
                    air_in,
                    air_out,
                    overall_u,
                    correction_factor,
                )
                if validation_error:
                    st.error(validation_error)
                else:
                    try:
                        p_in_q = Q_(p_in, clean_pressure_unit(p_unit))
                        p_out_q = Q_(p_out, clean_pressure_unit(p_unit))
                        t_in_q = Q_(t_in, clean_temp_unit(t_unit))
                        t_out_q = Q_(t_out, clean_temp_unit(t_unit))
                        air_in_q = Q_(air_in, clean_temp_unit(t_unit))
                        air_out_q = Q_(air_out, clean_temp_unit(t_unit))
                        cooler = AirFinnedGasCooler(
                            st.session_state.kompozisyon,
                            EOS_OPTIONS[eos_str],
                            p_unit,
                            atmospheric_pressure_pa=st.session_state.P_ATM_PA,
                            logger=log_message,
                        )
                        q_g, q_i, uyari = cooler.hesapla_isi_yuku(
                            flow_v,
                            flow_u,
                            p_in_q,
                            p_out_q,
                            t_in_q,
                            t_out_q,
                            air_sizing_inputs={
                                "air_in_q": air_in_q,
                                "air_out_q": air_out_q,
                                "overall_u_w_m2k": overall_u,
                                "correction_factor": correction_factor,
                            },
                        )
                        st.session_state.last_res = {
                            "q_g": q_g,
                            "q_i": q_i,
                            "uyari": uyari,
                            "ara": cooler.ara_sonuclar,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "eos": eos_str,
                        }
                        st.success(f"Hesaplama tamamlandı ({st.session_state.last_res['time']})")
                    except AmbiguousTwoPhaseInputError as exc:
                        st.error(str(exc))
                        log_warning("Belirsiz iki faz P-T girişi engellendi.", exc)
                    except HeatExchangerSizingError as exc:
                        st.error(str(exc))
                        log_warning("UA/LMTD ön boyutlandırma girdisi reddedildi.", exc)
                    except Exception as exc:
                        st.error(f"Hata: {exc}")
                        log_error("Hesaplama çöktü.", exc)

    with tab_report:
        result = st.session_state.get("last_res")
        if not result:
            st.info("Lütfen Girişler sekmesinden hesaplama işlemini başlatın.", icon="ℹ️")
        else:
            st.header(f"✅ Rapor ({result['time']})")
            if result["uyari"]:
                st.warning(result["uyari"], icon="⚠️")

            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric("Gerçek Gaz Soğutma Yükü", f"{result['q_g'].to('MW').m:.4f} MW", border=True)
            with metric_col2:
                if result["q_i"] is not None:
                    st.metric("İdeal Gaz Yükü (Referans)", f"{result['q_i'].to('MW').m:.4f} MW", border=True)
                else:
                    st.metric("İdeal Gaz Yükü (Referans)", "Hesaplanamadı", border=True)
            with metric_col3:
                if result["q_i"] is not None and abs(result["q_g"].m) > 1e-12:
                    diff = abs(result["q_g"].m - result["q_i"].m) / abs(result["q_g"].m) * 100.0
                    st.metric("Sapma (Gerçek vs İdeal)", f"% {diff:.2f}", border=True)
                else:
                    st.metric("Sapma (Gerçek vs İdeal)", "-", border=True)

            st.divider()
            draw_zone_analysis(result["ara"])

            st.divider()
            draw_preliminary_sizing(result["ara"])

            st.divider()
            st.subheader("🔍 Detaylı Termodinamik Veriler")
            ara = result["ara"]
            detail_col1, detail_col2, detail_col3 = st.columns(3)
            with detail_col1:
                with st.container(border=True):
                    st.markdown("**📥 Giriş Koşulları**")
                    st.write(f"**Faz:** {ara['faz_in']}")
                    st.write(f"**Basınç:** {ara['P_in_Pa'] / 1e5:.2f} bar(a)")
                    st.write(f"**Sıcaklık:** {ara['T_in_K'] - 273.15:.2f} °C")
                    st.write(f"**Yoğunluk:** {ara['rho_in']:.2f} kg/m³")
                    st.write(f"**Sp. Entalpi:** {ara['H_in_kJ_kg']:.2f} kJ/kg")
            with detail_col2:
                with st.container(border=True):
                    st.markdown("**📤 Çıkış Koşulları**")
                    st.write(f"**Faz:** {ara['faz_out']}")
                    st.write(f"**Basınç:** {ara['P_out_Pa'] / 1e5:.2f} bar(a)")
                    st.write(f"**Sıcaklık:** {ara['T_out_K'] - 273.15:.2f} °C")
                    st.write(f"**Yoğunluk:** {ara['rho_out']:.2f} kg/m³")
                    st.write(f"**Sp. Entalpi:** {ara['H_out_kJ_kg']:.2f} kJ/kg")
            with detail_col3:
                with st.container(border=True):
                    st.markdown("**⚙️ Akış Parametreleri**")
                    st.write(f"**Kütlesel Debi:** {ara['m_dot_kg_s']:.4f} kg/s")
                    st.write(f"**Basınç Düşümü (ΔP):** {ara['delta_P_bar']:.2f} bar")
                    st.write(f"**Kullanılan Motor:** {result['eos']}")
                    if "Cp_ideal" in ara:
                        st.write(f"**İdeal Gaz Cp0:** {ara['Cp_ideal']:.3f} kJ/(kg·K)")
    if tab_new_design is not None:
        with tab_new_design:
            draw_advanced_design()

    with tab_logs:
        if st.session_state.log_records:
            st.code("\n".join(st.session_state.log_records[-100:]))
        else:
            st.write("Kayıt yok.")


if __name__ == "__main__":
    apply_theme(get_theme_preference())
    if st.session_state.authenticated:
        draw_sidebar()
        draw_main()
    else:
        draw_login_page()
