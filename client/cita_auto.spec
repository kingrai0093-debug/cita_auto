# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

SPECPATH = os.path.abspath(SPECPATH if 'SPECPATH' in locals() else '.')

a = Analysis(
    ['cita_auto.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[
        ('config.example.json', '.'),
    ],
    hiddenimports=[
        'curl_cffi',
        'curl_cffi.requests',
        'curl_cffi.curl',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'urllib3',
        'certifi',
        'requests',
        'json',
        'argparse',
        'datetime',
        're',
        'time',
        'threading',
        'shutil',
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
    name='cita_auto',
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
)
