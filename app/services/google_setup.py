"""Google account authorization and private Sheet provisioning."""
import json
import os
from urllib.parse import urlencode

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

from services.local_db import metadata
from runtime_config import SAMPLE_DATA_DIR, google_settings

TOKEN_URL = 'https://oauth2.googleapis.com/token'
SHEETS_URL = 'https://sheets.googleapis.com/v4/spreadsheets'
SCOPES = (
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
)


def redirect_uri():
    return google_settings().redirect_uri


class GoogleConnectionError(ValueError):
    pass

def configuration():
    config = google_settings()
    values = (config.client_id, config.client_secret, config.redirect_uri)
    if not all(values):
        raise GoogleConnectionError('Configure the Google OAuth client ID, secret, and redirect URI on the server.')
    return values


def authorization_url(state, verifier_hash):
    client, _, redirect_uri = configuration()
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id': client, 'redirect_uri': redirect_uri, 'response_type': 'code',
        'scope': ' '.join(SCOPES), 'access_type': 'offline', 'prompt': 'consent select_account',
        'state': state, 'code_challenge': verifier_hash, 'code_challenge_method': 'S256',
    })


def exchange(code, verifier):
    client, secret, redirect_uri = configuration()
    response = requests.post(TOKEN_URL, data={
        'grant_type': 'authorization_code', 'code': code, 'code_verifier': verifier,
        'client_id': client, 'client_secret': secret, 'redirect_uri': redirect_uri,
    }, timeout=20)
    if not response.ok:
        raise ValueError('Google could not authorize this connection. Reconnect and check the OAuth redirect URL.')
    token = response.json()
    if not token.get('refresh_token') or not token.get('access_token'):
        raise ValueError('Google did not grant continued access. Connect again and approve access.')
    user = requests.get('https://openidconnect.googleapis.com/v1/userinfo',
                        headers={'Authorization': 'Bearer ' + token['access_token']}, timeout=20)
    if not user.ok or not user.json().get('email_verified') or not user.json().get('email'):
        raise ValueError('Use a Google account with a verified email address.')
    return {'email': user.json()['email'], 'refresh_token': token['refresh_token'], 'client_id': client}


def get_connection(conn=None):
    if conn:
        return conn
    conn = metadata('google_setup_connection') or {}
    env_refresh = os.getenv('GOOGLE_REFRESH_TOKEN', '').strip()
    client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '').strip()
    sheet_id = os.getenv('BUILDSMART_SHEET_ID', '').strip()
    if env_refresh:
        conn['refresh_token'] = env_refresh
        conn['client_id'] = client_id or conn.get('client_id', '')
        conn['sheet_id'] = sheet_id or conn.get('sheet_id', '')
        conn['ready'] = True
        try:
            from services.local_db import connection as db_conn
            with db_conn() as db:
                db.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', ('google_setup_connection', json.dumps(conn)))
        except Exception:
            pass
    return conn


def sheets_session(connection=None):
    client, secret, _ = configuration()
    connection = get_connection(connection)
    if not connection.get('refresh_token'):
        raise GoogleConnectionError('The Google connection is missing. Connect a Google account first.')
    credentials = Credentials(None, refresh_token=connection['refresh_token'], token_uri=TOKEN_URL,
                              client_id=client, client_secret=secret, scopes=SCOPES)
    return AuthorizedSession(credentials)


def verify_existing_sheet(connection, spreadsheet_id):
    with sheets_session(connection) as client:
        response = client.get(f'{SHEETS_URL}/{spreadsheet_id}', params={'fields': 'spreadsheetId'}, timeout=20)
    if not response.ok:
        raise GoogleConnectionError(
            'This Google account could not open the spreadsheet. '
            'Share the sheet with your Google account as Editor and try again.'
        )


def create_template(connection):
    from services.sheets_source import FIELDS
    from services.google_archive import TAB
    sheets = [{'properties': {'title': tab, 'gridProperties': {'frozenRowCount': 1}}} for tab in (*FIELDS, TAB)]
    with sheets_session(connection) as client:
        response = client.post(SHEETS_URL, params={'fields': 'spreadsheetId'},
                               json={'properties': {'title': 'BuildSmart 360 – Estimation Master Data'}, 'sheets': sheets},
                               timeout=30)
    if not response.ok or not response.json().get('spreadsheetId'):
        raise ValueError('Google could not create the spreadsheet. Check that the Sheets API is enabled and the account has permission to create files.')
    return response.json()['spreadsheetId']


def seed_template(connection):
    from services.sheets_source import FIELDS
    from services.google_archive import TAB, HEADERS

    samples = json.loads((SAMPLE_DATA_DIR / 'masters.json').read_text(encoding='utf-8'))
    data = []
    for tab, columns in FIELDS.items():
        rows = [[record.get(column, '') for column in columns] for record in samples[tab]]
        data.append({'range': f"'{tab}'!A1", 'values': [columns, *rows]})
    data.append({'range': f"'{TAB}'!A1", 'values': [HEADERS]})
    with sheets_session(connection) as client:
        response = client.post(SHEETS_URL + '/' + connection['sheet_id'] + '/values:batchUpdate',
                               json={'valueInputOption': 'RAW', 'data': data}, timeout=30)
    if not response.ok:
        raise ValueError('The Sheet was created, but Google could not save its sample data. Retry setup to finish the same Sheet.')


def setup_spreadsheet(connection, spreadsheet_id):
    from services.sheets_source import FIELDS
    from services.google_archive import TAB, HEADERS

    with sheets_session(connection) as client:
        response = client.get(f'{SHEETS_URL}/{spreadsheet_id}', params={'fields': 'sheets.properties(sheetId,title)'}, timeout=25)
        if not response.ok:
            raise GoogleConnectionError(
                'Could not access the Google Sheet. Verify that the connected Google account has access, or share the sheet with it as Editor.'
            )
        data = response.json()
        existing_sheets = {s['properties']['title']: s['properties']['sheetId'] for s in data.get('sheets', [])}

        needed_tabs = [*FIELDS, TAB]
        requests = []
        for tab in needed_tabs:
            if tab not in existing_sheets:
                requests.append({'addSheet': {'properties': {'title': tab, 'gridProperties': {'frozenRowCount': 1}}}})
        if requests:
            client.post(f'{SHEETS_URL}/{spreadsheet_id}:batchUpdate', json={'requests': requests}, timeout=30)
            response = client.get(f'{SHEETS_URL}/{spreadsheet_id}', params={'fields': 'sheets.properties(sheetId,title)'}, timeout=25)
            existing_sheets = {s['properties']['title']: s['properties']['sheetId'] for s in response.json().get('sheets', [])}

        samples = json.loads((SAMPLE_DATA_DIR / 'masters.json').read_text(encoding='utf-8'))
        batch_values = []
        for tab, columns in FIELDS.items():
            check = client.get(f"{SHEETS_URL}/{spreadsheet_id}/values/'{tab}'!A1:B2", timeout=15).json().get('values', [])
            if not check:
                rows = [[str(record.get(column, '')) for column in columns] for record in samples[tab]]
                batch_values.append({'range': f"'{tab}'!A1", 'values': [columns, *rows]})

        check_est = client.get(f"{SHEETS_URL}/{spreadsheet_id}/values/'{TAB}'!A1:B2", timeout=15).json().get('values', [])
        if not check_est:
            est_rows = [HEADERS]
            try:
                import csv
                from runtime_config import ROOT
                est_file = ROOT / 'scratch_sheets_export' / 'Estimates.csv'
                if est_file.is_file():
                    reader = list(csv.reader(est_file.open(encoding='utf-8')))
                    if len(reader) > 1:
                        est_rows = reader
            except Exception:
                pass
            batch_values.append({'range': f"'{TAB}'!A1", 'values': est_rows})

        if batch_values:
            client.post(f"{SHEETS_URL}/{spreadsheet_id}/values:batchUpdate",
                        json={'valueInputOption': 'RAW', 'data': batch_values}, timeout=30)

        if 'Sheet1' in existing_sheets and len(existing_sheets) > 1:
            try:
                client.post(f'{SHEETS_URL}/{spreadsheet_id}:batchUpdate',
                            json={'requests': [{'deleteSheet': {'sheetId': existing_sheets['Sheet1']}}]}, timeout=15)
            except Exception:
                pass

