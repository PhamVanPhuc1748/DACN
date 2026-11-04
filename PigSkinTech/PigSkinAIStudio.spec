# PyInstaller build recipe. PyInstaller must be installed explicitly by the owner.
from PyInstaller.utils.hooks import collect_all


flet_data, flet_binaries, flet_hidden = collect_all('flet')
project_data = [
    ('assets/login_pig.png', 'assets'),
    ('models/best.pth', 'models'),
    ('models/classes.json', 'models'),
    ('models/model_manifest.json', 'models'),
    ('models/runtime.json', 'models'),
    # The external AI interpreter needs physical modules; modules stored only
    # in PyInstaller's PYZ archive cannot be imported by that interpreter.
    ('services/inference_worker.py', 'services'),
    ('services/inference.py', 'services'),
    ('services/paths.py', 'services'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=flet_binaries,
    datas=flet_data + project_data,
    hiddenimports=flet_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=['torch', 'torchvision'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PigSkinAIStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
