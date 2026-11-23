"""Create first-run local accounts without changing existing users."""
import secrets
import json
import uuid
from services.local_db import supabase_admin, DATA_DIR, connection, read_rows, put_row, now, metadata

REQUESTED_EMAIL = 'vigneshrajas.vtab@gmail.com'
REQUESTED_PASSWORD_HASH = 'scrypt:32768:8:1$O9NAUGz96CwkC0vz$c29db3b4948f10dd2d1a9953f4e1f34fb990c4f8c765068d2de466e9d86df0d0c393b66cc9212a47efd99589d63c09154f072c7ea1d081339b192af2d651f6cd'
LOGIN_MIGRATION = 'requested-builder-login-20261118'

PUBLIC_DEMO_EMAIL = 'vtabpublicuser@gmail.com'
PUBLIC_DEMO_PASSWORD_HASH = 'scrypt:32768:8:1$pBndVbmsC3dAByRw$05450ac43a7516131858e7c4499b097e0be341dcafe1beab7e73b20bea0964786b45de9f3e7dc6562c4176cec8404479a71e6e9de98dcdbe4a3c511e6bc72406'

def configure_public_demo_user():
    """Ensure vtabpublicuser@gmail.com account and VTabdemo profile exist."""
    with connection() as db:
        account = db.execute('SELECT id FROM accounts WHERE email=?', (PUBLIC_DEMO_EMAIL,)).fetchone()
        profile = next((r for r in read_rows(db, 'profiles') if r.get('email') == PUBLIC_DEMO_EMAIL), {})
        uid = account[0] if account else profile.get('id', str(uuid.uuid4()))
        if account:
            db.execute('UPDATE accounts SET password_hash=? WHERE id=?', (PUBLIC_DEMO_PASSWORD_HASH, uid))
        else:
            db.execute('INSERT INTO accounts VALUES(?,?,?)', (uid, PUBLIC_DEMO_EMAIL, PUBLIC_DEMO_PASSWORD_HASH))
        put_row(db, 'profiles', {
            **profile,
            'id': uid,
            'email': PUBLIC_DEMO_EMAIL,
            'role': 'builder',
            'company_name': 'VTabdemo',
            'city': 'COIMBATORE',
            'phone': '9876543210',
            'is_approved': True,
            'failed_login_attempts': 0,
            'locked_until': None,
            'created_at': profile.get('created_at') or now(),
            'password_changed_at': now()
        })

def configure_requested_login():
    """Apply the requested local login once; preserve later password changes."""
    with connection() as db:
        if db.execute('SELECT value FROM metadata WHERE key=?', (LOGIN_MIGRATION,)).fetchone():
            return
        account = db.execute('SELECT id FROM accounts WHERE email=?', (REQUESTED_EMAIL,)).fetchone()
        profile = next((r for r in read_rows(db, 'profiles') if r.get('email') == REQUESTED_EMAIL), {})
        uid = account[0] if account else profile.get('id', str(uuid.uuid4()))
        if account:
            db.execute('UPDATE accounts SET password_hash=? WHERE id=?', (REQUESTED_PASSWORD_HASH, uid))
        else:
            db.execute('INSERT INTO accounts VALUES(?,?,?)', (uid, REQUESTED_EMAIL, REQUESTED_PASSWORD_HASH))
        put_row(db, 'profiles', {**profile, 'id': uid, 'email': REQUESTED_EMAIL,
            'role': 'builder', 'company_name': profile.get('company_name') or 'Vtab square',
            'city': profile.get('city') or 'Coimbatore', 'phone': profile.get('phone', ''),
            'is_approved': True, 'failed_login_attempts': 0, 'locked_until': None,
            'created_at': profile.get('created_at') or now(), 'password_changed_at': now()})
        db.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
        db.execute('INSERT INTO metadata VALUES(?,?)', (LOGIN_MIGRATION, json.dumps(True)))

def bootstrap():
    configure_requested_login()
    configure_public_demo_user()
    print('Your local Builder login is ready:', REQUESTED_EMAIL)
    created=[]
    for role in ('admin','builder'):
        email=role+'@buildsmart.test'
        exists=supabase_admin.table('profiles').select('id').eq('email',email).execute().data
        if exists: continue
        password=secrets.token_urlsafe(12)+'Aa1!'
        user=supabase_admin.auth.admin.create_user({'email':email,'password':password}).user
        supabase_admin.table('profiles').update({'role':role,'company_name':'BuildSmart Test '+role.title(),
            'city':'Coimbatore','is_approved':True}).eq('id',user.id).execute()
        created.append(f'{role.title()}\nEmail: {email}\nPassword: {password}\n')
    accounts=DATA_DIR/'first_run_accounts.txt'
    if created:
        with accounts.open('a',encoding='utf-8') as stream: stream.write('\n'.join(created)+'\n')
        try: accounts.chmod(0o600)
        except OSError: pass
        print('\nFirst-run local test accounts:\n'+'\n'.join(created))
    print('Local test account details:',accounts)

if __name__=='__main__': bootstrap()
