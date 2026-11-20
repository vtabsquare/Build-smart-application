"""BuildSmart local test server. Operational data stays on this computer."""
import hashlib
import os
import secrets
from flask import Flask, jsonify, redirect, request, send_from_directory
from services.local_db import metadata, get_supabase_user, supabase_admin
from services.email_delivery import email_configured
from runtime_config import WEB_DIR
from routes.setup import local_setup_pending, setup_bp, setup_pending

app=Flask(__name__,static_folder=None)
app.config['MAX_CONTENT_LENGTH']=2*1024*1024
if os.getenv('BUILDSMART_SETUP_TOKEN'):
    app.secret_key = hashlib.sha256(('buildsmart/setup/session/' + os.environ['BUILDSMART_SETUP_TOKEN']).encode()).digest()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '').startswith('https://'))
else:
    app.secret_key = secrets.token_bytes(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '').startswith('https://'))
DIST=WEB_DIR/'dist'

@app.before_request
def validate_request():
    if request.method=='OPTIONS': return '',204
    if request.blueprint == 'setup':
        return None
    if setup_pending():
        if request.path.startswith('/api/'):
            return jsonify({'status':'setup_required','error':'Complete BuildSmart setup first.'}),503
        return redirect('/setup')
    if request.path == '/' and local_setup_pending():
        return redirect('/setup')
    source = metadata('source_status') or {}
    if os.getenv('BUILDSMART_MODE') == 'production' and source.get('mode') != 'google_sheets':
        return jsonify({'status':'not_ready','error':'A validated Google Sheets source is required.'}),503
    if request.path.startswith('/api/') and request.method in ('POST','PUT','PATCH'):
        if request.path!='/api/admin/rates/import' and not request.is_json:
            return jsonify({'error':'Content-Type must be application/json.'}),415
        if request.path!='/api/admin/rates/import' and not isinstance(request.get_json(silent=True),dict):
            return jsonify({'error':'Request body must be a JSON object.'}),400
    public={'/api/health','/api/auth/login','/api/auth/register','/api/auth/forgot-password','/api/auth/verify-otp','/api/auth/reset-password'}
    if request.path.startswith('/api/') and request.path not in public:
        header=request.headers.get('Authorization','')
        if not header.startswith('Bearer '): return jsonify({'error':'Login required.'}),401
        try:
            user=get_supabase_user(header[7:]).user
            profile=supabase_admin.table('profiles').select('*').eq('id',user.id).single().execute().data
        except Exception:
            return jsonify({'error':'Invalid or expired session.'}),401
        if not profile or not profile.get('is_approved'):
            return jsonify({'error':'Account blocked or pending approval.'}),403
    if source.get('mode')=='google_sheets':
        if request.method in ('POST','PUT','DELETE','PATCH') and (
            request.path.startswith('/api/admin/rates') or
            request.path.startswith('/api/admin/settings') or
            request.path.startswith('/api/admin/city-indexes')):
            return jsonify({'error':'Google Sheets is active. Edit the sheet, then refresh Data Source.'}),409

from routes.auth import auth_bp
from routes.projects import projects_bp
from routes.estimates import estimates_bp
from routes.admin import admin_bp
from routes.source import source_bp
for blueprint in (auth_bp,projects_bp,estimates_bp,admin_bp,source_bp,setup_bp):
    app.register_blueprint(blueprint)

@app.route('/api/health')
def health():
    source = metadata('source_status') or {}
    source.pop('spreadsheet_id', None)
    return jsonify({'status':'ok','version':'1.8.0','storage':'local_sqlite',
        'source':source,'ai_configured':bool(os.getenv('GEMINI_API_KEY')),
        'google_setup_available':local_setup_pending(),
        'email_configured':email_configured()})

@app.route('/',defaults={'path':''})
@app.route('/<path:path>')
def frontend(path):
    if path.startswith('api/'): return jsonify({'error':'API endpoint not found.'}),404
    if not DIST.is_dir(): return jsonify({'error':'Frontend build missing. Start with python run.py.'}),503
    if path and (DIST/path).is_file(): return send_from_directory(DIST,path)
    return send_from_directory(DIST,'index.html')

@app.errorhandler(400)
def bad_request(error): return jsonify({'error':'Invalid request.'}),400
@app.errorhandler(413)
def too_large(error): return jsonify({'error':'Request exceeds the 2 MB test limit.'}),413

@app.after_request
def response_headers(response):
    origin=request.headers.get('Origin')
    allowed=os.getenv('CORS_ALLOWED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',')
    if origin in allowed:
        response.headers['Access-Control-Allow-Origin']=origin
        response.headers['Vary']='Origin'
        response.headers['Access-Control-Allow-Headers']='Authorization,Content-Type'
        response.headers['Access-Control-Allow-Methods']='GET,POST,PUT,DELETE,OPTIONS'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy']=(
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self';")
    return response

if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.getenv('FLASK_PORT','5000')),debug=False,use_reloader=False)

