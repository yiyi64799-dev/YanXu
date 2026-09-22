# Desktop-only build; keep the existing cross-platform release spec untouched.
a = Analysis(['yanxu_desktop.py'], pathex=['.build_deps'], binaries=[],
             datas=[('assets/yanxu-logo-1024.png', 'assets')],
             hiddenimports=['pkgutil', 'sqlite3'], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='YanXu', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, icon=['assets/yanxu.ico'])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='YanXu')
