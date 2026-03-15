# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec для сборки Nestify.
Генерирует .app + .dmg (macOS) или директорию для NSIS-инсталлера (Windows).
"""

import sys
from pathlib import Path

block_cipher = None

# Playwright browsers — добавляем в bundle если папка уже скачана в CI
_pw_dir = './playwright-browsers'
_pw_datas = [(_pw_dir, 'playwright-browsers')] if Path(_pw_dir).exists() else []

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('ui', 'ui'),
        ('assets', 'assets'),
        ('api', 'api'),
        ('agent', 'agent'),
        ('database', 'database'),
    ] + _pw_datas,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'fastapi.staticfiles',
        'fastapi.templating',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'fastapi.responses',
        'fastapi.routing',
        'starlette.staticfiles',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.responses',
        'starlette.routing',
        'starlette.templating',
        'aiosqlite',
        'google.generativeai',
        'playwright',
        'multipart',
        'jinja2',
        'email.mime.text',
        'email.mime.multipart',
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

# ──────────────────────────────────────────────
# macOS — .app bundle (COLLECT + BUNDLE)
# ──────────────────────────────────────────────
if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Nestify',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon='assets/logo.png',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Nestify',
    )
    app = BUNDLE(
        coll,
        name='Nestify.app',
        icon='assets/logo.png',
        bundle_identifier='kz.nestify.app',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleVersion': '0.1.0',
            'LSUIElement': False,
        },
    )

# ──────────────────────────────────────────────
# Windows — директория (для NSIS-инсталлера)
# ──────────────────────────────────────────────
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Nestify',
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
        icon='assets/logo.ico',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Nestify',
    )
