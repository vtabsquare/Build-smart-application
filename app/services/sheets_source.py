"""Read-only Google Sheets master-data import with configurable column mapping."""
import csv
import io
import json
import math
import os
import re
import threading
import uuid
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from services.local_db import DATA_DIR, MASTER_TABLES, metadata, replace_masters, now
from runtime_config import SAMPLE_DATA_DIR

SOURCE_LOCK = threading.RLock()
FIELDS = {
    'material_rates':['city','material_code','rate','vendor'],
    'material_master':['code','name','category','unit'],
    'system_settings':['key','value'],
    'city_indexes':['city','state','cost_index'],
}
DEFAULT_CONFIG = {'mode':'sample','access':'public','spreadsheet_id':'',
    'tables':{table:{'sheet':table,'columns':{k:k for k in fields}} for table,fields in FIELDS.items()}}

def load_config():
    return metadata('source_config') or json.loads(json.dumps(DEFAULT_CONFIG))

def validate_config(config):
    if not isinstance(config,dict): raise ValueError('Configuration must be a JSON object')
    if config.get('mode') not in ('sample','google_sheets'): raise ValueError('Choose sample or google_sheets mode')
    clean={'mode':config['mode'],'access':config.get('access','public'),'spreadsheet_id':str(config.get('spreadsheet_id','')).strip(),'tables':{}}
    if clean['access'] not in ('public','service_account','oauth'): raise ValueError('Unknown access mode')
    match=re.search(r'/spreadsheets/d/([A-Za-z0-9_-]+)',clean['spreadsheet_id'])
    if match: clean['spreadsheet_id']=match.group(1)
    if clean['mode']=='google_sheets' and not re.fullmatch(r'[A-Za-z0-9_-]{15,150}',clean['spreadsheet_id']): raise ValueError('Enter a valid spreadsheet ID or URL')
    tables=config.get('tables',{})
    if not isinstance(tables,dict): raise ValueError('tables must be an object')
    for table,fields in FIELDS.items():
        spec=tables.get(table,{})
        if not isinstance(spec,dict): raise ValueError('Invalid mapping for '+table)
        sheet=spec.get('sheet',table)
        columns=spec.get('columns',{k:k for k in fields})
        if not isinstance(sheet,str) or not sheet.strip() or len(sheet)>100: raise ValueError('Invalid tab name for '+table)
        if not isinstance(columns,dict) or set(columns)!=set(fields): raise ValueError('Map all canonical columns for '+table+': '+', '.join(fields))
        if any(not isinstance(v,str) or not v.strip() for v in columns.values()): raise ValueError('Column names cannot be blank')
        if len(set(columns.values()))!=len(fields): raise ValueError('Column mappings must be unique')
        clean['tables'][table]={'sheet':sheet.strip(),'columns':{k:v.strip() for k,v in columns.items()}}
    return clean

def read_sheet(config, spec):
    sid=config['spreadsheet_id']
    if config['access']=='public':
        url='https://docs.google.com/spreadsheets/d/'+sid+'/gviz/tq?'+urlencode({'tqx':'out:csv','sheet':spec['sheet']})
        try:
            with urlopen(Request(url,headers={'User-Agent':'BuildSmart-Test/1.1'}),timeout=25) as response:
                raw=response.read(5*1024*1024+1)
                if len(raw)>5*1024*1024: raise ValueError('Sheet exceeds 5 MB test limit')
                if 'text/html' in response.headers.get('Content-Type',''): raise ValueError('Google returned a sign-in page. Check sharing permissions')
                text=raw.decode('utf-8-sig')
        except ValueError: raise
        except Exception as exc: raise ValueError('Cannot read tab '+spec['sheet']+'. Check the spreadsheet ID, sharing permissions and internet connection.') from exc
        if text.lstrip().startswith('<'): raise ValueError('Google returned HTML instead of CSV')
        grid=list(csv.reader(io.StringIO(text)))
    else:
        if config['access'] == 'oauth':
            from services.google_setup import sheets_session
            session = sheets_session()
        else:
            from google.oauth2 import service_account
            from google.auth.transport.requests import AuthorizedSession
            path=os.getenv('GOOGLE_APPLICATION_CREDENTIALS','')
            if not path or not Path(path).is_file(): raise ValueError('Set GOOGLE_APPLICATION_CREDENTIALS to the service-account JSON path in .env')
            credentials=service_account.Credentials.from_service_account_file(path,scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            session = AuthorizedSession(credentials)
        with session:
            range_name="'"+spec['sheet'].replace("'","''")+"'"
            response=session.get('https://sheets.googleapis.com/v4/spreadsheets/'+sid+'/values/'+quote(range_name,safe=''),params={'valueRenderOption':'UNFORMATTED_VALUE'},timeout=25)
            if response.status_code!=200: raise ValueError('Cannot read tab '+spec['sheet']+'. Check that the connected Google account can access the sheet and the Sheets API is enabled.')
            grid=response.json().get('values',[])
    if not grid: raise ValueError('Empty sheet: '+spec['sheet'])
    header=[str(x).strip() for x in grid[0]]
    if len(header)!=len(set(header)): raise ValueError('Duplicate headers in '+spec['sheet'])
    missing=set(spec['columns'].values())-set(header)
    if missing: raise ValueError('Missing headers in '+spec['sheet']+': '+', '.join(sorted(missing)))
    indexes={k:header.index(v) for k,v in spec['columns'].items()}
    return [{k:(str(row[i]).strip() if i<len(row) else '') for k,i in indexes.items()}
            for row in grid[1:] if any(str(cell).strip() for cell in row)]

def finite_number(value,label):
    try: number=float(str(value).replace(',',''))
    except (TypeError,ValueError): raise ValueError(label+' must be a number') from None
    if not math.isfinite(number) or number<0: raise ValueError(label+' must be finite and non-negative')
    return number

def normalize_tables(tables):
    result={}
    for table in FIELDS:
        rows=tables.get(table)
        if not isinstance(rows,list) or not rows: raise ValueError('At least one data row is required in '+table)
        if len(rows)>20000: raise ValueError('Too many rows in '+table)
        seen=set(); output=[]
        for i, original in enumerate(rows,2):
            row={k:str(original.get(k,'')).strip() for k in FIELDS[table]}
            label=table+' row '+str(i)
            optional={'vendor','state'}
            if any(not row[k] for k in row if k not in optional): raise ValueError(label+': required field is blank')
            if table=='material_rates':
                row['material_code']=row['material_code'].upper()
                row['rate']=finite_number(row['rate'],label+' rate')
                key=(row['city'],row['material_code'])
            elif table=='material_master': row['code']=row['code'].upper(); key=(row['code'],)
            elif table=='city_indexes':
                row['cost_index']=finite_number(row['cost_index'],label+' cost_index')
                if row['cost_index']==0: raise ValueError(label+': index must be positive')
                key=(row['city'],)
            else:
                key=(row['key'],)
                if row['key'].startswith('include_'):
                    row['value']=row['value'].lower()
                    if row['value'] not in ('true','false'): raise ValueError(label+': inclusion must be true or false')
                elif row['key'].startswith('rate_') or row['key'].endswith('_pct'):
                    row['value']=str(finite_number(row['value'],label+' value'))
            if key in seen: raise ValueError(label+': duplicate key '+str(key))
            seen.add(key)
            row['id']=str(uuid.uuid5(uuid.NAMESPACE_URL,table+json.dumps(key)))
            output.append(row)
        result[table]=output
    codes={r['code'] for r in result['material_master']}
    for row in result['material_rates']:
        if row['material_code'] not in codes: raise ValueError('Unknown material code: '+row['material_code'])
    for quality in ('BASE','STANDARD','PREMIUM','LUXURY'):
        if not any(r['city']=='Default' and r['material_code']=='CONSTRUCTION_'+quality for r in result['material_rates']):
            raise ValueError('Add a Default city construction rate for '+quality)
    return result

def refresh(config=None, publish=True):
    config=validate_config(config or load_config())
    if os.getenv('BUILDSMART_MODE') == 'production' and config['mode'] != 'google_sheets':
        raise ValueError('Production requires a Google Sheets source. Sample rates are disabled.')
    with SOURCE_LOCK:
        if config['mode']=='sample':
            tables=normalize_tables(json.loads((SAMPLE_DATA_DIR/'masters.json').read_text(encoding='utf-8')))
        else:
            tables=normalize_tables({table:read_sheet(config,spec) for table,spec in config['tables'].items()})
        status={'mode':config['mode'],'access':config['access'],'spreadsheet_id':config['spreadsheet_id'],
            'updated_at':now(),'counts':{table:len(rows) for table,rows in tables.items()},
            'label':'Validated Google Sheets snapshot' if config['mode']=='google_sheets' else 'Bundled sample data - not live market rates'}
        if publish:
            # All tables remain unchanged if fetching or validation fails.
            replace_masters(tables,status,config)
        return status
