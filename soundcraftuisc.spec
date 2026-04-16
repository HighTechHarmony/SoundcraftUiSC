# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the soundcraftuisc standalone binary.
# Build with:  pyinstaller soundcraftuisc.spec

a = Analysis(
    ['soundcraftuisc/_entry.py'],
    pathex=[],
    binaries=[],
    # Bundle default-init.yml into the same sub-directory as cli.py so that
    # the os.path.dirname(__file__) lookup in cli.py still resolves correctly.
    datas=[('soundcraftuisc/default-init.yml', 'soundcraftuisc')],
    hiddenimports=['yaml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='soundcraftuisc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
