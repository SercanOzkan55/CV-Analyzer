# -*- mode: python ; coding: utf-8 -*-
#
# Builds on Windows, macOS, and Linux -- PyInstaller can't cross-compile, so
# each platform's binary must actually be built ON that platform (see
# .github/workflows/build-local-worker.yml, which does exactly this via a
# GitHub Actions job matrix). This file is plain Python, so it branches on
# sys.platform rather than needing three separate spec files.

import sys
from pathlib import Path

SPEC_DIR = Path(SPECPATH)
ICNS_PATH = SPEC_DIR / "assets" / "logo.icns"

datas = [
    ("assets/cv_analyzer_worker.ico", "assets"),
    ("assets/logo.png", "assets"),
    ("qml", "qml"),
    ("ats_config.yaml", "."),
]
# Only bundled when present -- the .icns is generated as a build step on the
# macOS CI runner (native sips/iconutil aren't available on Windows/Linux),
# so it doesn't exist for those platforms' builds.
if ICNS_PATH.exists():
    datas.append(("assets/logo.icns", "assets"))

if sys.platform == "win32":
    icon = "assets/cv_analyzer_worker.ico"
elif sys.platform == "darwin" and ICNS_PATH.exists():
    icon = "assets/logo.icns"
else:
    # PyInstaller's icon= only applies to Windows EXE resources and macOS
    # .app bundles -- there's no equivalent for a bare Linux ELF binary.
    icon = None

a = Analysis(
    ["qml_gui.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickControls2",
    ],
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
    a.binaries,
    a.datas,
    [],
    name="CV Analyzer Local Worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

# macOS gets a proper .app bundle (Finder-double-clickable, real dock icon)
# instead of a bare Unix executable -- Windows already has native .exe
# semantics and Linux has no equivalent bundle convention to match.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="CV Analyzer Local Worker.app",
        icon=icon,
        bundle_identifier="dev.cvanalyzer.localworker",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
        },
    )
