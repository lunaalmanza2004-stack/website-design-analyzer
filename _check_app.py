import importlib
m = importlib.import_module("app.app")
print("module file:", getattr(m, "__file__", None))
print("has `app`:", hasattr(m, "app"))
