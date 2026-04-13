# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'flask',
        'google.generativeai',
        'PIL',
        'dotenv',
        'fitz',
        'pymupdf',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'pytest',
        'unittest',
        'pydoc',
        'doctest',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'IPython', 'jupyter', 'notebook',
        'sqlite3',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onedir 방식: 즉시 실행, 폴더로 배포
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='경비정산서',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # 디버깅용. 안정화되면 False
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='경비정산서',
)
