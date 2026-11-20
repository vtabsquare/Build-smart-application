"""Archive estimates to the connected account's Drive and spreadsheet."""
import json
import os
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
                input_data = estimate.get('input_json') or {}
                customer = (input_data.get('customer_name') or input_data.get('customer') or 
                            input_data.get('client_name') or input_data.get('client') or 
                            project.get('customer_name') or '')
                row = [estimate_id, project.get('name', 'Project'), customer, estimate.get('generated_at') or estimate.get('created_at'),
                       estimate.get('grand_total', 0), archive.get('pdf_url', '')]
                checked(client.post(values_url(sheet, 'A1:F') + ':append',
                                    params={'valueInputOption': 'RAW', 'insertDataOption': 'INSERT_ROWS'},
                                    json={'values': [row]}, timeout=TIMEOUT))
        archive['status'] = 'archived'
        store(estimate_id, archive)
        return archive

def sync_estimates_from_sheet(builder_id=None):
    """Sync estimates and projects from connected Google Sheet into local SQLite."""
    try:
        config = metadata('source_config') or {}
        conn = google_setup.get_connection()
        spreadsheet_id = os.getenv('BUILDSMART_SHEET_ID') or config.get('spreadsheet_id') or conn.get('sheet_id')
        if not spreadsheet_id or not conn.get('refresh_token'):
            return 0

        with google_setup.sheets_session() as client:
            resp = client.get(
                f"{google_setup.SHEETS_URL}/{spreadsheet_id}/values/{TAB}!A2:F",
                timeout=TIMEOUT
            )
            if not resp.ok:
                return 0
            rows = resp.json().get('values', [])
            if not rows:
                return 0

        from services.local_db import connection, read_rows, put_row, now
        with connection() as db:
            profiles = read_rows(db, 'profiles')
            if not builder_id:
                builder_prof = next((p for p in profiles if p.get('role') == 'builder' and 'test' not in p.get('email', '')), None)
                if not builder_prof:
                    builder_prof = next((p for p in profiles if p.get('role') == 'builder'), profiles[0] if profiles else {})
                target_builder_id = builder_prof.get('id', 'default-builder')
            else:
                target_builder_id = builder_id

            existing_estimates = {e['id']: e for e in read_rows(db, 'estimates')}
            all_projects = {p['id']: p for p in read_rows(db, 'projects')}
            existing_projects_by_name = {p['name'].lower(): p for p in all_projects.values()}

            synced_count = 0
            for row in rows:
                if not row or not row[0]:
                    continue
                est_id = str(row[0]).strip()
                proj_name = str(row[1]).strip() if len(row) > 1 and str(row[1]).strip() else 'Untitled Project'
                cust_name = str(row[2]).strip() if len(row) > 2 else ''
                created_at = str(row[3]).strip() if len(row) > 3 and str(row[3]).strip() else now()
                try:
                    total_val = float(str(row[4]).replace(',', '')) if len(row) > 4 and str(row[4]).replace(',', '').strip() else 0.0
                except (ValueError, TypeError):
                    total_val = 0.0
                pdf_url = str(row[5]).strip() if len(row) > 5 else ''

                if est_id not in existing_estimates:
                    proj = existing_projects_by_name.get(proj_name.lower())
                    if not proj:
                        proj_id = str(uuid.uuid4())
                        proj = {
                            'id': proj_id,
                            'builder_id': target_builder_id,
                            'name': proj_name,
                            'location': 'Coimbatore',
                            'building_type': 'Residential Villa',
                            'total_sqft': 1000,
                            'quality': 'Standard',
                            'customer_name': cust_name,
                            'created_at': created_at,
                            'status': 'Draft'
                        }
                        put_row(db, 'projects', proj)
                        existing_projects_by_name[proj_name.lower()] = proj
                        all_projects[proj_id] = proj
                    else:
                        proj_id = proj['id']

                    est = {
                        'id': est_id,
                        'project_id': proj_id,
                        'version': 1,
                        'subtotal': total_val * 0.95,
                        'contingency_pct': 5.0,
                        'contingency_amount': total_val * 0.05,
                        'grand_total': total_val,
                        'generated_at': created_at,
                        'status': 'Draft',
                        'google_archive': {
                            'status': 'archived',
                            'pdf_url': pdf_url,
                            'spreadsheet_id': spreadsheet_id
                        },
                        'input_json': {'customer_name': cust_name, 'name': proj_name, 'builtup_area_sqft': 1000, 'city': 'Coimbatore'},
                        'output_json': {
                            'costs': {'subtotal': total_val * 0.95, 'contingency': total_val * 0.05, 'grandTotal': total_val},
                            'duration': {'min': 3, 'max': 5},
                            'summary': {'customerName': cust_name or proj_name, 'location': 'Coimbatore', 'totalSqft': 1000, 'quality': 'Standard'}
                        }
                    }
                    put_row(db, 'estimates', est)
                    existing_estimates[est_id] = est
                    synced_count += 1
                else:
                    if target_builder_id:
                        est = existing_estimates[est_id]
                        proj_id = est.get('project_id')
                        proj = all_projects.get(proj_id)
                        if proj and proj.get('builder_id') != target_builder_id:
                            user_proj_count = sum(1 for p in all_projects.values() if p.get('builder_id') == target_builder_id)
                            if user_proj_count == 0:
                                proj['builder_id'] = target_builder_id
                                put_row(db, 'projects', proj)
                                all_projects[proj_id] = proj

            return synced_count
    except Exception as exc:
        print(f"sync_estimates_from_sheet error: {exc}", flush=True)
        return 0

