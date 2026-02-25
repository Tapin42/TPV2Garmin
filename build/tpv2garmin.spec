# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for TPV2Garmin — single-file windowed application."""

import os
import sys

block_cipher = None

# Paths
SRC_DIR = os.path.join(os.path.dirname(SPEC), "..", "src")
ASSETS_DIR = os.path.join(SRC_DIR, "tpv2garmin", "assets")
ICON_FILE = os.path.join(ASSETS_DIR, "icon.ico")

a = Analysis(
    [os.path.join(SRC_DIR, "tpv2garmin", "app.py")],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[
        (os.path.join(ASSETS_DIR, "icon.ico"), os.path.join("tpv2garmin", "assets")),
    ],
    hiddenimports=[
        "pystray._win32",
        "winotify",
        "garth",
        "garth.sso",
        "garth.http",
        "garth.auth_tokens",
        "fit_file_faker",
        "fit_file_faker.fit_editor",
        "fit_file_faker.config",
        "fit_file_faker.utils",
        "fit_file_faker.vendor.fit_tool",
        "fit_file_faker.vendor.fit_tool.fit_file",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TPV2Garmin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # --windowed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
)
