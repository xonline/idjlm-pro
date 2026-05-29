# idjlm.spec
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

librosa_datas, librosa_binaries, librosa_hiddenimports = collect_all('librosa')
soundfile_datas, soundfile_binaries, soundfile_hiddenimports = collect_all('soundfile')
sklearn_datas, sklearn_binaries, sklearn_hiddenimports = collect_all('sklearn')
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')

a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=soundfile_binaries + librosa_binaries + sklearn_binaries + numpy_binaries,
    datas=[
        ('app', 'app'),
        ('templates', 'templates'),
        ('taxonomy.json', '.'),
        *librosa_datas,
        *soundfile_datas,
        *sklearn_datas,
        *numpy_datas,
        *collect_data_files('scipy'),
    ],
    hiddenimports=[
        *librosa_hiddenimports,
        *soundfile_hiddenimports,
        *sklearn_hiddenimports,
        *numpy_hiddenimports,
        *collect_submodules('scipy'),
        *collect_submodules('flask'),
        *collect_submodules('flask_cors'),
        *collect_submodules('mutagen'),
        *collect_submodules('google.generativeai'),
        *collect_submodules('anthropic'),
        *collect_submodules('spotipy'),
        *collect_submodules('watchdog'),
        *collect_submodules('pylast'),
        *collect_submodules('deezer'),
        'resampy', 'soxr', 'audioread', 'pooch', 'lazy_loader',
        'numba', 'llvmlite', 'certifi', 'charset_normalizer', 'urllib3',
        'PIL', 'PIL.Image',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'IPython', 'jupyter', 'matplotlib', 'tkinter', 'PyQt5', 'PyQt6',
        'wx', 'gi', 'cv2', 'tensorflow', 'torch', 'torchvision', 'pywebview',
    ],
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
    name='idjlm-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
)
