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
    excludes=[
        # GUI alternatives we don't use
        'tkinter', 'matplotlib', 'IPython',
        # OCR is an optional install via [project.optional-dependencies] ocr.
        # When present in the build env, exclude from the .app bundle to keep
        # the distribution slim. (Saves ~60MB on macOS arm64.)
        'ocrmac', 'PIL',
        'objc', 'Foundation', 'AppKit', 'Quartz', 'Vision', 'CoreML',
        'pyobjc_framework_Cocoa', 'pyobjc_framework_Vision',
        'pyobjc_framework_CoreML', 'pyobjc_framework_Quartz',
        # ML frameworks not used at runtime (huggingface_hub touches them
        # via ctypes lookups that PyInstaller scans). These are NOT installed
        # but we exclude defensively to silence warnings and avoid stale
        # imports finding system-wide installs.
        'tensorflow', 'tensorflow_text', 'tensorboard',
        'torch', 'torchvision', 'torchaudio',
        'jax', 'jaxlib', 'flax', 'optax',
        # PySide6 modules we don't use — saves ~80MB
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtSensors',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel', 'PySide6.QtWebSockets',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtPositioning', 'PySide6.QtLocation',
        'PySide6.QtSerialPort', 'PySide6.QtSerialBus',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
        'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtPdf',
        'PySide6.QtPdfWidgets', 'PySide6.QtRemoteObjects',
        'PySide6.QtScxml', 'PySide6.QtStateMachine', 'PySide6.QtSpatialAudio',
    ],
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
