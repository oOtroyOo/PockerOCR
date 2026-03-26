# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ['program.py','PokerOCRWindow.py','RegionEditorDialog.py','OCRWorker.py','CardEvaluator.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.yaml', '.'),
        ('styles/style.qss', 'styles'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'win32gui',
        'win32con',
        'win32api',
        'mss',
        'cv2',
        'pytesseract',
        'yaml',
        'PIL',
        'numpy',
        'secrets'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'unittest',
        'pytest',
        'pydoc',
        'email',
        'http',
        'xml',
        'html',
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
    name='PokerOCR',
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PokerOCR',
)
