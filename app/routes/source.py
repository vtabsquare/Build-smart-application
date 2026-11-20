import os
from flask import Blueprint, request, jsonify
from google.auth.exceptions import GoogleAuthError
from routes.admin import is_admin
from routes.setup import begin_reconnect
from services.sheets_source import load_config, refresh
from services.local_db import metadata, save_metadata
from services import google_setup

source_bp=Blueprint('source_bp',__name__,url_prefix='/api/admin/source')


@source_bp.post('/reconnect')
def reconnect():
    try:
        is_admin(request)
        return jsonify({'data': {'url': begin_reconnect()}})
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

@source_bp.route('',methods=['GET','PUT'])
def configure_source():
    try:
        is_admin(request)
        if request.method=='GET':
            return jsonify({'data':{'config':load_config(),'status':metadata('source_status'),
                'production':os.getenv('BUILDSMART_MODE') == 'production'}})
        config = request.get_json()
        if config.get('access') == 'oauth' and config.get('spreadsheet_id'):
            conn = metadata('google_setup_connection') or {}
            if conn.get('refresh_token'):
                try:
                    google_setup.setup_spreadsheet(conn, config['spreadsheet_id'])
                    conn['sheet_id'] = config['spreadsheet_id']
                    save_metadata('google_setup_connection', conn)
                except Exception:
                    pass
        return jsonify({'data':refresh(config)})
    except PermissionError as exc: return jsonify({'error':str(exc)}),403
    except (ValueError,TypeError,KeyError) as exc: return jsonify({'error':str(exc)}),400
    except Exception: return jsonify({'error':'Source connection failed. Check credentials, permissions and network. The previous snapshot is unchanged.'}),502

@source_bp.route('/test',methods=['POST'])
def test_source():
    try:
        is_admin(request)
        config = request.get_json()
        if config.get('access') == 'oauth' and config.get('spreadsheet_id'):
            conn = metadata('google_setup_connection') or {}
            if conn.get('refresh_token'):
                try:
                    google_setup.setup_spreadsheet(conn, config['spreadsheet_id'])
                except Exception:
                    pass
        return jsonify({'data':refresh(config,publish=False)})
    except PermissionError as exc: return jsonify({'error':str(exc)}),403
    except (ValueError,TypeError,KeyError) as exc: return jsonify({'error':str(exc)}),400
    except Exception: return jsonify({'error':'Unable to connect to Google Sheets. Check credentials and network.'}),502

@source_bp.route('/refresh',methods=['POST'])
def refresh_source():
    try:
        is_admin(request)
        return jsonify({'data':refresh()})
    except PermissionError as exc: return jsonify({'error':str(exc)}),403
    except GoogleAuthError: return jsonify({'error':'Google authorization could not be refreshed. Check the current credentials and use Reconnect Google.'}),502
    except ValueError as exc: return jsonify({'error':str(exc)}),400
    except Exception: return jsonify({'error':'Refresh failed. The previous validated snapshot is unchanged.'}),502
