# lexisub.spec
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

mlx_datas, mlx_binaries, mlx_hidden = collect_all('mlx')
mlx_whisper_datas, mlx_whisper_binaries, mlx_whisper_hidden = collect_all('mlx_whisper')
mlx_lm_datas, mlx_lm_binaries, mlx_lm_hidden = collect_all('mlx_lm')

block_cipher = None

a = Analysis(
    ['lexisub/main.py'],
    pathex=[],
    binaries=mlx_binaries + mlx_whisper_binaries + mlx_lm_binaries,
    datas=[
        ('lexisub/db/schema.sql', 'lexisub/db'),
    ] + mlx_datas + mlx_whisper_datas + mlx_lm_datas,
    hiddenimports=[
        'lexisub.gui.video_tab',
        'lexisub.gui.glossary_tab',
        'lexisub.gui.main_window',
        'loguru',
    ] + mlx_hidden + mlx_whisper_hidden + mlx_lm_hidden
      + collect_submodules('mlx_lm.models'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython'],
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
    name='Lexisub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Lexisub',
)

app = BUNDLE(
    coll,
    name='Lexisub.app',
    icon=None,
    bundle_identifier='dev.existmaster.lexisub',
    info_plist={
        'CFBundleName': 'Lexisub',
        'CFBundleDisplayName': 'Lexisub',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'LSMinimumSystemVersion': '12.0',
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    },
)
