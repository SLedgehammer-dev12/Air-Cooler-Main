import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import ht

from air_cooler_export import export_excel, export_pdf, save_project, list_projects, delete_project_file, load_project_filepath

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
    ENGINE_EOS,
    get_engine_keys,
    get_eos_options,
    resolve_engine_eos,
    clean_pressure_unit,
    clean_temp_unit,
    initialize_users_db,
    authenticate_user,
    assess_eos_risk,
    recommend_eos,
    get_fallback_eos,
    EOS_RISK_RULES,
    fin_type_temperature_limit_C,
    required_tube_wall_with_ca,
    TUBE_MATERIAL_GRADES,
)
from air_cooler_users import (
    register_user,
    delete_user as auth_delete_user,
    update_user_role,
    list_users as auth_list_users,
    update_last_login,
    change_password,
    is_default_password,
    validate_password as validate_user_password,
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

def update_composition_pct():
    for key in list(st.session_state.kompozisyon.keys()):
        pct_key = f"pct_{key}"
        if pct_key in st.session_state:
            st.session_state.kompozisyon[key]["yuzde"] = st.session_state[pct_key]

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
if "eos_warning_accepted" not in st.session_state:
    st.session_state.eos_warning_accepted = False
if "q_eos_warning_accepted" not in st.session_state:
    st.session_state.q_eos_warning_accepted = False
if "show_file_loader" not in st.session_state:
    st.session_state.show_file_loader = False

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
    if total < 99.0:
        return f"Bileşen toplamı %{total:.4f} — en az %99.0000 olmalıdır."

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


def draw_phase_envelope(cooler, p_in_bar=None, t_in_c=None, p_out_bar=None, t_out_c=None):
    envelope = cooler.get_phase_envelope()
    if not envelope:
        st.caption("ℹ️ Faz zarfı bu motor/EOS kombinasyonu için oluşturulamadı (yalnızca CoolProp HEOS desteklenir).")
        return

    with st.expander("🌡️ PT Faz Zarfı (Phase Envelope)", expanded=False):
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=envelope["T_C"], y=envelope["P_bar"],
                mode="lines", line=dict(color="#8e44ad", width=3),
                name="Faz Zarfı", fill="tozeroy", fillcolor="rgba(142,68,173,0.08)",
            )
        )
        if envelope["T_crit_C"] is not None:
            fig.add_trace(go.Scatter(
                x=[envelope["T_crit_C"]], y=[envelope["P_crit_bar"]],
                mode="markers", marker=dict(color="#c0392b", size=12, symbol="star"),
                name=f"Kritik Nokta ({envelope['T_crit_C']:.1f}°C, {envelope['P_crit_bar']:.1f} bar)",
            ))
        if p_in_bar is not None and t_in_c is not None:
            fig.add_trace(go.Scatter(
                x=[t_in_c], y=[p_in_bar], mode="markers+text",
                marker=dict(color="#e67e22", size=12, symbol="circle"),
                text=["Giriş"], textposition="top center",
                name="Giriş Noktası",
            ))
        if p_out_bar is not None and t_out_c is not None:
            fig.add_trace(go.Scatter(
                x=[t_out_c], y=[p_out_bar], mode="markers+text",
                marker=dict(color="#2ecc71", size=12, symbol="square"),
                text=["Çıkış"], textposition="top center",
                name="Çıkış Noktası",
            ))
        fig.update_layout(
            title="PT Faz Zarfı",
            xaxis_title="Sıcaklık (°C)",
            yaxis_title="Basınç (bar)",
            height=420,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Cricondentherm: {envelope['cricondentherm_C']:.1f} °C · "
            f"Cricondenbar: {envelope['cricondenbar_bar']:.1f} bar"
        )


def draw_temperature_profile(segments):
    """Proses ve hava sıcaklığını kümülatif alan üzerinde çizer."""
    if not segments:
        return
    xs = [0.0]
    t_proc = [segments[0]["T_out_C"]]
    t_air = [segments[0]["T_air_out_C"]]
    for s in segments:
        xs.append(xs[-1] + s["area_m2"])
        t_proc.append(s["T_in_C"])
        t_air.append(s["T_air_in_C"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=t_proc, mode="lines+markers",
        line=dict(color="#e74c3c", width=2), name="Proses Sıcaklığı",
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=t_air, mode="lines+markers",
        line=dict(color="#2980b9", width=2, dash="dash"), name="Hava Sıcaklığı",
    ))
    fig.update_layout(
        title="Boru Boyu / Alan Boyunca Sıcaklık Profili",
        xaxis_title="Kümülatif Alan (m²)",
        yaxis_title="Sıcaklık (°C)",
        height=380,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def draw_bundle_layout(geom_params):
    """Boru demeti kesit düzenini (sıra × tüp) gösterir."""
    rows = int(geom_params.get("tube_rows", 4))
    cols = int(geom_params.get("tubes_per_row", 24))
    pitch = float(geom_params.get("pitch", 0.0635)) * 1000.0

    xs, ys = [], []
    for r in range(rows):
        for c in range(cols):
            x = c * pitch
            y = r * pitch * 0.866 if geom_params.get("angle", 30) == 30 else r * pitch
            xs.append(x)
            ys.append(y)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(size=7, color="#3498db", opacity=0.8, line=dict(width=1, color="#1f618d")),
        name="Tüpler",
    ))
    fig.update_layout(
        title=f"Boru Demeti Kesiti ({rows} sıra × {cols} tüp, adım {pitch:.0f} mm)",
        xaxis_title="Yatay (mm)",
        yaxis_title="Dikey (mm)",
        height=360,
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


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
                    uname = username_input.strip()
                    st.session_state.authenticated = True
                    st.session_state.username = uname
                    st.session_state.role = role
                    update_last_login(uname, users_db, USERS_FILE)
                    if is_default_password(password_input):
                        st.session_state.default_password = True
                        st.warning("⚠️ Varsayılan şifre ile giriş yaptınız. Güvenlik için şifrenizi değiştirmeniz önerilir.")
                        st.rerun()
                    else:
                        st.session_state.default_password = False
                        st.success("Giriş başarılı! Yönlendiriliyorsunuz...")
                        st.rerun()
                else:
                    st.error("Hatalı kullanıcı adı veya şifre!")

            with st.popover("🔑 Şifre Değiştir", use_container_width=True):
                if not st.session_state.get("authenticated"):
                    st.info("Önce giriş yapın.")
                else:
                    with st.form("password_change_form"):
                        cur_pass = st.text_input("Mevcut Şifre", type="password", key="cur_pass_input")
                        new_pass = st.text_input("Yeni Şifre (en az 6 karakter)", type="password", key="new_pass_input")
                        new_pass2 = st.text_input("Yeni Şifre (Tekrar)", type="password", key="new_pass2_input")
                        if st.form_submit_button("Şifreyi Değiştir", type="primary"):
                            if not new_pass or len(new_pass) < 6:
                                st.error("Şifre en az 6 karakter olmalıdır.")
                            elif new_pass != new_pass2:
                                st.error("Şifreler eşleşmiyor.")
                            else:
                                ok, msg = change_password(
                                    st.session_state.username, cur_pass,
                                    new_pass, users_db, USERS_FILE
                                )
                                if ok:
                                    st.session_state.default_password = False
                                    st.success(f"✅ {msg}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")

            with st.popover("📝 Kayıt Ol", use_container_width=True):
                with st.form("register_form"):
                    reg_user = st.text_input("Kullanıcı Adı", key="reg_user")
                    reg_email = st.text_input("E-posta", key="reg_email")
                    reg_pass = st.text_input("Şifre (en az 6 karakter)", type="password", key="reg_pass")
                    reg_pass2 = st.text_input("Şifre (Tekrar)", type="password", key="reg_pass2")
                    if st.form_submit_button("Kaydol", type="primary"):
                        if not reg_user or not reg_pass:
                            st.error("Kullanıcı adı ve şifre gerekli.")
                        elif reg_pass != reg_pass2:
                            st.error("Şifreler eşleşmiyor.")
                        else:
                            ok, msg = register_user(reg_user, reg_pass, reg_email, users_db, USERS_FILE)
                            if ok:
                                st.success(f"✅ {msg} Şimdi giriş yapabilirsiniz.")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")


def draw_advanced_design():
    st.subheader("📐 Gelişmiş 3-Kademeli Tasarım & Değerlendirme")
    st.caption("Doğal gaz karışımları için çapraz akış (cross-flow) modellemesi, Briggs-Young ısı geçişi ve ESDU basınç kaybı hesaplama motoru.")
    
    if not st.session_state.get("kompozisyon"):
        st.warning("⚠️ Akışkan bileşimi henüz girilmedi. Lütfen '⚙️ Girişler' sekmesinden en az bir gaz bileşeni ekleyin.")
        return
        
    total_comp = sum(v["yuzde"] for v in st.session_state.kompozisyon.values())
    if total_comp < 99.0:
        st.warning(f"⚠️ Karışım bileşeni toplamı %{total_comp:.4f}. En az %99.0000 olmalıdır.")
        return
    if abs(total_comp - 100.0) > 0.01:
        st.info(f"ℹ️ Toplam %{total_comp:.4f} — normalize edilerek hesaplanacak.")

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
            adv_engine = st.selectbox("Termodinamik Motor", get_engine_keys(), key="adv_engine")
            adv_eos_options = get_eos_options(adv_engine)
            if "adv_eos_label" not in st.session_state or st.session_state.adv_eos_label not in adv_eos_options:
                st.session_state.adv_eos_label = adv_eos_options[0]
            adv_eos_label = st.selectbox("EOS", adv_eos_options, key="adv_eos_label")
            st.session_state._adv_eos_key = f"{adv_engine}:{adv_eos_label}"

            _rec_adv = recommend_eos(
                st.session_state.get("kompozisyon", {}),
                P_bar=st.session_state.get("adv_p_in", 0.0),
                current_engine=adv_engine,
            )
            if _rec_adv and st.session_state.get("kompozisyon"):
                _is_ideal = (
                    adv_engine == _rec_adv["recommended_engine"]
                    and adv_eos_label == _rec_adv["recommended_label"]
                )
                if _is_ideal:
                    st.caption(f"💡 *Öneri:* `{adv_eos_label}` ({_rec_adv['badge']}) — Kompozisyon ile uyumlu.")
                else:
                    st.caption(f"💡 *Öneri:* `{_rec_adv['recommended_label']}` ({_rec_adv['badge']})")
                    if st.button("🔄 Önerilene Geç", key="btn_quick_switch_rec_adv", help=_rec_adv["reason"]):
                        st.session_state.adv_engine = _rec_adv["recommended_engine"]
                        st.session_state.adv_eos_label = _rec_adv["recommended_label"]
                        st.session_state.eos_warning_accepted = False
                        st.rerun()

        # ── EOS Risk Uyarısı ──
        _adv_eng_backend, _adv_eos_val = resolve_engine_eos(
            st.session_state.adv_engine, st.session_state.adv_eos_label
        )
        _adv_eos_key = f"{st.session_state.adv_engine}:{st.session_state.adv_eos_label}"
        if st.session_state.get("_adv_eos_prev_key", "") != _adv_eos_key:
            st.session_state.eos_warning_accepted = False
            st.session_state._adv_eos_prev_key = _adv_eos_key
        if _adv_eng_backend == "neqsim" and st.session_state.get("kompozisyon"):
            _risks = assess_eos_risk(
                _adv_eos_val, st.session_state.kompozisyon,
                st.session_state.get("adv_p_in", 0),
            )
            if _risks:
                _expanded = not st.session_state.eos_warning_accepted
                with st.expander("⚠️ EOS Uyarıları", expanded=_expanded):
                    for r in _risks:
                        st.warning(r)
                    if not st.session_state.eos_warning_accepted:
                        fallback = get_fallback_eos(_adv_eos_val)
                        if fallback:
                            _fb_label = None
                            for lbl, val in ENGINE_EOS[st.session_state.adv_engine]["eos"].items():
                                if val == fallback:
                                    _fb_label = lbl
                                    break
                            if _fb_label:
                                col_w1, col_w2 = st.columns(2)
                                with col_w1:
                                    if st.button(f"🔄 Önerilene Geç: {_fb_label}"):
                                        st.session_state.adv_eos_label = _fb_label
                                        st.session_state.eos_warning_accepted = False
                                        st.rerun()
                                with col_w2:
                                    if st.button("⚠️ Yine de Devam Et"):
                                        st.session_state.eos_warning_accepted = True
                                        st.rerun()

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

    if st.session_state.get("kompozisyon"):
        try:
            _env_eng, _env_eos = resolve_engine_eos(st.session_state.adv_engine, st.session_state.adv_eos_label)
            _env_cooler = AirFinnedGasCooler(
                st.session_state.kompozisyon,
                engine=_env_eng,
                eos=_env_eos,
                raw_p_unit=adv_p_unit,
                atmospheric_pressure_pa=st.session_state.P_ATM_PA,
                logger=log_message,
            )
            _t_in_c = Q_(adv_t_in, clean_temp_unit(adv_t_unit)).to("degC").m
            _t_out_c = Q_(adv_t_out, clean_temp_unit(adv_t_unit)).to("degC").m
            _p_in_bar = Q_(adv_p_in, clean_pressure_unit(adv_p_unit)).to("bar").m
            _p_out_bar = Q_(adv_p_out, clean_pressure_unit(adv_p_unit)).to("bar").m
            draw_phase_envelope(_env_cooler, _p_in_bar, _t_in_c, _p_out_bar, _t_out_c)
        except Exception as _env_exc:
            st.caption(f"ℹ️ Faz zarfı oluşturulamadı: {_env_exc}")

    # 2. Mod Seçimi ve Özel Girdiler
    mode = st.radio("Çalışma Modu Seçin", ["Basit Dizayn (Teorik Isı Yükü)", "Detaylı Boyutlandırma (Sizing)", "Eşanjör Değerlendirme (Rating)"], horizontal=True)
    st.session_state["adv_mode"] = mode
    
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
                
                _engine_b, _eos_v = resolve_engine_eos(st.session_state.adv_engine, st.session_state.adv_eos_label)
                cooler = AirFinnedGasCooler(
                    st.session_state.kompozisyon,
                    engine=_engine_b,
                    eos=_eos_v,
                    raw_p_unit=adv_p_unit,
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
                tube_od = st.number_input("Boru Dış Çapı (mm)", min_value=5.0, max_value=100.0, value=25.4, help="API 661 standardı için minimum 25.4 mm (1 inç) veya 20 mm önerilir.", key="adv_tube_od")
                tube_thick = st.number_input("Boru Duvar Kalınlığı (mm)", min_value=0.5, max_value=10.0, value=2.11, help="14 BWG standardı: 2.11 mm", key="adv_tube_thick")
            with g_col2:
                tube_len = st.number_input("Boru Boyu (m)", min_value=1.0, max_value=24.0, value=6.0, key="adv_tube_len")
                tubes_per_row = st.number_input("Sıra Başına Boru Sayısı", min_value=5, max_value=200, value=24, key="adv_tubes_per_row")
            with g_col3:
                tube_rows = st.number_input("Boru Sıra Sayısı", min_value=1, max_value=12, value=4, key="rows_size")
                tube_passes = st.number_input("Akış Geçiş Sayısı", min_value=1, max_value=12, value=4, key="passes_size")
            with g_col4:
                layout_angle = st.selectbox("Dizilim Açısı", [30, 90], format_func=lambda x: "30° (Üçgen)" if x == 30 else "90° (Kare)", key="adv_layout_angle")
                pitch_normal = st.number_input("Boru Eksene Adımı (mm)", min_value=10.0, max_value=200.0, value=63.5, help="Tüplerin merkezleri arasındaki mesafe. 2.5 inç standardı: 63.5 mm", key="adv_pitch_normal")

            g_col5, g_col6, g_col7, g_col8 = st.columns(4)
            with g_col5:
                fin_height = st.number_input("Kanatçık Yüksekliği (mm)", min_value=2.0, max_value=50.0, value=15.9, help="0.625 inç standardı: 15.9 mm", key="adv_fin_height")
                fin_thick = st.number_input("Kanatçık Kalınlığı (mm)", min_value=0.1, max_value=5.0, value=0.4, key="adv_fin_thick")
            with g_col6:
                fin_fpi = st.number_input("İnç Başına Kanatçık (FPI)", min_value=2.0, max_value=30.0, value=10.0, key="adv_fin_fpi")
                fin_type = st.selectbox("Kanat Bağlantı Tipi", ["L-Foot / Double L", "KL (Knurled L)", "Embedded (G-Fin)", "Extruded"], key="adv_fin_type")
            with g_col7:
                tube_mat = st.selectbox("Boru Malzemesi (İletkenlik)", ["Karbon Çelik (50 W/mK)", "Paslanmaz Çelik (15 W/mK)", "Bakır (385 W/mK)"], key="adv_tube_mat")
                fin_mat = st.selectbox("Kanatçık Malzemesi (İletkenlik)", ["Alüminyum (205 W/mK)", "Bakır (385 W/mK)"], key="adv_fin_mat")
                header_type = st.selectbox("Kollektör (Header) Tipi", ["Tapalı Kollektör (Plug)", "Kapaklı Kollektör (Cover Plate)", "Başlıklı Kollektör (Bonnet)"], key="adv_header_type")
            with g_col8:
                fouling_in = st.number_input("Boru İçi Kirlenme (m²K/W)", min_value=0.0, value=0.000176, format="%.6f", help="TEMA standardı doğalgaz kirlenme katsayısı: 0.000176", key="adv_fouling_in")
                fouling_out = st.number_input("Hava Kirlenme Katsayısı (m²K/W)", min_value=0.0, value=0.000088, format="%.6f", key="adv_fouling_out")
                corr_allow = st.number_input("Korozyon Payı (mm)", min_value=0.0, max_value=10.0, value=1.6, help="ASME tasarımında boru iç yüzeyi için korozyon payı", key="adv_ca")
                asme_grade = st.selectbox("Boru Malzeme Sınıfı (ASME)", ["Karbon Çelik (SA-179/A214)", "Paslanmaz Çelik (SA-213 316L)", "Duplex (SA-789 2205)"], key="adv_asme_grade")

            g_col9, g_col10, g_col11, g_col12 = st.columns(4)
            with g_col9:
                fan_eff_raw = st.number_input("Fan Toplam Verimi (%)", min_value=10.0, max_value=100.0, value=65.0, key="adv_fan_eff")
                fan_eff = fan_eff_raw / 100.0
                fan_diameter = st.number_input("Fan Çapı (m)", min_value=0.5, max_value=10.0, value=2.44, help="API 661 standardına göre fan çapı", key="adv_fan_dia")
                n_fans = st.number_input("Fan Sayısı", min_value=1, max_value=20, value=1, key="adv_n_fans")
                fan_rpm = st.number_input("Fan Devri (RPM)", min_value=50, max_value=2000, value=350, help="Kanat uç hızı hesabı için fan devri", key="adv_fan_rpm")
                draft_type = st.selectbox("Çekiş Tipi", ["Cebri Çekiş (Forced Draft)", "İndüklenmiş Çekiş (Induced Draft)"], key="adv_draft_type")
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
                    "fin_type": fin_type,
                    "header_type": header_type,
                    "pitch": float(pitch_normal / 1000.0),
                    "angle": float(layout_angle),
                    "tube_k": k_tube,
                    "fin_k": k_fin,
                    "tube_mat": tube_mat,
                    "fin_mat": fin_mat,
                    "fouling_in": fouling_in,
                    "fouling_out": fouling_out,
                    "fan_efficiency": fan_eff,
                    "fan_diameter": float(fan_diameter),
                    "n_fans": int(n_fans),
                    "fan_rpm": int(fan_rpm),
                    "draft_type": draft_type
                }
                
                _engine_b, _eos_v = resolve_engine_eos(st.session_state.adv_engine, st.session_state.adv_eos_label)
                cooler = AirFinnedGasCooler(
                    st.session_state.kompozisyon,
                    engine=_engine_b,
                    eos=_eos_v,
                    raw_p_unit=adv_p_unit,
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
                
                res["time"] = datetime.now().strftime("%H:%M:%S")
                res["calc_type"] = "detailed_sizing"
                st.session_state.last_res = res.copy()
                for k in ("bolgeler",):
                    if k in res:
                        st.session_state.last_res[k] = res[k]
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
                        st.write(f"**Tahmini Fan Şaft Gücü (API 661):** {res['fan_power_kW']:.2f} kW")
                        st.write(f"**Dinamik Basınç Kaybı (hız basıncı):** {res['dP_dynamic_Pa']:.1f} Pa")
                        st.write(f"**Plenum Kaybı (tahmini %10):** {res['dP_plenum_Pa']:.1f} Pa")
                        st.write(f"**Toplam Fan Basıncı:** {res['total_dP_fan_Pa']:.1f} Pa")
                        st.write(f"**Fan Çıkış Hızı:** {res['v_fan_m_s']:.2f} m/s")
                        st.write(f"**Boru İçi Gaz Akış Hızı:** {res['gas_velocity_m_s']:.2f} m/s")
                        st.write(f"**Boru İçi Gaz Reynolds:** {res['gas_Re']:.0f}")
                        if res.get('gas_dP_minor_bar'):
                            st.write(f"**Gaz Tarafı Toplam Basınç Düşümü:** {res['gas_dP_bar']:.4f} bar (Sürtünme: {res.get('gas_dP_friction_bar', 0.0):.4f} bar, Kollektör/Nozül: {res.get('gas_dP_minor_bar', 0.0):.4f} bar)")
                        else:
                            st.write(f"**Gaz Tarafı Toplam Basınç Düşümü:** {res['gas_dP_bar']:.4f} bar")

                if res.get('saturation_fallback_applied'):
                    st.info(f"ℹ️ **Termodinamik Model Bildirimi:** {res.get('saturation_note')}")
                    st.warning("⚠️ **Gürültü ve Erozyon Riski!** Boru içi gaz hızı 20 m/s sınırının üzerinde. Akış alanını artırmak için paralel tüp sayısını artırmayı düşünebilirsiniz.")
                elif res['gas_velocity_m_s'] < 1.0:
                    st.warning("⚠️ **Kirlenme (Fouling) Riski!** Boru içi akış hızı 1.0 m/s sınırının altında. Geçiş sayısını artırarak hızı yükseltmeyi düşünebilirsiniz.")
                else:
                    st.success("✅ **Hız Sınırları:** Gaz hızları API 661 erozyon ve kirlenme ön-kontrol sınırları içerisinde.")
                    
                with st.expander("📋 API 661 Ön-Tasarım Kontrolleri (Screening Checks)", expanded=False):
                    tube_od_mm = float(tube_od)
                    if tube_od_mm < 25.4:
                        st.warning(f"⚠️ **Boru Dış Çapı:** {tube_od_mm:.1f} mm < 25.4 mm. API 661 rafineri servisi için minimum 1 inç (25.4 mm) önerir.")
                    else:
                        st.info(f"✅ **Boru Dış Çapı:** {tube_od_mm:.1f} mm ≥ 25.4 mm. API 661 asgari kriterini sağlıyor.")
                    
                    tube_thick_mm = float(tube_thick)
                    min_wall = 2.11 if "Karbon" in tube_mat else 1.65
                    if tube_thick_mm < min_wall:
                        st.warning(f"⚠️ **Boru Duvar Kalınlığı:** {tube_thick_mm:.2f} mm < {min_wall:.2f} mm. API 661 minimum {min_wall:.2f} mm önerir ({'CS 14 BWG' if min_wall > 2 else 'Alaşım'} için).")
                    else:
                        st.info(f"✅ **Boru Duvar Kalınlığı:** {tube_thick_mm:.2f} mm ≥ {min_wall:.2f} mm. API 661 asgari kriterini sağlıyor.")
                    
                    v_tip = res.get('fan_tip_speed_m_s', 0.0)
                    if v_tip > 0:
                        if v_tip > 61.0:
                            st.warning(f"⚠️ **Fan Kanat Uç Hızı (Tip Speed):** {v_tip:.1f} m/s > 61 m/s. API 661 maksimum 61 m/s (standart) / 50 m/s (düşük gürültü) önerir.")
                        elif v_tip > 50.0:
                            st.warning(f"⚠️ **Fan Kanat Uç Hızı (Tip Speed):** {v_tip:.1f} m/s > 50 m/s. Düşük gürültü uygulamaları için maksimum 50 m/s önerilir.")
                        else:
                            st.info(f"✅ **Fan Kanat Uç Hızı (Tip Speed):** {v_tip:.1f} m/s ≤ 50 m/s. API 661 asgari kriterini sağlıyor.")
                    else:
                        st.info("ℹ️ **Fan Kanat Uç Hızı:** Fan devri (RPM) girilmeden hesaplanamaz.")

                    fan_lw = res.get('fan_sound_power_dB', 0.0)
                    if fan_lw > 0:
                        spl_1m = fan_lw - 8.0
                        st.info(f"🔊 **Fan Ses Gücü Seviyesi:** ~{fan_lw:.0f} dB (yaklaşık SPL @1m: ~{spl_1m:.0f} dB(A)) — tarama seviyesi tahmin.")

                    fin_limit_c = fin_type_temperature_limit_C(fin_type)
                    if fin_limit_c is not None:
                        t_in_c = t_in_q.to("degC").m
                        if t_in_c > fin_limit_c:
                            st.warning(f"⚠️ **Kanat Tipi Sıcaklık Limiti:** Proses giriş sıcaklığı {t_in_c:.1f} °C > {fin_limit_c:.0f} °C ({fin_type} için API 661 limiti). Daha yüksek sıcaklık sınıfı kanat tipi seçin (ör. Embedded/Extruded).")
                        else:
                            st.info(f"✅ **Kanat Tipi Sıcaklık Limiti:** {t_in_c:.1f} °C ≤ {fin_limit_c:.0f} °C ({fin_type}). API 661 asgari kriterini sağlıyor.")

                    grade = TUBE_MATERIAL_GRADES.get(asme_grade)
                    if grade:
                        p_in_pa, _ = cooler._birim_cevir_P_T(p_in_q, t_in_q)
                        p_out_pa, _ = cooler._birim_cevir_P_T(p_out_q, t_out_q)
                        design_P_pa = max(p_in_pa, p_out_pa) * 1.1
                        S_pa = grade["S_MPa"] * 1e6
                        E = grade["E"]
                        CA_m = float(corr_allow) / 1000.0
                        t_req_mm = required_tube_wall_with_ca(
                            design_P_pa, tube_od / 1000.0, S_pa, E, CA_m
                        ) * 1000.0
                        if tube_thick < t_req_mm:
                            st.warning(f"⚠️ **ASME VIII Div.1 (App.1-1):** Gerekli min. et kalınlığı {t_req_mm:.2f} mm (dahil {corr_allow:.1f} mm CA) > girilen {tube_thick:.2f} mm. Et kalınlığını artırın veya malzeme sınıfını yükseltin.")
                        else:
                            st.info(f"✅ **ASME VIII Div.1 (App.1-1):** Gerekli min. et kalınlığı {t_req_mm:.2f} mm ≤ girilen {tube_thick:.2f} mm ({asme_grade}).")

                if res.get('segmental_applied') and res.get('segments'):
                    with st.expander("🔬 Bölgesel (Segmental) Analiz", expanded=False):
                        st.caption("Isı yükü 12 eşit entalpi segmentine bölünerek her segmentte ayrı U, hi ve alan hesaplandı (yoğuşma segmentlerinde Silver-Bell-Ghaly düzeltmesi).")
                        seg_rows = [
                            {
                                "Segment": s["index"] + 1,
                                "Faz": "İki Faz" if s["two_phase"] else "Tek Faz",
                                "T Giriş (°C)": f"{s['T_in_C']:.1f}",
                                "T Çıkış (°C)": f"{s['T_out_C']:.1f}",
                                "Q (kW)": f"{s['Q_kW']:.2f}",
                                "U (W/m²K)": f"{s['U_W_m2K']:.2f}",
                                "hi (W/m²K)": f"{s['h_inside_W_m2K']:.1f}",
                                "Ft": f"{s.get('Ft', 1.0):.3f}",
                                "Alan (m²)": f"{s['area_m2']:.2f}",
                            }
                            for s in res["segments"]
                        ]
                        st.dataframe(pd.DataFrame(seg_rows), use_container_width=True, hide_index=True)
                        draw_temperature_profile(res["segments"])
                        draw_bundle_layout(geom_params)

                with st.container(border=True):
                    st.markdown("**📥 Rapor İndir**")
                    exp_col1, exp_col2 = st.columns(2)
                    with exp_col1:
                        excel_buf = export_excel(res, geom_params, st.session_state.kompozisyon, mode="Sizing")
                        st.download_button(
                            label="📊 Excel Raporu İndir",
                            data=excel_buf,
                            file_name=f"AirCooler_Sizing_{datetime.now():%Y%m%d_%H%M}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    with exp_col2:
                        pdf_buf = export_pdf(res, geom_params, st.session_state.kompozisyon, mode="Sizing")
                        st.download_button(
                            label="📄 PDF Raporu İndir",
                            data=pdf_buf,
                            file_name=f"AirCooler_Sizing_{datetime.now():%Y%m%d_%H%M}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
            
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
                
                _engine_b, _eos_v = resolve_engine_eos(st.session_state.adv_engine, st.session_state.adv_eos_label)
                cooler = AirFinnedGasCooler(
                    st.session_state.kompozisyon,
                    engine=_engine_b,
                    eos=_eos_v,
                    raw_p_unit=adv_p_unit,
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
                
                res["time"] = datetime.now().strftime("%H:%M:%S")
                res["calc_type"] = "rating"
                st.session_state.last_res = res.copy()
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
                        if "margin_pct" in res and abs(res["margin_pct"]) > 0.01:
                            st.write(f"**Tasarım Marjı (Over-design):** {res['margin_pct']:+.2f} %")
                with rc_5:
                    with st.container(border=True):
                        st.markdown("**⚙️ Basınç Kayıpları & Akış Limiti**")
                        st.write(f"**Boru İçi Hız:** {res['gas_velocity_m_s']:.2f} m/s")
                        st.write(f"**Gaz Tarafı Toplam Basınç Düşümü:** {res['gas_dP_bar']:.4f} bar")
                        if "gas_dP_friction_bar" in res and "gas_dP_minor_bar" in res:
                            st.caption(f"Sürtünme: {res['gas_dP_friction_bar']:.4f} bar | Kollektör/Nozül: {res['gas_dP_minor_bar']:.4f} bar")
                        st.write(f"**Hava Tarafı Basınç Düşümü (ESDU):** {res['dP_air_Pa']:.2f} Pa")
                        st.write(f"**Çıkış Gaz Faz Durumu:** **{res['gas_out_phase']}**")
                        if "gas_out_quality" in res and res.get("condensation_applied"):
                            st.write(f"**Çıkış Buhar Kalitesi (x):** {res['gas_out_quality']:.3f}")

                if res.get('segmental_applied') and res.get('segments'):
                    with st.expander("📊 Segmental (Zone-by-Zone) Isı & Alan Profili (12 Segment)", expanded=False):
                        st.dataframe(
                            pd.DataFrame([
                                {
                                    "Segment": s["segment_idx"],
                                    "T_in (°C)": f"{s['T_in_C']:.1f}",
                                    "T_out (°C)": f"{s['T_out_C']:.1f}",
                                    "T_air_in (°C)": f"{s['T_air_in_C']:.1f}",
                                    "T_air_out (°C)": f"{s['T_air_out_C']:.1f}",
                                    "U (W/m²K)": f"{s['U_W_m2K']:.1f}",
                                    "hi (W/m²K)": f"{s['h_inside_W_m2K']:.1f}",
                                    "Ft": f"{s.get('Ft', 1.0):.3f}",
                                    "Alan (m²)": f"{s['area_m2']:.2f}",
                                    "İki Faz": "Evet" if s["is_two_phase"] else "Hayır",
                                }
                                for s in res["segments"]
                            ]),
                            use_container_width=True,
                            hide_index=True,
                        )
                        draw_temperature_profile(res["segments"])

                with st.container(border=True):
                    st.markdown("**📥 Rapor İndir**")
                    exp_col1, exp_col2 = st.columns(2)
                    with exp_col1:
                        excel_buf = export_excel(res, geom_params, st.session_state.kompozisyon, mode="Rating")
                        st.download_button(
                            label="📊 Excel Raporu İndir",
                            data=excel_buf,
                            file_name=f"AirCooler_Rating_{datetime.now():%Y%m%d_%H%M}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    with exp_col2:
                        pdf_buf = export_pdf(res, geom_params, st.session_state.kompozisyon, mode="Rating")
                        st.download_button(
                            label="📄 PDF Raporu İndir",
                            data=pdf_buf,
                            file_name=f"AirCooler_Rating_{datetime.now():%Y%m%d_%H%M}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
            
            except Exception as e:
                st.error(f"Değerlendirme hatası: {e}")
                log_error("Değerlendirme hesaplama hatası.", e)


# ═══════════════════════════════════════════════════════════
# PROJE KAYDET / AÇ
# ═══════════════════════════════════════════════════════════

def _json_safe(value):
    """Dataclass, Pint Quantity ve numpy değerlerini JSON-serializable yapıya derinlemesine çevirir."""
    import dataclasses
    import numpy as np
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_safe(dataclasses.asdict(value))
    if hasattr(value, "magnitude") and hasattr(value, "units"):
        return {"magnitude": float(value.magnitude), "unit": str(value.units)}
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (np.generic, np.number)):
        return value.item()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def serialize_inputs(state=None):
    """Tüm girdileri JSON-serializable dict'e çevirir."""
    if state is None:
        state = st.session_state
    _s = state.get  # shorthand
    inp = {"version": "1.0", "timestamp": datetime.now().isoformat(), "inputs": {}}
    i = inp["inputs"]

    i["composition"] = _s("kompozisyon", {})

    i["units"] = {
        "p_unit": _s("ui_p_u", "bar(a)"),
        "t_unit": _s("ui_t_u", "°C"),
        "flow_u": _s("ui_flow_u", "Sm3/h"),
        "adv_p_u": _s("adv_p_u", "bar(a)"),
        "adv_t_u": _s("adv_t_u", "°C"),
        "adv_flow_u": _s("adv_flow_u", "Sm3/h"),
    }

    i["quick_tab"] = {
        "flow_v": _s("ui_flow", 15.0),
        "p_in": _s("ui_p_in", 60.0),
        "t_in": _s("ui_t_in", 100.0),
        "p_out": _s("ui_p_out", 58.0),
        "t_out": _s("ui_t_out", 40.0),
        "air_in": _s("ui_air_in", 25.0),
        "air_out": _s("ui_air_out", 45.0),
        "engine": _s("q_engine", get_engine_keys()[0]),
        "eos_label": _s("q_eos_label", None),
        "overall_u": _s("ui_overall_u", 35.0),
        "correction_factor": _s("ui_cf", 0.90),
    }

    adv = {"mode": _s("adv_mode", "Basit Dizayn (Teorik Isı Yükü)")}

    for k in ("flow_v", "p_in", "t_in", "t_out", "p_out",
              "engine", "eos_label", "t_u", "p_u", "flow_u"):
        sk = f"adv_{k}"
        v = _s(sk)
        if v is not None:
            adv[k] = v

    geom_keys = {
        "tube_od": 25.4, "tube_thick": 2.11, "tube_len": 6.0,
        "tubes_per_row": 24, "layout_angle": 30, "pitch_normal": 63.5,
        "fin_height": 15.9, "fin_thick": 0.4, "fin_fpi": 10.0,
        "fin_type": "L-Foot / Double L",
        "header_type": "Tapalı Kollektör (Plug)",
        "tube_mat": "Karbon Çelik (50 W/mK)", "fin_mat": "Alüminyum (205 W/mK)",
        "fouling_in": 0.000176, "fouling_out": 0.000088, "fan_eff": 65.0,
        "fan_dia": 2.44, "n_fans": 1, "fan_rpm": 350,
        "draft_type": "Cebri Çekiş (Forced Draft)",
        "ca": 1.6, "asme_grade": "Karbon Çelik (SA-179/A214)",
    }
    geom = {}
    for gk, gdefault in geom_keys.items():
        sk = f"adv_{gk}"
        geom[gk] = _s(sk, gdefault)
    adv["geometry"] = geom

    rgeom_keys = {
        "r_od": 25.4, "r_thick": 2.11, "r_len": 6.0, "r_tubes": 24,
        "r_angle": 30, "r_pitch": 63.5, "r_fin_h": 15.9, "r_fin_t": 0.4,
        "r_fpi": 10.0, "r_tmat": "Karbon Çelik (50 W/mK)",
        "r_fmat": "Alüminyum (205 W/mK)", "r_fi": 0.000176, "r_fo": 0.000088,
        "r_air_in": 25.0, "r_fan_flow": 150000.0,
    }
    for gk in ("rows_rating", "passes_rating"):
        v = _s(gk)
        if v is not None:
            rgeom_keys[gk] = v
    rgeom = {}
    for gk, gdefault in rgeom_keys.items():
        rgeom[gk] = _s(gk, gdefault)
    adv["rating_geometry"] = rgeom

    for k in ("air_in_b", "air_out_b", "rows_b", "passes_b"):
        sk = f"adv_{k}"
        v = _s(sk)
        if v is not None:
            adv[k] = v

    for k in ("air_in_s", "air_out_s"):
        v = _s(k)
        if v is not None:
            adv[k] = v

    i["advanced_tab"] = adv

    last_res = _s("last_res")
    if last_res:
        rs = {}
        for k, v in last_res.items():
            try:
                v = _json_safe(v)
                json.dumps(v)
                rs[k] = v
            except (TypeError, OverflowError):
                rs[k] = str(v)
        i["last_res"] = rs

    return json.dumps(inp, ensure_ascii=False, indent=2)


def load_project_file(data, state=None):
    """JSON proje dosyasından session_state'i günceller."""
    if state is None:
        state = st.session_state
    i = data.get("inputs", {})

    if "composition" in i:
        state["kompozisyon"] = i["composition"]

    units = i.get("units", {})
    for sk, sv in units.items():
        state[sk] = sv

    unit_key_map = {
        "p_unit": "ui_p_u",
        "t_unit": "ui_t_u",
        "flow_u": "ui_flow_u",
        "adv_p_u": "adv_p_u",
        "adv_t_u": "adv_t_u",
        "adv_flow_u": "adv_flow_u",
    }
    for orig_k, ui_k in unit_key_map.items():
        if orig_k in units:
            state[ui_k] = units[orig_k]

    qt = i.get("quick_tab", {})
    qmap = {"flow_v": "ui_flow", "p_in": "ui_p_in", "t_in": "ui_t_in",
            "p_out": "ui_p_out", "t_out": "ui_t_out", "air_in": "ui_air_in",
            "air_out": "ui_air_out", "overall_u": "ui_overall_u",
            "correction_factor": "ui_cf", "engine": "q_engine",
            "eos_label": "q_eos_label"}
    for qk, sk in qmap.items():
        if qk in qt:
            state[sk] = qt[qk]

    at = i.get("advanced_tab", {})
    if "mode" in at:
        state["adv_mode"] = at["mode"]
    amap = {"flow_v": "adv_flow_v", "p_in": "adv_p_in", "t_in": "adv_t_in",
            "t_out": "adv_t_out", "p_out": "adv_p_out",
            "engine": "adv_engine", "eos_label": "adv_eos_label",
            "t_u": "adv_t_u", "p_u": "adv_p_u", "flow_u": "adv_flow_u"}
    for ak, sk in amap.items():
        if ak in at:
            state[sk] = at[ak]

    gmap = {"tube_od": "adv_tube_od", "tube_thick": "adv_tube_thick",
            "tube_len": "adv_tube_len", "tubes_per_row": "adv_tubes_per_row",
            "layout_angle": "adv_layout_angle", "pitch_normal": "adv_pitch_normal",
            "fin_height": "adv_fin_height", "fin_thick": "adv_fin_thick",
            "fin_fpi": "adv_fin_fpi", "fin_type": "adv_fin_type",
            "header_type": "adv_header_type",
            "tube_mat": "adv_tube_mat",
            "fin_mat": "adv_fin_mat", "fouling_in": "adv_fouling_in",
            "fouling_out": "adv_fouling_out", "fan_eff": "adv_fan_eff",
            "fan_dia": "adv_fan_dia", "n_fans": "adv_n_fans", "fan_rpm": "adv_fan_rpm",
            "draft_type": "adv_draft_type",
            "ca": "adv_ca", "asme_grade": "adv_asme_grade"}
    for gk, sk in gmap.items():
        v = at.get("geometry", {}).get(gk)
        if v is not None:
            state[sk] = v

    rmap = {"r_od": "r_od", "r_thick": "r_thick", "r_len": "r_len",
            "r_tubes": "r_tubes", "r_angle": "r_angle", "r_pitch": "r_pitch",
            "r_fin_h": "r_fin_h", "r_fin_t": "r_fin_t", "r_fpi": "r_fpi",
            "r_tmat": "r_tmat", "r_fmat": "r_fmat", "r_fi": "r_fi",
            "r_fo": "r_fo", "r_air_in": "r_air_in", "r_fan_flow": "r_fan_flow",
            "rows_rating": "rows_rating", "passes_rating": "passes_rating"}
    for gk, sk in rmap.items():
        v = at.get("rating_geometry", {}).get(gk)
        if v is not None:
            state[sk] = v

    for k in ("air_in_b", "air_out_b", "rows_b", "passes_b"):
        v = at.get(k)
        if v is not None:
            state[f"adv_{k}"] = v
    for k in ("air_in_s", "air_out_s"):
        v = at.get(k)
        if v is not None:
            state[k] = v

    results = data.get("results", i.get("last_res", {}))
    if results:
        state["last_res"] = results

    state["eos_warning_accepted"] = False
    state["q_eos_warning_accepted"] = False


def draw_main():
    st.title(f"🌡️ {APP_DISPLAY_NAME} | Gaz Soğutucu Termal Yük Hesaplayıcı")
    st.caption("Doğal gaz ve hidrokarbon karışımları için termal yük ve ön boyutlandırma tahmini")
    draw_release_notes()

    role = st.session_state.get("role", "user")

    # ── Proje Kaydet / Aç Toolbar ──
    username = st.session_state.get("username", "user")

    proje_json = serialize_inputs()
    st.caption("Proje kaydetmek/açmak için üstteki araçları kullanın.")

    with st.expander("💾 Proje Yönetimi", expanded=False):
        save_col1, save_col2, save_col3 = st.columns([3, 1, 1])
        with save_col1:
            project_name = st.text_input("Proje Adı", value="", placeholder="örn: Doğalgaz Soğutucu", label_visibility="collapsed")
            project_desc = st.text_input("Açıklama", value="", placeholder="Kısa açıklama (opsiyonel)", label_visibility="collapsed")
        with save_col2:
            if st.button("💾 Sunucuya Kaydet", use_container_width=True):
                if not project_name:
                    st.error("Lütfen bir proje adı girin.")
                else:
                    try:
                        inputs_data = json.loads(proje_json)
                        results_data = _json_safe(st.session_state.get("last_res", {}))
                        path = save_project(project_name, project_desc, inputs_data.get("inputs", inputs_data), results_data, saved_by=username)
                        st.success(f"✅ Proje kaydedildi: {Path(path).name}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Kayıt hatası: {exc}")
        with save_col3:
            st.download_button(
                "📥 Dışa Aktar",
                data=proje_json,
                file_name=f"air_cooler_{datetime.now():%Y%m%d_%H%M}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.divider()
        st.markdown("**📂 Kayıtlı Projeler**")
        projects = list_projects()
        if not projects:
            st.info("Henüz kaydedilmiş proje yok.")
        else:
            proj_options = {f"{p['project_name']} ({p['filename']})": p for p in projects}
            selected_label = st.selectbox("Bir proje seçin", list(proj_options.keys()), label_visibility="collapsed")
            if selected_label:
                sel = proj_options[selected_label]
                desc = sel.get("description", "")
                meta = f"👤 {sel.get('saved_by', '?')} | 🕐 {sel.get('updated_at', '?')[:16]}"
                st.caption(f"{desc} — {meta}" if desc else meta)
                act_col1, act_col2, act_col3 = st.columns([1, 1, 1])
                with act_col1:
                    if st.button("📂 Yükle", use_container_width=True):
                        try:
                            data = load_project_filepath(sel["path"])
                            load_project_file(data)
                            st.success(f"✅ {sel['project_name']} yüklendi.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Yükleme hatası: {exc}")
                with act_col2:
                    st.download_button(
                        "📥 Dışa Aktar",
                        data=json.dumps(load_project_filepath(sel["path"]), ensure_ascii=False, indent=2),
                        file_name=sel["filename"],
                        mime="application/json",
                        use_container_width=True,
                    )
                with act_col3:
                    if st.button("🗑️ Sil", use_container_width=True, type="secondary"):
                        if delete_project_file(sel["path"]):
                            st.success(f"✅ {sel['project_name']} silindi.")
                            st.rerun()
                        else:
                            st.error("Silme hatası.")
        st.divider()
        if st.button("📂 Dosyadan Aç", use_container_width=True):
            st.session_state.show_file_loader = True
        if st.session_state.show_file_loader:
            uploaded = st.file_uploader("Proje dosyası seçin", type="json", label_visibility="collapsed")
            if uploaded:
                try:
                    data = json.loads(uploaded.read().decode("utf-8"))
                    load_project_file(data)
                    st.session_state.show_file_loader = False
                    st.success(f"✅ Proje yüklendi: {uploaded.name}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Dosya yüklenemedi: {exc}")
                    st.session_state.show_file_loader = False
    st.divider()

    if role == "admin":
        tab_inputs, tab_report, tab_new_design, tab_users, tab_logs = st.tabs(["⚙️ Girişler", "📊 Rapor", "📐 Gelişmiş Boyutlandırma", "👥 Kullanıcı Yönetimi", "📜 Kayıtlar"])
    else:
        tab_inputs, tab_report, tab_logs = st.tabs(["⚙️ Girişler", "📊 Rapor", "📜 Kayıtlar"])
        tab_new_design = None
        tab_users = None

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
                b_val = st.number_input("Yüzde", 0.0, 100.0, 0.0, 0.0001, format="%.4f", label_visibility="collapsed")
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
                st.markdown("**Mevcut Karışım (tıklayarak düzenle)**")
                for key in list(st.session_state.kompozisyon.keys()):
                    val = st.session_state.kompozisyon[key]
                    row1, row2, row3, row4 = st.columns([4, 2.5, 2, 1])
                    row1.write(f"🧪 {COOLPROP_COMPONENTS[key]}")
                    row2.number_input(
                        "%", min_value=0.0, max_value=100.0,
                        value=float(val["yuzde"]), step=0.0001, format="%.4f",
                        key=f"pct_{key}", label_visibility="collapsed",
                        on_change=update_composition_pct,
                    )
                    row3.write(val["tip"])
                    if row4.button("❌", key=f"del_{key}", help=f"{COOLPROP_COMPONENTS[key]} sil"):
                        del st.session_state.kompozisyon[key]
                        st.rerun()

            total = sum(v["yuzde"] for v in st.session_state.kompozisyon.values())
            tip = list(st.session_state.kompozisyon.values())[0]["tip"]
            if total < 99.0:
                st.error(f"⚠️ Toplam: %{total:.4f} (En az %99.0000 olmalıdır.)")
            elif abs(total - 100.0) > 0.01:
                st.info(f"ℹ️ Toplam: %{total:.4f} — normalize edilerek hesaplanacak ({tip})")
            else:
                st.success(f"✅ Toplam: %100.0000 ({tip})")

            # ── EOS Öneri Kartı ──
            _p_hint = st.session_state.get("adv_p_in", st.session_state.get("ui_p_in", 0.0))
            _rec = recommend_eos(
                st.session_state.kompozisyon,
                P_bar=_p_hint,
                current_engine=st.session_state.get("adv_engine"),
            )
            if _rec:
                with st.container(border=True):
                    r_col1, r_col2 = st.columns([3.8, 1.2])
                    with r_col1:
                        st.markdown(
                            f"💡 **Önerilen Termodinamik Model:** "
                            f"`{_rec['recommended_label']}` ({_rec['recommended_engine']}) — "
                            f"*{_rec['badge']}*"
                        )
                        st.caption(f"**Gerekçe:** {_rec['reason']}")
                        if _rec.get("alternative_label"):
                            st.caption(
                                f"**Alternatif:** `{_rec['alternative_label']}` ({_rec['alternative_engine']}) — "
                                f"{_rec['alternative_reason']}"
                            )
                    with r_col2:
                        _curr_eng = st.session_state.get("adv_engine", "")
                        _curr_eos = st.session_state.get("adv_eos_label", "")
                        _is_active = (
                            _curr_eng == _rec["recommended_engine"]
                            and _curr_eos == _rec["recommended_label"]
                        )
                        if _is_active:
                            st.success("✅ Şu an Seçili")
                        else:
                            if st.button("👉 Önerileni Uygula", key="btn_apply_eos_rec", use_container_width=True):
                                st.session_state.adv_engine = _rec["recommended_engine"]
                                st.session_state.adv_eos_label = _rec["recommended_label"]
                                if _rec["recommended_engine"] in get_engine_keys():
                                    st.session_state.q_engine = _rec["recommended_engine"]
                                st.session_state.q_eos_label = _rec["recommended_label"]
                                st.session_state.eos_warning_accepted = False
                                st.session_state.q_eos_warning_accepted = False
                                st.rerun()

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
                p_in = st.number_input("Giriş Basıncı", min_value=0.0, value=60.0, format="%.2f", key="ui_p_in")

                t_unit = st.selectbox("Sıcaklık Birimi", UNITS["Sıcaklık"], key="ui_t_u")
                min_temp = {"°C": -273.15, "K": 0.0, "°F": -459.67}[t_unit]
                default_in = 107.0 if t_unit != "K" else 380.15
                default_out = 37.0 if t_unit != "K" else 310.15
                t_in = st.number_input("Giriş Sıc.", min_value=min_temp, value=default_in, format="%.2f", key="ui_t_in")

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
                air_in = st.number_input("Hava Giriş Sıc.", min_value=min_temp, value=default_air_in, format="%.2f", key="ui_air_in")

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
                    key="ui_p_out",
                )
                t_out = st.number_input("Çıkış Sıc.", min_value=min_temp, value=default_out, format="%.2f", key="ui_t_out")

            with st.container(border=True):
                draw_station_header("C1", "Bundle / UA", "EOS seçimi ve ön boyutlandırma parametreleri", "design")
                q_engine = st.selectbox("Termodinamik Motor", get_engine_keys(), key="q_engine")
                q_eos_options = get_eos_options(q_engine)
                st.selectbox("EOS", q_eos_options, key="q_eos_label")

                _rec_q = recommend_eos(
                    st.session_state.get("kompozisyon", {}),
                    P_bar=st.session_state.get("q_p_in", 0.0),
                    current_engine=q_engine,
                )
                if _rec_q and st.session_state.get("kompozisyon"):
                    _curr_q_lbl = st.session_state.get("q_eos_label", "")
                    _is_ideal_q = (
                        q_engine == _rec_q["recommended_engine"]
                        and _curr_q_lbl == _rec_q["recommended_label"]
                    )
                    if _is_ideal_q:
                        st.caption(f"💡 *Öneri:* `{_curr_q_lbl}` ({_rec_q['badge']}) — Kompozisyon ile uyumlu.")
                    else:
                        st.caption(f"💡 *Öneri:* `{_rec_q['recommended_label']}` ({_rec_q['badge']})")
                        if st.button("🔄 Önerilene Geç", key="btn_quick_switch_rec_q", help=_rec_q["reason"]):
                            st.session_state.q_engine = _rec_q["recommended_engine"]
                            st.session_state.q_eos_label = _rec_q["recommended_label"]
                            st.session_state.q_eos_warning_accepted = False
                            st.rerun()
                # ── EOS Risk Uyarısı (Hızlı Hesaplama) ──
                _q_eng_backend, _q_eos_val = resolve_engine_eos(
                    st.session_state.get("q_engine", get_engine_keys()[0]),
                    st.session_state.get("q_eos_label", get_eos_options(get_engine_keys()[0])[0]),
                )
                _q_eos_key = f"{st.session_state.get('q_engine', '')}:{st.session_state.get('q_eos_label', '')}"
                if st.session_state.get("_q_eos_prev_key", "") != _q_eos_key:
                    st.session_state.q_eos_warning_accepted = False
                    st.session_state._q_eos_prev_key = _q_eos_key
                if _q_eng_backend == "neqsim" and st.session_state.get("kompozisyon"):
                    _q_risks = assess_eos_risk(
                        _q_eos_val, st.session_state.kompozisyon,
                        st.session_state.get("q_p_in", 0),
                    )
                    if _q_risks:
                        _q_expanded = not st.session_state.q_eos_warning_accepted
                        with st.expander("⚠️ EOS Uyarıları", expanded=_q_expanded):
                            for r in _q_risks:
                                st.warning(r)
                            if not st.session_state.q_eos_warning_accepted:
                                _q_fb = get_fallback_eos(_q_eos_val)
                                if _q_fb:
                                    _q_fb_label = None
                                    for lbl, val in ENGINE_EOS[st.session_state.get("q_engine", list(ENGINE_EOS.keys())[0])]["eos"].items():
                                        if val == _q_fb:
                                            _q_fb_label = lbl
                                            break
                                    if _q_fb_label:
                                        _q_c1, _q_c2 = st.columns(2)
                                        with _q_c1:
                                            if st.button(f"🔄 Önerilene Geç: {_q_fb_label}", key="q_fb_btn"):
                                                st.session_state.q_eos_label = _q_fb_label
                                                st.session_state.q_eos_warning_accepted = False
                                                st.rerun()
                                        with _q_c2:
                                            if st.button("⚠️ Yine de Devam Et", key="q_continue_btn"):
                                                st.session_state.q_eos_warning_accepted = True
                                                st.rerun()
                overall_u = st.number_input(
                    "Genel U [W/(m²·K)]",
                    min_value=1.0,
                    value=35.0,
                    step=1.0,
                    help="Finned air cooler için kullanıcı tanımlı ön toplam ısı transfer katsayısı.",
                    key="ui_overall_u",
                )
                correction_factor = st.number_input(
                    "LMTD Düzeltme Faktörü F",
                    min_value=0.10,
                    max_value=1.00,
                    value=0.90,
                    step=0.01,
                    format="%.2f",
                    help="Karşı-akış eşdeğeri LMTD üzerine uygulanan düzeltme faktörü.",
                    key="ui_cf",
                )

            st.markdown('<div class="ac-spacer-sm"></div>', unsafe_allow_html=True)

            with st.container(border=True):
                draw_station_header("B2", "Üst Hava Çıkışı", "Bundle üzerinden ısınarak çıkan hava", "air-out")
                air_out = st.number_input("Hava Çıkış Sıc.", min_value=min_temp, value=default_air_out, format="%.2f", key="ui_air_out")

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
                        _q_engine_b, _q_eos_v = resolve_engine_eos(
                            st.session_state.get("q_engine", get_engine_keys()[0]),
                            st.session_state.get("q_eos_label", get_eos_options(get_engine_keys()[0])[0]),
                        )
                        cooler = AirFinnedGasCooler(
                            st.session_state.kompozisyon,
                            engine=_q_engine_b,
                            eos=_q_eos_v,
                            raw_p_unit=p_unit,
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
                            "eos": _q_eos_v,
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
            st.info("Lütfen Girişler veya Gelişmiş Boyutlandırma sekmesinden bir hesaplama işlemini başlatın.", icon="ℹ️")
        else:
            time_str = result.get("time", "")
            header_title = f"✅ Rapor ({time_str})" if time_str else "✅ Rapor"
            st.header(header_title)

            if result.get("uyari"):
                st.warning(result["uyari"], icon="⚠️")

            if "q_g" in result:
                # ── Hızlı Hesaplama Raporu ──
                metric_col1, metric_col2, metric_col3 = st.columns(3)
                with metric_col1:
                    st.metric("Gerçek Gaz Soğutma Yükü", f"{result['q_g'].to('MW').m:.4f} MW", border=True)
                with metric_col2:
                    if result.get("q_i") is not None:
                        st.metric("İdeal Gaz Yükü (Referans)", f"{result['q_i'].to('MW').m:.4f} MW", border=True)
                    else:
                        st.metric("İdeal Gaz Yükü (Referans)", "Hesaplanamadı", border=True)
                with metric_col3:
                    if result.get("q_i") is not None and abs(result["q_g"].m) > 1e-12:
                        diff = abs(result["q_g"].m - result["q_i"].m) / abs(result["q_g"].m) * 100.0
                        st.metric("Sapma (Gerçek vs İdeal)", f"% {diff:.2f}", border=True)
                    else:
                        st.metric("Sapma (Gerçek vs İdeal)", "-", border=True)

                if "ara" in result:
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
                            st.write(f"**Faz:** {ara.get('faz_in', '—')}")
                            st.write(f"**Basınç:** {ara.get('P_in_Pa', 0) / 1e5:.2f} bar(a)")
                            st.write(f"**Sıcaklık:** {ara.get('T_in_K', 273.15) - 273.15:.2f} °C")
                            st.write(f"**Yoğunluk:** {ara.get('rho_in', 0):.2f} kg/m³")
                            st.write(f"**Sp. Entalpi:** {ara.get('H_in_kJ_kg', 0):.2f} kJ/kg")
                    with detail_col2:
                        with st.container(border=True):
                            st.markdown("**📤 Çıkış Koşulları**")
                            st.write(f"**Faz:** {ara.get('faz_out', '—')}")
                            st.write(f"**Basınç:** {ara.get('P_out_Pa', 0) / 1e5:.2f} bar(a)")
                            st.write(f"**Sıcaklık:** {ara.get('T_out_K', 273.15) - 273.15:.2f} °C")
                            st.write(f"**Yoğunluk:** {ara.get('rho_out', 0):.2f} kg/m³")
                            st.write(f"**Sp. Entalpi:** {ara.get('H_out_kJ_kg', 0):.2f} kJ/kg")
                    with detail_col3:
                        with st.container(border=True):
                            st.markdown("**⚙️ Akış Parametreleri**")
                            st.write(f"**Kütlesel Debi:** {ara.get('m_dot_kg_s', 0):.4f} kg/s")
                            st.write(f"**Basınç Düşümü (ΔP):** {ara.get('delta_P_bar', 0):.2f} bar")
                            st.write(f"**Kullanılan Motor:** {result.get('eos', '—')}")
                            if "Cp_ideal" in ara:
                                st.write(f"**İdeal Gaz Cp0:** {ara['Cp_ideal']:.3f} kJ/(kg·K)")

            elif "actual_area_m2" in result:
                # ── Detaylı Boyutlandırma Raporu ──
                st.caption("Bu rapor **Gelişmiş Boyutlandırma (Sizing)** sonuçlarını içermektedir.")
                m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                m_col1.metric("Toplam Yük (Q)", f"{result.get('Q_kW', 0.0) / 1000.0:.4f} MW", border=True)
                m_col2.metric("Toplam Eşanjör Alanı", f"{result.get('actual_area_m2', 0.0):.2f} m²", border=True)
                m_col3.metric("Gerekli Alan", f"{result.get('required_area_m2', 0.0):.2f} m²", border=True)
                m_col4.metric("Overdesign %", f"{result.get('overdesign_pct', 0.0):.2f} %", border=True)

                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    with st.container(border=True):
                        st.markdown("**🔬 Isı Geçiş Performansı & Dirençler**")
                        st.write(f"**U Katsayısı (Toplam):** {result.get('U_W_m2K', 0.0):.2f} W/(m²·K)")
                        st.write(f"**h_i (Boru İçi):** {result.get('h_inside_W_m2K', 0.0):.1f} W/(m²·K)")
                        st.write(f"**h_o (Hava Tarafı):** {result.get('h_outside_W_m2K', 0.0):.1f} W/(m²·K)")
                        st.write(f"**Efektif LMTD (Ft x LMTD):** {result.get('effective_lmtd_K', 0.0):.2f} K")
                with d_col2:
                    with st.container(border=True):
                        if result.get('gas_dP_minor_bar'):
                            st.write(f"**Gaz Tarafı Toplam Basınç Düşümü:** {result.get('gas_dP_bar', 0.0):.4f} bar (Sürtünme: {result.get('gas_dP_friction_bar', 0.0):.4f} bar, Kollektör/Nozül: {result.get('gas_dP_minor_bar', 0.0):.4f} bar)")
                        else:
                            st.write(f"**Gaz Tarafı Basınç Düşümü:** {result.get('gas_dP_bar', 0.0):.4f} bar")
                        st.write(f"**Hava Tarafı Basınç Düşümü:** {result.get('dP_air_Pa', 0.0):.1f} Pa")
                        st.write(f"**Tahmini Fan Gücü:** {result.get('fan_power_kW', 0.0):.2f} kW")
                        st.write(f"**Boru İçi Gaz Hızı:** {result.get('gas_velocity_m_s', 0.0):.2f} m/s")

                if result.get('saturation_fallback_applied'):
                    st.info(f"ℹ️ **Termodinamik Model Bildirimi:** {result.get('saturation_note')}")

            elif "effectiveness" in result:
                # ── Rating Raporu ──
                st.caption("Bu rapor **Gelişmiş Değerlendirme (Rating)** sonuçlarını içermektedir.")
                rc_1, rc_2, rc_3 = st.columns(3)
                rc_1.metric("Gerçek Isı Aktarımı (Q)", f"{result.get('Q_kW', 0.0) / 1000.0:.4f} MW", border=True)
                rc_2.metric("Gaz Çıkış Sıcaklığı", f"{result.get('T_gas_out_C', 0.0):.2f} °C", border=True)
                rc_3.metric("Hava Çıkış Sıcaklığı", f"{result.get('T_air_out_C', 0.0):.2f} °C", border=True)

                rc_4, rc_5 = st.columns(2)
                with rc_4:
                    with st.container(border=True):
                        st.markdown("**🔬 Isı Değiştirici Etkinliği**")
                        st.write(f"**Isı Değiştirici Verimi (Effectiveness):** {result.get('effectiveness', 0.0) * 100:.2f} %")
                        st.write(f"**NTU (Transfer Birim Sayısı):** {result.get('NTU', 0.0):.3f}")
                        st.write(f"**U Katsayısı (Toplam):** {result.get('U_W_m2K', 0.0):.2f} W/(m²·K)")
                with rc_5:
                    with st.container(border=True):
                        st.markdown("**🌪️ Hidrolik & Fan**")
                        st.write(f"**Gaz Tarafı Basınç Düşümü:** {result.get('gas_dP_bar', 0.0):.4f} bar")
                        st.write(f"**Hava Tarafı Basınç Düşümü:** {result.get('dP_air_Pa', 0.0):.1f} Pa")
                        st.write(f"**Boru İçi Gaz Hızı:** {result.get('gas_velocity_m_s', 0.0):.2f} m/s")
            else:
                st.json(result)

            # ── Admin: Tüm EOS Karşılaştırma Tablosu ──
            _role = st.session_state.get("role", "user")
            if _role == "admin" and st.session_state.get("kompozisyon") and "ara" in result:
                st.divider()
                with st.expander("🔬 Tüm EOS'ları Karşılaştır (Admin)", expanded=False):
                    if st.button("▶ Karşılaştırmayı Çalıştır", key="eos_compare_btn"):
                        _comp = st.session_state.kompozisyon
                        _P_in = result["ara"].get("P_in_Pa", 60e5) / 1e5
                        _P_out = result["ara"].get("P_out_Pa", 58e5) / 1e5
                        _T_in_K = result["ara"].get("T_in_K", 373.15)
                        _T_out_K = result["ara"].get("T_out_K", 313.15)
                        _flow_v = result["ara"].get("m_dot_kg_s", 0.1)
                        _p_unit = "bar(a)"

                        _rows = []
                        for _eos_label, _eos_val in ENGINE_EOS["🌍 neqsim"]["eos"].items():
                            try:
                                _c = AirFinnedGasCooler(
                                    _comp,
                                    engine="neqsim",
                                    eos=_eos_val,
                                    raw_p_unit=_p_unit,
                                )
                                _q, _qi, _ = _c.hesapla_isi_yuku(
                                    _flow_v, "kg/s",
                                    Q_(_P_in, "bar"), Q_(_P_out, "bar"),
                                    Q_(_T_in_K, "K"), Q_(_T_out_K, "K"),
                                )
                                _r = _c.ara_sonuclar
                                _dh = _r.get("H_in_kJ_kg", 0) - _r.get("H_out_kJ_kg", 0)
                                _rows.append({
                                    "EOS": _eos_label,
                                    "Q (MW)": round(float(_q.to("MW").m), 6),
                                    "Δh (kJ/kg)": round(_dh, 2),
                                    "ρ_in": round(_r.get("rho_in", 0), 2),
                                    "ρ_out": round(_r.get("rho_out", 0), 2),
                                    "Z_in": round(_r.get("Z_in", 0), 4),
                                    "Çalıştı": "✅",
                                })
                            except Exception as _exc:
                                _rows.append({
                                    "EOS": _eos_label,
                                    "Q (MW)": None,
                                    "Δh (kJ/kg)": None,
                                    "ρ_in": None,
                                    "ρ_out": None,
                                    "Z_in": None,
                                    "Çalıştı": f"❌ {str(_exc)[:60]}",
                                })

                        if _rows:
                            _df = pd.DataFrame(_rows)
                            st.dataframe(_df, use_container_width=True, hide_index=True)
                            _ok = [r for r in _rows if r["Çalıştı"] == "✅"]
                            if len(_ok) > 1:
                                _ref_q = _ok[0]["Q (MW)"]
                                _df_chart = pd.DataFrame(_ok)
                                _df_chart["fark%"] = _df_chart["Q (MW)"].apply(
                                    lambda q: round((q - _ref_q) / _ref_q * 100, 3) if _ref_q else 0
                                )
                                _fig = px.bar(
                                    _df_chart, x="EOS", y="Q (MW)",
                                    color="fark%",
                                    color_continuous_scale="RdYlGn_r",
                                    title="EOS Karşılaştırma - Isı Yükü (MW)",
                                    text="fark%",
                                )
                                _fig.update_traces(texttemplate="%{text}%", textposition="outside")
                                st.plotly_chart(_fig, use_container_width=True)
    if tab_new_design is not None:
        with tab_new_design:
            draw_advanced_design()

    if tab_users is not None:
        with tab_users:
            st.subheader("👥 Kullanıcı Yönetimi")
            user_list = auth_list_users(users_db)

            st.markdown("**Mevcut Kullanıcılar**")
            if user_list:
                df_users = pd.DataFrame(user_list)
                df_users.columns = ["Kullanıcı Adı", "Rol", "E-posta", "Görünen Ad", "Oluşturulma", "Son Giriş"]
                st.dataframe(df_users, use_container_width=True, hide_index=True)

            with st.popover("➕ Yeni Kullanıcı Ekle", use_container_width=True):
                with st.form("admin_add_user"):
                    au_user = st.text_input("Kullanıcı Adı", key="au_user")
                    au_email = st.text_input("E-posta", key="au_email")
                    au_pass = st.text_input("Şifre (en az 6 karakter)", type="password", key="au_pass")
                    au_role = st.selectbox("Rol", ["user", "admin"], key="au_role")
                    if st.form_submit_button("Oluştur", type="primary"):
                        if not au_user or not au_pass:
                            st.error("Kullanıcı adı ve şifre gerekli.")
                        else:
                            ok, msg = register_user(au_user, au_pass, au_email, users_db, USERS_FILE)
                            if ok:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")

            st.divider()
            st.markdown("**Kullanıcı İşlemleri**")
            user_names = [u["username"] for u in user_list]
            if user_names:
                op_col1, op_col2, op_col3 = st.columns(3)
                with op_col1:
                    sel_user = st.selectbox("Kullanıcı Seç", user_names, label_visibility="collapsed")
                with op_col2:
                    new_role = st.selectbox("Yeni Rol", ["user", "admin"], index=0, key="admin_role_sel")
                    if st.button("Rolü Güncelle", use_container_width=True):
                        ok, msg = update_user_role(sel_user, new_role, users_db, USERS_FILE)
                        if ok:
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                with op_col3:
                    if st.button("🗑️ Kullanıcıyı Sil", use_container_width=True, type="secondary"):
                        ok, msg = auth_delete_user(sel_user, users_db, USERS_FILE)
                        if ok:
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

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
