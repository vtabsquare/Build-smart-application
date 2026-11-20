"""Load server settings without logging credential values."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
WEB_DIR = APP_DIR / 'web'
SAMPLE_DATA_DIR = APP_DIR / 'sample_data'
KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
TEMPLATE_VALUES = {
    'GOOGLE_OAUTH_CLIENT_ID': 'PASTE_GOOGLE_CLIENT_ID_HERE',
    'GOOGLE_OAUTH_CLIENT_SECRET': 'PASTE_GOOGLE_CLIENT_SECRET_HERE',
    'BREVO_API_KEY': 'PASTE_BREVO_API_KEY_HERE',
    'BREVO_SENDER_EMAIL': 'PASTE_VERIFIED_SENDER_EMAIL_HERE',
}


def read_env(path):
    entries = {}
    if not path.is_file():
        return entries
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.removeprefix('export ').partition('=')
        key, value = key.strip(), value.strip()
        if not separator or not KEY.fullmatch(key):
            raise ValueError(f'{path}:{number}: expected NAME=value.')
        if value.startswith(('"', "'")):
            closing = value.rfind(value[0])
            tail = value[closing + 1:].strip()
            if closing == 0 or (tail and not tail.startswith('#')):
                raise ValueError(f'{path}:{number}: check the quotes around {key}.')
            value = value[1:closing]
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].rstrip()
        entries[key] = value
    return entries


def load_environment(env_file=None):
    paths = [ROOT / 'backend' / '.env', ROOT / '.env']
    if env_file is not None:
        path = Path(env_file).resolve()
        if not path.is_file():
            raise ValueError(f'Environment file not found: {path}')
        paths = [path]

    values, origins = {}, {}
    for path in paths:
        entries = read_env(path)
        values.update(entries)
        origins.update(dict.fromkeys(entries, str(path)))
    for key in values:
        if key in os.environ:
            origins[key] = 'process environment'
        else:
            os.environ[key] = values[key]
    return origins


@dataclass(frozen=True)
class GoogleSettings:
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class BrevoSettings:
    api_key: str
    sender_email: str
    sender_name: str


def setting(key):
    value = os.getenv(key, '').strip()
    return '' if value == TEMPLATE_VALUES.get(key) else value


def google_settings():
    callback = setting('GOOGLE_OAUTH_REDIRECT_URI')
    if not callback:
        render_url = os.getenv('RENDER_EXTERNAL_URL', '').rstrip('/')
        if render_url:
            callback = f"{render_url}/setup/google/callback"
        elif setting('BUILDSMART_MODE') != 'production':
            callback = f"http://127.0.0.1:{setting('FLASK_PORT') or '5000'}/setup/google/callback"
    return GoogleSettings(setting('GOOGLE_OAUTH_CLIENT_ID'), setting('GOOGLE_OAUTH_CLIENT_SECRET'), callback)


def brevo_settings():
    return BrevoSettings(setting('BREVO_API_KEY'), setting('BREVO_SENDER_EMAIL') or setting('BREVO_MAIL'),
                         setting('BREVO_SENDER_NAME') or 'BuildSmart 360')


def integration_status(origins):
    keys = ('GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET', 'GOOGLE_OAUTH_REDIRECT_URI',
            'BREVO_API_KEY', 'BREVO_SENDER_EMAIL', 'BREVO_MAIL', 'BREVO_SENDER_NAME', 'GEMINI_API_KEY')
    for key in keys:
        origin = origins.get(key) or ('process environment' if key in os.environ else None)
        name = 'set' if setting(key) else 'placeholder' if key in TEMPLATE_VALUES and os.getenv(key, '').strip() == TEMPLATE_VALUES[key] else 'empty' if origin else 'missing'
        print(f"{key}: {name}" + (f" ({origin})" if origin else ''))
    print('Effective Google callback:', google_settings().redirect_uri or '(missing)')
    sender = 'BREVO_SENDER_EMAIL' if setting('BREVO_SENDER_EMAIL') else 'BREVO_MAIL' if setting('BREVO_MAIL') else '(missing)'
    print('Effective Brevo sender setting:', sender)
