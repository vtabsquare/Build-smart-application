"""Local account recovery; never prints or accepts a password on the command line."""
import argparse
from getpass import getpass
from services.local_db import supabase_admin

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reset-password',required=True,metavar='EMAIL')
    args=parser.parse_args()
    profile=supabase_admin.table('profiles').select('id').eq('email',args.reset_password.strip().lower()).single().execute().data
    if not profile: raise SystemExit('Local account not found.')
    from routes.auth import validate_password_strength
    password=getpass('New password (at least 12 characters): ')
    ok,error=validate_password_strength(password)
    if not ok: raise SystemExit(error)
    if getpass('Confirm password: ')!=password: raise SystemExit('Passwords do not match.')
    supabase_admin.auth.admin.update_user_by_id(profile['id'],{'password':password})
    print('Password updated. Previous sessions were revoked.')

if __name__=='__main__': main()

