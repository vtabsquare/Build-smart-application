"""Isolated reconstruction checks. No real credentials or external requests."""
import copy
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

TEMP=tempfile.TemporaryDirectory(prefix='buildsmart-tests-')
os.environ['BUILDSMART_DATA_DIR']=TEMP.name
os.environ.pop('GEMINI_API_KEY',None)
os.environ.pop('BREVO_API_KEY',None)
os.environ.pop('BREVO_SENDER_EMAIL',None)
from app import app
from services.local_db import supabase_admin, metadata, connection, read_rows
from runtime_config import SAMPLE_DATA_DIR
from services.sheets_source import DEFAULT_CONFIG, refresh, normalize_tables, validate_config, read_sheet
from services.estimator import calculate_estimate

PASSWORD='TestWorkflow@12345'
PARAMS={'customer_name':'Test Client','customer_email':'client@example.test','name':'Coimbatore test villa',
    'city':'Coimbatore','quality':'Standard','plot_length':50,'plot_width':40,
    'floors_list':[{'floor_name':'Ground Floor','length':30,'width':30}],
    'rooms_list':[{'name':'Bedroom','length':12,'width':10,'doors':[{'qty':1}],'windows':[{'qty':1}]}],
    'contingency_percentage':0}

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING']=True
        cls.client=app.test_client()
        cls.users={}
        for role in ('admin','builder','other'):
            email=role+'@example.test'
            uid=supabase_admin.auth.admin.create_user({'email':email,'password':PASSWORD}).user.id
            supabase_admin.table('profiles').update({'role':'admin' if role=='admin' else 'builder','company_name':role}).eq('id',uid).execute()
            cls.users[role]=uid
    def setUp(self):
        refresh(copy.deepcopy(DEFAULT_CONFIG))
        self.tokens={}
        for role in self.users:
            response=self.client.post('/api/auth/login',json={'email':role+'@example.test','password':PASSWORD})
            self.assertEqual(response.status_code,200,response.get_json())
            self.tokens[role]={'Authorization':'Bearer '+response.get_json()['token']}
    def generate(self,params=None):
        response=self.client.post('/api/estimates/generate',json=params or copy.deepcopy(PARAMS),headers=self.tokens['builder'])
        self.assertEqual(response.status_code,201,response.get_json())
        return response.get_json()
    def config(self):
        config=copy.deepcopy(DEFAULT_CONFIG); config.update(mode='google_sheets',spreadsheet_id='test_spreadsheet_123456789')
        return config
    def tables(self): return json.loads((SAMPLE_DATA_DIR/'masters.json').read_text(encoding='utf-8'))
    def test_auth_and_admin_permissions(self):
        self.assertEqual(self.client.get('/api/projects').status_code,401)
        self.assertEqual(self.client.get('/api/admin/users',headers=self.tokens['builder']).status_code,403)
        self.assertEqual(self.client.get('/api/admin/users',headers=self.tokens['admin']).status_code,200)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'builder@example.test','password':'incorrect'}).status_code,401)
    def test_register_profile_and_login(self):
        payload={'email':'new@example.test','password':PASSWORD,'company_name':'New Builder','phone':'9876543210','city':'Coimbatore'}
        response=self.client.post('/api/auth/register',json=payload)
        self.assertEqual(response.status_code,201,response.get_json())
        response=self.client.post('/api/auth/login',json={'email':payload['email'],'password':PASSWORD})
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(response.get_json()['user']['role'],'builder')
    def test_estimate_math_zero_contingency_and_legacy_area(self):
        result=self.generate()
        self.assertEqual(result['costs']['grandTotal'],900*2400)
        self.assertEqual(result['summary']['totalSqft'],900)
        self.assertEqual(result['costs']['contingencyPct'],0)
        self.assertEqual(calculate_estimate({'totalSqft':1000})['costs']['grandTotal'],2520000)
        self.assertEqual(result['source']['mode'],'sample')
    def test_persistence_history_and_versions(self):
        first=self.generate()
        params=copy.deepcopy(PARAMS); params['project_id']=first['project_id']
        second=self.generate(params)
        self.assertEqual(second['version'],2)
        history=self.client.get('/api/projects',headers=self.tokens['builder']).get_json()['data']
        project=next(p for p in history if p['id']==first['project_id'])
        self.assertEqual(len(project['estimates']),2)
        stored=self.client.get('/api/estimates/'+first['estimate_id'],headers=self.tokens['builder']).get_json()['data']
        self.assertEqual(stored['output_json']['costs']['grandTotal'],first['costs']['grandTotal'])
        self.assertTrue(stored['items'])
    def test_pdf_and_excel_exports(self):
        result=self.generate(); eid=result['estimate_id']
        pdf=self.client.get('/api/estimates/'+eid+'/download-pdf',headers=self.tokens['builder'])
        self.assertEqual(pdf.status_code,200,pdf.get_json() if pdf.is_json else '')
        self.assertTrue(pdf.data.startswith(b'%PDF'))
        excel=self.client.get('/api/estimates/'+eid+'/export/excel',headers=self.tokens['builder'])
        self.assertEqual(excel.status_code,200,excel.get_json() if excel.is_json else '')
        from openpyxl import load_workbook
        workbook=load_workbook(io.BytesIO(excel.data))
        self.assertIn('Estimate Summary',workbook.sheetnames)
    def test_cross_user_access_and_delete_cascade(self):
        result=self.generate(); eid=result['estimate_id']; pid=result['project_id']
        for suffix in ('','/download-pdf','/export/excel'):
            self.assertIn(self.client.get('/api/estimates/'+eid+suffix,headers=self.tokens['other']).status_code,(403,404))
        self.assertEqual(self.client.delete('/api/projects/'+pid,headers=self.tokens['other']).status_code,404)
        self.assertEqual(self.client.delete('/api/projects/'+pid,headers=self.tokens['builder']).status_code,200)
        self.assertFalse(supabase_admin.table('estimates').select('*').eq('project_id',pid).execute().data)
        self.assertFalse(supabase_admin.table('estimate_items').select('*').eq('estimate_id',eid).execute().data)
    def test_bad_input_does_not_create_projects(self):
        before=len(supabase_admin.table('projects').select('*').execute().data)
        for area in (-100,'NaN',0,'Infinity'):
            params=copy.deepcopy(PARAMS); params['floors_list']=[{'area':area}]
            response=self.client.post('/api/estimates/generate',json=params,headers=self.tokens['builder'])
            self.assertEqual(response.status_code,400,response.get_json())
        self.assertEqual(before,len(supabase_admin.table('projects').select('*').execute().data))
    def test_snapshot_refresh_changes_new_estimates_only(self):
        old=self.generate(); config=self.config(); tables=self.tables()
        for row in tables['material_rates']:
            if row['material_code']=='CONSTRUCTION_STANDARD': row['rate']=3000
        with patch('services.sheets_source.read_sheet',side_effect=lambda cfg,spec:tables[spec['sheet']]):
            response=self.client.put('/api/admin/source',json=config,headers=self.tokens['admin'])
        self.assertEqual(response.status_code,200,response.get_json())
        new=self.generate(); self.assertEqual(new['costs']['grandTotal'],900*3000)
        stored=self.client.get('/api/estimates/'+old['estimate_id'],headers=self.tokens['builder']).get_json()['data']
        self.assertEqual(stored['grand_total'],900*2400)
        response=self.client.put('/api/admin/rates/anything',json={'rate':1},headers=self.tokens['admin'])
        self.assertEqual(response.status_code,409)
    def test_failed_refresh_keeps_snapshot(self):
        before=metadata('source_status'); config=self.config()
        with patch('services.sheets_source.read_sheet',side_effect=ValueError('Invalid header')):
            response=self.client.put('/api/admin/source',json=config,headers=self.tokens['admin'])
        self.assertEqual(response.status_code,400)
        self.assertEqual(metadata('source_status'),before)
        self.assertEqual(self.generate()['source']['mode'],'sample')

    def test_project_and_estimate_rollback_when_items_fail(self):
        from services.local_db import Query
        original = Query.execute
        with connection() as db:
            before = {table: len(read_rows(db, table)) for table in ('projects', 'project_floors', 'estimates', 'estimate_items')}

        def fail_items(query):
            if query.table == 'estimate_items' and query.op == 'insert':
                raise RuntimeError('Simulated storage failure')
            return original(query)

        with patch.object(Query, 'execute', fail_items):
            response = self.client.post('/api/estimates/generate', json=PARAMS, headers=self.tokens['builder'])
        self.assertEqual(response.status_code, 500)
        with connection() as db:
            self.assertEqual(before, {table: len(read_rows(db, table)) for table in before})

    def test_export_saved_sheet_estimate_after_source_switch(self):
        tables = self.tables()
        with patch('services.sheets_source.read_sheet', side_effect=lambda cfg, spec: tables[spec['sheet']]):
            refresh(self.config())
        params = {**PARAMS, 'customer_name': 'R & D <Client>', 'project_name': 'House <Phase 1>'}
        estimate = self.generate(params)
        self.assertEqual(estimate['source']['mode'], 'google_sheets')
        refresh(copy.deepcopy(DEFAULT_CONFIG))
        url = '/api/estimates/' + estimate['estimate_id']
        self.assertEqual(self.client.get(url, headers=self.tokens['builder']).get_json()['data']['output_json']['source']['mode'], 'google_sheets')
        for suffix, prefix in (('/download-pdf', b'%PDF'), ('/export/excel', b'PK')):
            response = self.client.get(url + suffix, headers=self.tokens['builder'])
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data.startswith(prefix))
    def test_preview_does_not_activate(self):
        before=metadata('source_status'); config=self.config(); tables=self.tables()
        with patch('services.sheets_source.read_sheet',side_effect=lambda cfg,spec:tables[spec['sheet']]):
            response=self.client.post('/api/admin/source/test',json=config,headers=self.tokens['admin'])
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(metadata('source_status'),before)
    def test_custom_header_mapping_csv_transport(self):
        config=self.config(); spec={'sheet':'Rates Tab','columns':{'city':'Town','material_code':'Item','rate':'Price','vendor':'Supplier'}}
        class Response(io.BytesIO): headers={'Content-Type':'text/csv'}
        with patch('services.sheets_source.urlopen',return_value=Response(b'Town,Item,Price,Supplier\nCoimbatore,CONSTRUCTION_STANDARD,3100,Test\n')) as mock:
            rows=read_sheet(config,spec)
        self.assertEqual(rows[0]['rate'],'3100')
        self.assertEqual(rows[0]['city'],'Coimbatore')
        self.assertIn('sheet=Rates+Tab',mock.call_args.args[0].full_url)
    def test_source_validation(self):
        for invalid in ('NaN','-1','Infinity','bad'):
            tables=self.tables(); tables['material_rates'][0]['rate']=invalid
            with self.assertRaises(ValueError): normalize_tables(tables)
        tables=self.tables(); tables['material_rates'].append(tables['material_rates'][0])
        with self.assertRaises(ValueError): normalize_tables(tables)
        config=self.config(); config['spreadsheet_id']='http://127.0.0.1/secret'
        with self.assertRaises(ValueError): validate_config(config)
    def test_blocked_session_rejected_and_unblocked(self):
        uid=self.users['other']
        response=self.client.put('/api/admin/users/'+uid+'/block',json={},headers=self.tokens['admin'])
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/projects',headers=self.tokens['other']).status_code,403)
        self.client.put('/api/admin/users/'+uid+'/approve',json={},headers=self.tokens['admin'])
    def test_missing_email_configuration_is_explicit(self):
        result=self.generate()
        with patch('requests.post',side_effect=AssertionError('No email may be sent by tests')):
            response=self.client.post('/api/estimates/'+result['estimate_id']+'/share-pdf',json={},headers=self.tokens['builder'])
        self.assertEqual(response.status_code,503)
        self.assertIn('not configured',response.get_json()['error'])

    def test_pdf_email_requires_provider_acceptance_and_contains_pdf(self):
        import base64
        from unittest.mock import Mock
        result = self.generate()
        path = '/api/estimates/' + result['estimate_id'] + '/share-pdf'
        with patch.dict(os.environ, {'BREVO_API_KEY': 'test-key', 'BREVO_SENDER_EMAIL': 'mailer@example.test'}):
            with patch('requests.post', return_value=Mock(status_code=201, **{'json.return_value': {'messageId': 'test-id'}})) as send:
                response = self.client.post(path, json={}, headers=self.tokens['builder'])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['message_id'], 'test-id')
            payload = send.call_args.kwargs['json']
            self.assertEqual(payload['to'][0]['email'], 'client@example.test')
            self.assertTrue(base64.b64decode(payload['attachment'][0]['content']).startswith(b'%PDF'))
            self.assertEqual(send.call_args.kwargs['timeout'], (5, 20))
            with patch('requests.post', return_value=Mock(status_code=401)):
                failure = self.client.post(path, json={}, headers=self.tokens['builder'])
            self.assertEqual(failure.status_code, 502)
            self.assertIn('API key', failure.get_json()['error'])

    def test_password_reset_keeps_only_a_usable_code(self):
        from unittest.mock import Mock
        email = 'reset-mail@example.test'
        supabase_admin.auth.admin.create_user({'email': email, 'password': PASSWORD})
        path = '/api/auth/forgot-password'
        with patch.dict(os.environ, {'BREVO_API_KEY': 'test-key', 'BREVO_SENDER_EMAIL': 'mailer@example.test'}):
            with patch('requests.post', return_value=Mock(status_code=401)):
                self.client.post(path, json={'email': email})
            codes = supabase_admin.table('password_reset_otps').select('*').eq('email', email).execute().data
            self.assertEqual(codes, [])
            with patch('requests.post', return_value=Mock(status_code=201, **{'json.return_value': {'messageId': 'otp-id'}})) as send:
                first = self.client.post(path, json={'email': email})
                second = self.client.post(path, json={'email': email})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.get_json(), first.get_json())
            send.assert_called_once()
            codes = supabase_admin.table('password_reset_otps').select('*').eq('email', email).execute().data
            verified = self.client.post('/api/auth/verify-otp', json={'email': email, 'otp': codes[0]['otp']})
            self.assertEqual(verified.status_code, 200)
            password = 'Replacement-Workflow@123'
            with patch('requests.post', return_value=Mock(status_code=201, **{'json.return_value': {'messageId': 'alert-id'}})):
                reset = self.client.post('/api/auth/reset-password', json={
                    'email': email, 'otp': codes[0]['otp'], 'password': password,
                })
            self.assertEqual(reset.status_code, 200)
            self.assertEqual(self.client.post('/api/auth/login', json={'email': email, 'password': password}).status_code, 200)

    def test_bootstrap_does_not_reset_existing_accounts(self):
        from bootstrap import bootstrap
        with contextlib.redirect_stdout(io.StringIO()): bootstrap()
        with connection() as db:
            first=db.execute('SELECT id,password_hash FROM accounts WHERE email=?',('admin@buildsmart.test',)).fetchone()
        with contextlib.redirect_stdout(io.StringIO()): bootstrap()
        with connection() as db:
            second=db.execute('SELECT id,password_hash FROM accounts WHERE email=?',('admin@buildsmart.test',)).fetchone()
        self.assertEqual(first,second)

    def test_password_reset_revokes_sessions(self):
        user=supabase_admin.auth.admin.create_user({'email':'reset@example.test','password':PASSWORD}).user
        token=supabase_admin.auth.sign_in_with_password({'email':user.email,'password':PASSWORD}).session.access_token
        supabase_admin.auth.admin.update_user_by_id(user.id,{'password':'Replacement@12345'})
        with self.assertRaises(ValueError): supabase_admin.auth.get_user(token)

if __name__=='__main__': unittest.main()
