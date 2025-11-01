import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

SCOPE = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def _client():
    creds = Credentials.from_service_account_file(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'), scopes=SCOPE)
    return gspread.authorize(creds)

def append_log(spreadsheet_id: str, row: list):
    gc = _client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.sheet1
    ws.append_row(row, value_input_option='RAW')
