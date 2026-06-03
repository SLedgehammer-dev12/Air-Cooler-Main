# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = [
    ("air_cooler_main_app.py", "."),
    ("air_cooler_main_core.py", "."),
    ("air_cooler_main_templates.json", "."),
    ("air_cooler_main_prefs.json", "."),
    ("assets/gas_cooler_schematic.svg", "assets"),
]
binaries = []
hiddenimports = []

for package_name in ("streamlit", "pint", "CoolProp", "plotly", "pandas", "numpy"):
    datas += copy_metadata(package_name)
    tmp_datas, tmp_binaries, tmp_hidden = collect_all(package_name)
    datas += tmp_datas
    binaries += tmp_binaries
    hiddenimports += tmp_hidden

a = Analysis(
    ["run_air_cooler_main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AirCooler_Main",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AirCooler_Main",
)
