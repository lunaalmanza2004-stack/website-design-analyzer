import importlib, traceback
mods = [
 "app.app","app.services.report","app.services.drive","app.services.sheets",
 "app.services.scoring","app.services.palette","app.services.insights","app.config"
]
for m in mods:
    print(">> probing", m)
    try:
        importlib.import_module(m)
        print("OK", m)
    except Exception:
        traceback.print_exc()
        raise
