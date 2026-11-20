"""Archive estimates to the connected account's Drive and spreadsheet."""
import json
import threading
import uuid
from urllib.parse import quote

from services import google_setup
from services.local_db import metadata, supabase_admin
from services.pdf_generator import generate_estimate_pdf

DRIVE = 'https://www.googleapis.com/drive/v3/files'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files'
TAB = 'Estimates'
HEADERS = ['Estimate ID', 'Project', 'Customer', 'Created at', 'Grand total (INR)', 'PDF']
LOCK = threading.Lock()
TIMEOUT = (5, 15)


def checked(response):
    if not response.ok:
        raise RuntimeError(f'Google archive request returned HTTP {response.status_code}.')
    return response.json()


def values_url(sheet, cells):
    return sheet + '/values/' + quote(f"'{TAB}'!{cells}", safe='')


def ensure_tab(client, sheet):
    info = checked(client.get(sheet, params={'fields': 'sheets(properties(title))'}, timeout=TIMEOUT))
    if not any(tab['properties']['title'] == TAB for tab in info.get('sheets', [])):
        checked(client.post(sheet + ':batchUpdate', json={'requests': [
            {'addSheet': {'properties': {'title': TAB, 'gridProperties': {'frozenRowCount': 1}}}},
        ]}, timeout=TIMEOUT))
    headers = checked(client.get(values_url(sheet, 'A1:F1'), timeout=TIMEOUT)).get('values', [])
    if not headers:
        checked(client.put(values_url(sheet, 'A1:F1'), params={'valueInputOption': 'RAW'},
                           json={'values': [HEADERS]}, timeout=TIMEOUT))
    elif headers[0] != HEADERS:
        raise ValueError('The Estimates tab headers were changed. Restore its original first row.')


def store(estimate_id, archive):
    supabase_admin.table('estimates').update({'google_archive': archive}).eq('id', estimate_id).execute()


def upload_pdf(client, estimate_id, file_id, pdf):
    boundary = uuid.uuid4().hex
    details = json.dumps({'id': file_id, 'name': f'Estimate_{estimate_id}.pdf', 'mimeType': 'application/pdf'}).encode()
    body = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode() + details +
            f'\r\n--{boundary}\r\nContent-Type: application/pdf\r\n\r\n'.encode() + pdf +
            f'\r\n--{boundary}--\r\n'.encode())
    response = client.post(UPLOAD, params={'uploadType': 'multipart', 'fields': 'id'}, data=body,
                           headers={'Content-Type': f'multipart/related; boundary={boundary}'}, timeout=TIMEOUT)
    if response.status_code == 409:
        response = client.get(f'{DRIVE}/{file_id}', params={'fields': 'id'}, timeout=TIMEOUT)
    checked(response)


def archive_estimate(estimate_id, project, builder):
    config = metadata('source_config') or {}
    conn = google_setup.get_connection()
    if (config.get('mode') != 'google_sheets' and not os.getenv('BUILDSMART_SHEET_ID')) or not conn.get('refresh_token'):
        return {'status': 'not_connected'}

    # Use the target sheet: environment variable or source_config spreadsheet_id or conn.sheet_id.
    archive_spreadsheet_id = os.getenv('BUILDSMART_SHEET_ID') or config.get('spreadsheet_id') or conn.get('sheet_id')

    with LOCK:
        estimate = supabase_admin.table('estimates').select('*').eq('id', estimate_id).single().execute().data
        archive = estimate.get('google_archive') or {'status': 'pending', 'spreadsheet_id': archive_spreadsheet_id}
        if archive['status'] == 'archived':
            return archive
        archive['spreadsheet_id'] = archive_spreadsheet_id
        sheet = f"{google_setup.SHEETS_URL}/{archive_spreadsheet_id}"
        store(estimate_id, archive)
        with google_setup.sheets_session() as client:
            ensure_tab(client, sheet)
            if not archive.get('file_id'):
                response = client.get(DRIVE + '/generateIds',
                                      params={'count': 1, 'space': 'drive', 'type': 'files'}, timeout=TIMEOUT)
                archive['file_id'] = checked(response)['ids'][0]
                store(estimate_id, archive)
            file_id = archive['file_id']
            if not archive.get('pdf_url'):
                items = supabase_admin.table('estimate_items').select('*').eq(
                    'estimate_id', estimate_id).order('sort_order', desc=False).execute().data
                pdf = generate_estimate_pdf(estimate, items, builder_name=builder.get('company_name'),
                                            builder_logo=builder.get('avatar_url'))
                upload_pdf(client, estimate_id, file_id, pdf)
                archive['pdf_url'] = f'https://drive.google.com/file/d/{file_id}/view'
                store(estimate_id, archive)
            existing = checked(client.get(values_url(sheet, 'A2:A'), timeout=TIMEOUT)).get('values', [])
            if not any(row and row[0] == estimate_id for row in existing):
                customer = (estimate.get('input_json') or {}).get('customer_name', '')
                row = [estimate_id, project['name'], customer, estimate['generated_at'],
                       estimate['grand_total'], archive['pdf_url']]
                checked(client.post(values_url(sheet, 'A1:F') + ':append',
                                    params={'valueInputOption': 'RAW', 'insertDataOption': 'INSERT_ROWS'},
                                    json={'values': [row]}, timeout=TIMEOUT))
        archive['status'] = 'archived'
        store(estimate_id, archive)
        return archive
