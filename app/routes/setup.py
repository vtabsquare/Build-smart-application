"""First-run and administrator Google authorization flows."""
import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from urllib.parse import urlsplit

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from google.auth.exceptions import GoogleAuthError
from requests import RequestException

from routes.auth import validate_password_strength
from services import google_setup
from services.branding import validate_branding
from services.email_delivery import valid_email
from services.local_db import metadata, save_metadata, supabase_admin, transaction
from services.sheets_source import refresh

setup_bp = Blueprint('setup', __name__, url_prefix='/setup')
LOCK = threading.Lock()


def setup_pending():
    return (
        os.getenv('BUILDSMART_MODE') == 'production'
        and bool(os.getenv('BUILDSMART_SETUP_TOKEN'))
        and not metadata('production_initialized', False)
    )


def local_setup_pending():
    return (
        os.getenv('BUILDSMART_MODE') != 'production'
        and request.remote_addr in {'127.0.0.1', '::1'}
        and urlsplit('//' + request.host).hostname in {'127.0.0.1', 'localhost', '::1'}
        and not metadata('local_google_setup_complete', False)
        and not metadata('production_initialized', False)
    )


def allow_setup():
    return setup_pending() or local_setup_pending() or (
        os.getenv('BUILDSMART_MODE') != 'production'
        and request.remote_addr in {'127.0.0.1', '::1'}
        and urlsplit('//' + request.host).hostname in {'127.0.0.1', 'localhost', '::1'}
        and not metadata('production_initialized', False)
    )


def unlocked():
    return session.get('setup_until', 0) > time.time()


def reconnecting():
    return unlocked() and session.get('google_reconnect') is True


def begin_reconnect():
    config = metadata('source_config') or {}
    if config.get('mode') != 'google_sheets':
        raise ValueError('There is no active Google spreadsheet to reconnect.')
    callback = urlsplit(google_setup.configuration()[2])
    if callback.path != '/setup/google/callback' or callback.netloc != request.host:
        raise ValueError('Open BuildSmart at the host in GOOGLE_OAUTH_REDIRECT_URI before reconnecting.')
    start_session()
    session['google_reconnect'] = True
    session['setup_until'] = time.time() + 600
    return url_for('setup.index')


def page(error=None, status=200):
    active = unlocked()
    connection = (metadata('google_setup_connection') or {}) if active else {}
    try:
        current_client = google_setup.configuration()[0]
        oauth_ready = True
    except ValueError:
        current_client = ''
        oauth_ready = False
    if connection.get('client_id') and connection['client_id'] != current_client:
        connection = {}
    sheet = connection.get('sheet_id') if connection.get('ready') else None
    return render_template('setup.html', unlocked=active, sheet=sheet, local=local_setup_pending(),
                           reconnect=reconnecting(),
                           oauth_ready=oauth_ready, redirect_uri=google_setup.redirect_uri(),
                           email=connection.get('email'), csrf=session.get('setup_csrf'), error=error,
                           fields=request.form if active and request.endpoint == 'setup.finish' else {}), status, {'Cache-Control': 'no-store'}


@setup_bp.before_request
def restrict_setup():
    if reconnecting():
        if request.endpoint not in {'setup.index', 'setup.connect', 'setup.google_callback'}:
            abort(404)
    elif not allow_setup():
        return redirect('/login') if request.method == 'GET' else abort(404)
    if request.endpoint not in {'setup.index', 'setup.unlock'} and not unlocked():
        return redirect(url_for('setup.index'))
    if request.method == 'POST' and request.endpoint != 'setup.unlock':
        given = request.form.get('csrf', '')
        expected = session.get('setup_csrf', '')
        if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
            abort(400)


@setup_bp.get('')
def index():
    if not reconnecting() and (local_setup_pending() or (os.getenv('BUILDSMART_MODE') != 'production' and request.remote_addr in {'127.0.0.1', '::1'})):
        callback = urlsplit(google_setup.redirect_uri())
        if callback.scheme == 'http' and callback.hostname in {'127.0.0.1', 'localhost'} and callback.netloc != request.host:
            return redirect(f'http://{callback.netloc}/setup')
        if not unlocked():
            start_session()
        if request.args.get('reconnect') or request.args.get('connect'):
            session['google_reconnect'] = True
    return page()


@setup_bp.post('/unlock')
def unlock():
    if not setup_pending():
        abort(404)
    given = request.form.get('token', '')
    expected = os.environ['BUILDSMART_SETUP_TOKEN']
    if not hmac.compare_digest(given.encode(), expected.encode()):
        return page('The setup code is incorrect.', 403)
    start_session()
    return redirect(url_for('setup.index'), code=303)


def start_session():
    session.clear()
    session['setup_until'] = time.time() + 2700
    session['setup_csrf'] = secrets.token_urlsafe(32)


@setup_bp.post('/connect')
def connect():
    try:
        google_setup.configuration()
        if local_setup_pending():
            callback = urlsplit(google_setup.redirect_uri())
            if callback.scheme != 'http' or callback.hostname not in {'127.0.0.1', 'localhost'} or callback.path != '/setup/google/callback':
                raise ValueError('For local setup, configure an HTTP loopback Google OAuth callback ending in /setup/google/callback.')
    except ValueError as exc:
        return page(str(exc), 400)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    session['google_state'] = state
    session['google_verifier'] = verifier
    return redirect(google_setup.authorization_url(state, challenge), code=303)


def provision(connection):
    target_id = os.getenv('BUILDSMART_SHEET_ID') or connection.get('sheet_id')
    if target_id:
        connection['sheet_id'] = target_id
        save_metadata('google_setup_connection', connection)
        google_setup.setup_spreadsheet(connection, target_id)
        connection['seeded'] = True
    else:
        if not connection.get('sheet_id'):
            connection['sheet_id'] = google_setup.create_template(connection)
            save_metadata('google_setup_connection', connection)
        if not connection.get('seeded'):
            google_setup.seed_template(connection)
            connection['seeded'] = True
    save_metadata('google_setup_connection', connection)
    refresh({'mode': 'google_sheets', 'access': 'oauth', 'spreadsheet_id': connection['sheet_id']})
    connection['ready'] = True
    save_metadata('google_setup_connection', connection)


@setup_bp.get('/google/callback')
def google_callback():
    state = session.pop('google_state', '')
    verifier = session.pop('google_verifier', '')
    given = request.args.get('state', '')
    if not state or not verifier or not hmac.compare_digest(given.encode(), state.encode()):
        return page('This Google authorization expired. Start the connection again.', 400)
    code = request.args.get('code')
    if not code:
        return page('Google access was not granted. Connect again to continue.', 400)
    try:
        with LOCK:
            if not (allow_setup() or reconnecting()):
                return redirect('/login')
            connection = google_setup.exchange(code, verifier)
            saved = metadata('google_setup_connection') or {}
            if reconnecting():
                config = metadata('source_config') or {}
                if config.get('mode') != 'google_sheets':
                    raise ValueError('The active Google source changed. Start reconnecting again.')
                # Always prefer BUILDSMART_SHEET_ID from env as the target
                target_sheet = os.getenv('BUILDSMART_SHEET_ID') or config.get('spreadsheet_id')
                google_setup.verify_existing_sheet(connection, target_sheet)
                google_setup.setup_spreadsheet(connection, target_sheet)
                new_conn = {**saved, **connection, 'sheet_id': target_sheet, 'ready': True, 'seeded': True}
                save_metadata('google_setup_connection', new_conn)
                refresh({'mode': 'google_sheets', 'access': 'oauth', 'spreadsheet_id': target_sheet})
                session.clear()
                return redirect('/admin/source?reconnected=1', code=303)
            if saved.get('email') == connection['email'] and saved.get('sheet_id'):
                connection = {**saved, **connection}
            save_metadata('google_setup_connection', connection)
            provision(connection)
    except ValueError as exc:
        return page(str(exc), 400)
    except (GoogleAuthError, RequestException):
        return page('Google could not be reached. Try again in a moment.', 502)
    return redirect(url_for('setup.index'), code=303)


@setup_bp.post('/retry')
def retry():
    try:
        with LOCK:
            if not allow_setup():
                return redirect('/login')
            connection = metadata('google_setup_connection')
            if not connection:
                return redirect(url_for('setup.index'))
            provision(connection)
    except ValueError as exc:
        return page(str(exc), 400)
    except (GoogleAuthError, RequestException):
        return page('Google could not be reached. Try again or reconnect.', 502)
    return redirect(url_for('setup.index'), code=303)


@setup_bp.post('/finish')
def finish():
    try:
        with LOCK, transaction():
            if not allow_setup():
                return redirect('/login')
            connection = metadata('google_setup_connection') or {}
            if not connection.get('ready') or (metadata('source_status') or {}).get('mode') != 'google_sheets':
                raise ValueError('Connect Google and finish creating the Sheet first.')
            branding = validate_branding(request.form, request.files.get('logo'))
            if local_setup_pending():
                save_metadata('company_branding', branding)
                save_metadata('local_google_setup_complete', True)
                session.clear()
                return redirect('/login', code=303)
            email = request.form.get('admin_email', '').strip().lower()
            password = request.form.get('password', '')
            if not valid_email(email):
                raise ValueError('Enter a valid administrator email address.')
            valid, error = validate_password_strength(password)
            if not valid:
                raise ValueError(error)
            user = supabase_admin.auth.admin.create_user({'email': email, 'password': password}).user
            supabase_admin.table('profiles').update({
                'role': 'admin', 'is_approved': True, 'company_name': branding['name'],
            }).eq('id', user.id).execute()
            save_metadata('company_branding', branding)
            save_metadata('production_initialized', True)
    except ValueError as exc:
        return page(str(exc), 400)
    session.clear()
    return redirect('/login', code=303)
