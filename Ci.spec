# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


block_cipher = None
datas = [('./poems.json', '.')]
if Path('qiji-combo.ttf').exists():
    datas.append(('./qiji-combo.ttf', '.'))


a = Analysis(
    ['ci.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['ipaddress', 'pkg_resources'],
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
    [],
    exclude_binaries=True,
    name='Ci',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Ci',
)
app = BUNDLE(
    coll,
    name='Ci.app',
    icon=None,
    bundle_identifier='com.yankihue.ci',
    info_plist={
            'NSPrincipalClass': 'NSApplication',
            'LSBackgroundOnly': True,
            'LSUIElement': True,
            },
)
