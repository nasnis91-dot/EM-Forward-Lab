# PyInstaller spec — builds a folder app (fast start-up). Run:  pyinstaller --noconfirm EM-Forward-Lab.spec
from PyInstaller.utils.hooks import collect_submodules

hidden = (collect_submodules("scipy.sparse") + collect_submodules("scipy.linalg") + collect_submodules("scipy.signal")
          + ["matplotlib.backends.backend_qtagg", "openpyxl"])

a = Analysis(["app.py"], pathex=["."], datas=[("examples", "examples")],
             hiddenimports=hidden, excludes=["tkinter", "pytest", "IPython"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EM-Forward-Lab", console=False,
          icon=None, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="EM-Forward-Lab")
