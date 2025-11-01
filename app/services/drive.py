import os
from typing import Dict
try:
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
except Exception:
    GoogleAuth = None
    GoogleDrive = None

def _drive():
    if GoogleAuth is None or GoogleDrive is None:
        raise RuntimeError("pydrive2 no está instalado/configurado.")
    gauth = GoogleAuth()
    gauth.ServiceAuth()
    return GoogleDrive(gauth)

def upload_file(local_path: str, parent_folder_id: str) -> Dict[str,str]:
    # Si falta config, devolvemos info clara pero NO rompemos importaciones.
    if not parent_folder_id:
        return {"error": "No DRIVE_PARENT_FOLDER_ID set"}
    if GoogleAuth is None:
        return {"error": "pydrive2 not available"}
    d = _drive()
    fname = os.path.basename(local_path)
    f = d.CreateFile({"title": fname, "parents": [{"id": parent_folder_id}]})
    f.SetContentFile(local_path)
    f.Upload()
    try:
        f.InsertPermission({"type": "anyone", "value": "me", "role": "reader"})
    except Exception:
        pass
    return {"id": f.get("id",""), "webViewLink": f.get("alternateLink","")}
