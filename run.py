"""Run BuildSmart locally or start its production web server."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import venv
import webbrowser

from app.runtime_config import APP_DIR, ROOT, WEB_DIR, integration_status, load_environment


def run_command(arguments, cwd=ROOT, env=None):
    subprocess.run([str(argument) for argument in arguments], cwd=cwd, env=env, check=True)


def prepare_python(use_current_python):
    if use_current_python:
        return Path(sys.executable)

    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        print('Creating the BuildSmart Python environment...', flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)

    requirements = APP_DIR / 'requirements.txt'
    signature = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = environment / '.buildsmart-requirements'
    if not stamp.exists() or stamp.read_text() != signature:
        print('Installing Python dependencies. The first launch requires internet access.', flush=True)
        run_command([python, '-m', 'pip', 'install', '-r', requirements])
        stamp.write_text(signature)
    return python


def prepare_web(rebuild):
    if (WEB_DIR / 'dist' / 'index.html').is_file() and not rebuild:
        return

    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    node = shutil.which('node')
    if not npm or not node:
        raise RuntimeError('Install Node.js 22.12 or newer to rebuild the web interface.')
    version = subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.')
    if tuple(map(int, version[:2])) < (22, 12):
        raise RuntimeError('Use Node.js 22.12 or newer to rebuild the web interface.')

    print('Building the web interface...', flush=True)
    run_command([npm, 'ci', '--no-audit', '--no-fund'], WEB_DIR)
    run_command([npm, 'run', 'build'], WEB_DIR, {**os.environ, 'VITE_API_URL': ''})


def open_when_ready(url):
    from urllib.request import urlopen

    for _ in range(60):
        try:
            with urlopen(url + '/api/health', timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(0.5)


def start_local(python, port, open_browser):
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise RuntimeError(f'Port {port} is unavailable. Try python run.py --port 5050.') from None

    run_command([python, APP_DIR / 'bootstrap.py'])
    url = f'http://127.0.0.1:{port}'
    print(f'BuildSmart is starting at {url}. Press Ctrl+C to stop.', flush=True)
    if open_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()

    server = subprocess.Popen([str(python), str(APP_DIR / 'app.py')], cwd=APP_DIR)
    try:
        if server.wait() != 0:
            raise RuntimeError('BuildSmart stopped unexpectedly. See the error above.')
    except KeyboardInterrupt:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    default_port = int(os.getenv('PORT', 5000))
    default_host = os.getenv('HOST', '127.0.0.1')
    parser.add_argument('--port', type=int, default=default_port)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--rebuild', action='store_true', help='Rebuild the web interface after source edits')
    parser.add_argument('--no-install', action='store_true', help='Use the current Python and its installed dependencies')
    parser.add_argument('--test', action='store_true', help='Run the isolated application tests')
    parser.add_argument('--check', action='store_true', help='Show prerequisites and configuration status')
    parser.add_argument('--env-file', type=Path, help='Use a specific environment file')
    parser.add_argument('--reset-password', metavar='EMAIL', help='Reset a local account password')
    parser.add_argument('--production', action='store_true', help='Start the production web server')
    parser.add_argument('--host', default=default_host, help='Production bind address')
    parser.add_argument('--check-email', metavar='RECIPIENT', help='Send one Brevo test message')
    return parser.parse_args()


def main():
    args = arguments()
    if sys.version_info < (3, 11):
        raise RuntimeError('Install Python 3.11 or newer.')
    origins = load_environment(args.env_file)
    os.environ['FLASK_PORT'] = str(args.port)
    if args.production:
        os.environ['BUILDSMART_MODE'] = 'production'

    if args.check:
        print('Python:', sys.version.split()[0])
        print('Packaged web interface:', 'ready' if (WEB_DIR / 'dist' / 'index.html').is_file() else 'missing')
        integration_status(origins)
        return

    python = prepare_python(args.no_install)
    if args.check_email:
        run_command([python, APP_DIR / 'production.py', '--check-email', args.check_email])
    elif args.test:
        run_command([python, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], APP_DIR)
    elif args.reset_password:
        run_command([python, APP_DIR / 'manage_admin.py', '--reset-password', args.reset_password])
    else:
        if not 1024 <= args.port <= 65535:
            raise ValueError('Choose a port between 1024 and 65535.')
        prepare_web(args.rebuild)
        if os.getenv('BUILDSMART_MODE') == 'production':
            run_command([python, APP_DIR / 'production.py', '--host', args.host, '--port', args.port])
        else:
            start_local(python, args.port, not args.no_browser)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('BuildSmart stopped.')
    except (RuntimeError, ValueError, subprocess.CalledProcessError, OSError) as error:
        print(f'Startup failed: {error}', file=sys.stderr)
        sys.exit(1)
