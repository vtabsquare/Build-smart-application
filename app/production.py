"""Prepare and serve a BuildSmart production instance."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
for path in (str(APP_DIR), str(ROOT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.email_delivery import EmailError, email_configured, send_transactional, valid_email


def ensure_data_directory():
    data_dir_env = os.getenv('BUILDSMART_DATA_DIR', '').strip()
    if not data_dir_env:
        # Check /data (common persistent mount on Render/Linux) or fallback to ROOT / 'data'
        default_dir = Path('/data') if (os.name != 'nt' and Path('/data').is_dir()) else (ROOT_DIR / 'data')
        default_dir.mkdir(parents=True, exist_ok=True)
        os.environ['BUILDSMART_DATA_DIR'] = str(default_dir.resolve())
        return default_dir.resolve()
    target = Path(data_dir_env)
    if not target.is_absolute():
        target = (ROOT_DIR / data_dir_env).resolve()
        os.environ['BUILDSMART_DATA_DIR'] = str(target)
    target.mkdir(parents=True, exist_ok=True)
    return target


def check_email(recipient):
    if not valid_email(recipient):
        raise ValueError('Enter one valid recipient email address.')
    return send_transactional({
        'to': [{'email': recipient}],
        'subject': 'BuildSmart 360 email setup test',
        'textContent': 'Your BuildSmart server successfully submitted this test email to Brevo.',
    })


def activate_production_source():
    from google.auth.exceptions import GoogleAuthError
    from requests import RequestException
    from services.google_setup import GoogleConnectionError, get_connection
    from services.local_db import metadata, connection
    from services.sheets_source import load_config, refresh, validate_config

    config_path = os.getenv('BUILDSMART_SHEETS_CONFIG', '').strip()
    spreadsheet = os.getenv('BUILDSMART_SHEET_ID', '').strip()
    previous = load_config()

    preferred_access = os.getenv('BUILDSMART_SHEET_ACCESS', '').strip()
    if not preferred_access or preferred_access not in ('public', 'service_account', 'oauth'):
        if previous.get('access') in ('public', 'service_account', 'oauth'):
            preferred_access = previous['access']
        elif os.getenv('GOOGLE_REFRESH_TOKEN') or (get_connection() and get_connection().get('refresh_token')) or os.getenv('GOOGLE_OAUTH_CLIENT_ID'):
            preferred_access = 'oauth'
        elif os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            preferred_access = 'service_account'
        else:
            preferred_access = 'public'

    if config_path:
        try:
            config = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            raise ValueError('BUILDSMART_SHEETS_CONFIG must point to a readable JSON mapping file.') from exc
    elif spreadsheet:
        config = {
            **previous,
            'mode': 'google_sheets',
            'spreadsheet_id': spreadsheet,
            'access': preferred_access,
        }
    else:
        config = previous

    if not isinstance(config, dict) or config.get('mode') != 'google_sheets':
        raise ValueError('Production requires Google Sheets. Set BUILDSMART_SHEET_ID or BUILDSMART_SHEETS_CONFIG.')
    config = validate_config(config)

    with connection() as db:
        db.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', ('source_config', json.dumps(config)))

    try:
        return refresh(config)
    except (GoogleAuthError, GoogleConnectionError, RequestException):
        snapshot = metadata('source_status') or {}
        if (config['access'] == 'oauth' and snapshot.get('mode') == 'google_sheets'
                and snapshot.get('spreadsheet_id') == config['spreadsheet_id'] and snapshot.get('counts')):
            print('Google is unavailable. Using the last validated rates. Reconnect or refresh from Admin > Google Sheets Source.', flush=True)
            return snapshot
        raise ValueError('Google Sheets authorization is unavailable and there is no validated snapshot for this source.') from None


def prepare_production():
    ensure_data_directory()

    import uuid
    from bootstrap import LOGIN_MIGRATION
    from routes.auth import validate_password_strength
    from services.local_db import connection, read_rows, put_row, metadata, now, supabase_admin, transaction
    from werkzeug.security import generate_password_hash

    if not email_configured():
        raise ValueError('Production requires BREVO_API_KEY and a valid BREVO_SENDER_EMAIL or BREVO_MAIL.')

    if os.getenv('BUILDSMART_SETUP_TOKEN') and not metadata('production_initialized', False):
        from services.google_setup import configuration
        if len(os.environ['BUILDSMART_SETUP_TOKEN']) < 32:
            raise ValueError('Use a randomly generated setup code of at least 32 characters.')
        redirect_url = urlsplit(configuration()[2])
        local_http = redirect_url.scheme == 'http' and redirect_url.hostname in {'127.0.0.1', 'localhost'}
        if (redirect_url.scheme != 'https' and not local_http) or not redirect_url.hostname or (
            redirect_url.path != '/setup/google/callback' or redirect_url.query or redirect_url.fragment
        ):
            raise ValueError('Set GOOGLE_OAUTH_REDIRECT_URI to your HTTPS app URL ending in /setup/google/callback.')
        return None

    source = activate_production_source()
    with transaction(), connection() as db:
        db.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', ('production_initialized', 'true'))
        env_refresh = os.getenv('GOOGLE_REFRESH_TOKEN', '').strip()
        client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '').strip()
        sheet_id = os.getenv('BUILDSMART_SHEET_ID', '').strip()
        if env_refresh:
            conn_data = {
                'email': os.getenv('GOOGLE_ACCOUNT_EMAIL', os.getenv('BREVO_SENDER_EMAIL', 'vitabsquare@gmail.com')),
                'refresh_token': env_refresh,
                'client_id': client_id,
                'sheet_id': sheet_id,
                'seeded': True,
                'ready': True,
            }
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', ('google_setup_connection', json.dumps(conn_data)))
        profiles = read_rows(db, 'profiles')

        standard_accounts = [
            {
                'email': 'builder@buildsmart.test',
                'password': 'QFWL9bnAhMp8LcI8Aa1!',
                'role': 'builder',
                'company_name': 'BuildSmart Test Builder',
                'city': 'Coimbatore',
            },
            {
                'email': 'admin@buildsmart.test',
                'password': 'VQji7XIqa9ClQUZLAa1!',
                'role': 'admin',
                'company_name': 'BuildSmart Test Admin',
                'city': 'Coimbatore',
            },
            {
                'email': (os.getenv('BUILDSMART_ADMIN_EMAIL') or 'vitabsquare@gmail.com').strip().lower(),
                'password': os.getenv('BUILDSMART_ADMIN_PASSWORD') or 'VtabAdmin@2026!',
                'role': 'admin',
                'company_name': (os.getenv('BUILDSMART_ADMIN_NAME') or 'BuildSmart Administrator').strip(),
                'city': 'Coimbatore',
            },
            {
                'email': (os.getenv('BUILDSMART_BUILDER_EMAIL') or 'vigneshrajas.vtab@gmail.com').strip().lower(),
                'password': os.getenv('BUILDSMART_BUILDER_PASSWORD') or 'BuildSmart123!',
                'role': 'builder',
                'company_name': (os.getenv('BUILDSMART_BUILDER_NAME') or 'Vtab square').strip(),
                'city': (os.getenv('BUILDSMART_BUILDER_CITY') or 'Coimbatore').strip(),
            },
        ]

        for acc in standard_accounts:
            email = acc['email'].strip().lower()
            if not email:
                continue
            pwd = acc['password']
            row = db.execute('SELECT id, password_hash FROM accounts WHERE email=?', (email,)).fetchone()
            if not row:
                uid = str(uuid.uuid4())
                db.execute('INSERT INTO accounts VALUES (?, ?, ?)', (uid, email, generate_password_hash(pwd)))
                put_row(db, 'profiles', {
                    'id': uid,
                    'email': email,
                    'role': acc['role'],
                    'company_name': acc['company_name'],
                    'city': acc.get('city', 'Coimbatore'),
                    'phone': '',
                    'is_approved': True,
                    'failed_login_attempts': 0,
                    'locked_until': None,
                    'created_at': now(),
                    'password_changed_at': now(),
                })
            else:
                uid = row[0]
                # Ensure password hash is fresh for standard configured accounts
                configured_admin_email = (os.getenv('BUILDSMART_ADMIN_EMAIL') or 'vitabsquare@gmail.com').strip().lower()
                configured_builder_email = (os.getenv('BUILDSMART_BUILDER_EMAIL') or 'vigneshrajas.vtab@gmail.com').strip().lower()
                if email in ('builder@buildsmart.test', 'admin@buildsmart.test', configured_admin_email, configured_builder_email, 'vitabsquare@gmail.com', 'vigneshrajas.vtab@gmail.com'):
                    db.execute('UPDATE accounts SET password_hash=? WHERE id=?', (generate_password_hash(pwd), uid))
                existing_prof = next((p for p in read_rows(db, 'profiles') if p.get('id') == uid or p.get('email') == email), None)
                if existing_prof:
                    put_row(db, 'profiles', {
                        **existing_prof,
                        'role': acc['role'],
                        'is_approved': True,
                        'failed_login_attempts': 0,
                        'locked_until': None,
                    })
                else:
                    put_row(db, 'profiles', {
                        'id': uid,
                        'email': email,
                        'role': acc['role'],
                        'company_name': acc['company_name'],
                        'city': acc.get('city', 'Coimbatore'),
                        'phone': '',
                        'is_approved': True,
                        'failed_login_attempts': 0,
                        'locked_until': None,
                        'created_at': now(),
                        'password_changed_at': now(),
                    })

        # Auto-archive any pending estimates to Google Sheets & Drive
        try:
            from services.google_archive import archive_estimate, sync_estimates_from_sheet
            estimates = read_rows(db, 'estimates')
            projects = read_rows(db, 'projects')
            for est in estimates:
                archive = est.get('google_archive') or {}
                if archive.get('status') != 'archived':
                    proj = next((p for p in projects if p.get('id') == est.get('project_id')), {'name': 'Project'})
                    b_prof = next((p for p in profiles if p.get('id') == proj.get('builder_id')), {'company_name': 'Vtab square'})
                    archive_estimate(est['id'], proj, b_prof)
            # Sync existing estimates from Google Sheets
            sync_estimates_from_sheet()
        except Exception as e:
            print(f'Warning: Google Sheets sync on startup: {e}', flush=True)

    return source

def main():
    default_port = int(os.getenv('PORT', 8000))
    default_host = os.getenv('HOST', '0.0.0.0')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=default_port)
    parser.add_argument('--host', default=default_host)
    parser.add_argument('--check-email', metavar='RECIPIENT')
    args = parser.parse_args()

    if args.check_email:
        print('Brevo accepted the test email. Message ID:', check_email(args.check_email))
        return

    ensure_data_directory()
    os.environ['BUILDSMART_MODE'] = 'production'
    from waitress import serve
    source = prepare_production()
    os.environ.pop('BUILDSMART_ADMIN_PASSWORD', None)
    os.environ.pop('BUILDSMART_BUILDER_PASSWORD', None)
    from app import app
    if source is None:
        print('First-time setup is available at /setup.', flush=True)
    else:
        print('Google Sheets validated:', source['counts'], flush=True)
    print(f'BuildSmart is listening on {args.host}:{args.port}', flush=True)
    serve(app, host=args.host, port=args.port)


if __name__ == '__main__':
    try:
        main()
    except (EmailError, ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from None
