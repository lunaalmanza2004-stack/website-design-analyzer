import importlib
mods = [
 "flask","reportlab","PIL","dotenv","pydrive2","bs4","numpy",
 "app.services.report","app.services.screenshot","app.services.scoring",
 "app.services.drive","app.services.sheets","app.services.palette",
 "app.services.insights","app.config"
]
for m in mods:
    try:
        importlib.import_module(m)
        print("OK", m)
    except Exception as e:
        print("ERR", m, "->", repr(e))
        raise
