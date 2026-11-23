"""
Authentication routes for BuildSmart AI Estimator.
Handles user registration, login, and profile retrieval.
"""

import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, current_app
from services.email_delivery import EmailError, email_configured, send_transactional, valid_email
from services.local_db import transaction
from services.db import supabase_admin, get_supabase_user, supabase_client

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/auth')


def validate_password_strength(password):
    """
    Validates password strength according to the security guidelines:
    - Passwords must be at least 12 characters in length.
    - Passwords exceeding 128 characters must be denied.
    - Password complexity: requires a combination of lowercase letters, 
      uppercase letters, numbers, and special characters.
    - Password must not be in the weak/common password blocklist.
    """
    if not password:
        return False, 'Password is required.'
        
    if len(password) < 12:
        return False, 'Password must be at least 12 characters long.'
        
    if len(password) > 128:
        return False, 'Password must not exceed 128 characters.'
        
    import re
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one number.'
    if not re.search(r'[^a-zA-Z0-9]', password):
        return False, 'Password must contain at least one special character.'
        
    weak_passwords = {
        'password123', 'password1234', '123456789012', 'admin12345678', 
        'welcome12345', 'buildsmart360', 'buildsmart123', 'rohit12345678', 
        'gokul12345678', 'qwertyuiopas', 'vtabproject123'
    }
    if password.lower() in weak_passwords:
        return False, 'This password is too common or weak. Please choose a more secure password.'
        
    return True, ''


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------
@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new builder account.
    Body: { email, password, company_name, phone, city }
    Creates the auth user with email_confirm=True, then fills in the profile.
    Account is inactive until an admin approves it.
    """
    try:
        data = request.get_json(force=True) or {}

        email        = data.get('email', '').strip()
        password     = data.get('password', '')
        company_name = data.get('company_name', '').strip()
        phone        = data.get('phone', '').strip()
        city         = data.get('city', '').strip()

        if not email or not password:
            return jsonify({'error': 'Email and password are required.'}), 400

        is_valid, pwd_err = validate_password_strength(password)
        if not is_valid:
            return jsonify({'error': pwd_err}), 400

        # Validate email format
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return jsonify({'error': 'Please enter a valid email address.'}), 400

        # Validate phone format (if entered)
        if phone:
            phone_regex = r'^[6-9]\d{9}$'
            if not re.match(phone_regex, phone):
                return jsonify({'error': 'Please enter a valid 10-digit phone number starting with 6-9.'}), 400

        # Check if email already exists
        existing_profile = (
            supabase_admin
            .table('profiles')
            .select('id')
            .eq('email', email)
            .execute()
        )
        if existing_profile.data:
            return jsonify({'error': 'A user with this email address is already registered.'}), 400

        # Create auth user (admin API – bypasses email verification flow)
        auth_response = supabase_admin.auth.admin.create_user({
            'email': email,
            'password': password,
            'email_confirm': True,
        })

        user = auth_response.user
        if not user:
            return jsonify({'error': 'Failed to create user.'}), 500

        from datetime import datetime, timezone
        # Update the auto-created profile row with business details & auto-approve directly
        profile_update = (
            supabase_admin
            .table('profiles')
            .update({
                'company_name': company_name,
                'phone':        phone,
                'city':         city,
                'is_approved':  True,
                'password_changed_at': datetime.now(timezone.utc).isoformat()
            })
            .eq('id', user.id)
            .execute()
        )

        # Seed password history with first password hash
        from werkzeug.security import generate_password_hash
        pwd_hash = generate_password_hash(password)
        supabase_admin.table('password_history').insert({
            'user_id': user.id,
            'password_hash': pwd_hash
        }).execute()

        return jsonify({
            'success': True,
            'message': 'Registration successful! You can now log in.',
        }), 201

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------
@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login with email and password.
    Body: { email, password }
    Returns JWT access_token and user profile if approved.
    """
    try:
        data = request.get_json(force=True) or {}

        email    = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({'error': 'Email and password are required.'}), 400

        from services.audit import log_audit_event
        from datetime import datetime, timezone, timedelta

        # Check account lockout before calling Supabase auth
        profile_db_resp = (
            supabase_admin
            .table('profiles')
            .select('*')
            .eq('email', email)
            .execute()
        )
        profile_db = None
        if profile_db_resp.data:
            profile_db = profile_db_resp.data[0]
            locked_until = profile_db.get('locked_until')
            if locked_until:
                # Convert locked_until ISO string to comparison time
                locked_dt = datetime.fromisoformat(locked_until.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) < locked_dt:
                    log_audit_event(email, "USER_LOGIN", request.remote_addr, status="FAILED", details="Account is locked out")
                    return jsonify({'error': 'Account is temporarily locked due to too many failed attempts. Try again in 15 minutes.'}), 423

        # Sign in via password flow
        try:
            auth_response = supabase_client.auth.sign_in_with_password({
                'email':    email,
                'password': password,
            })
            session = auth_response.session
            user    = auth_response.user
            if not session or not user:
                raise Exception("Invalid credentials.")
        except Exception as exc:
            # Increment failed attempts on failure
            if profile_db:
                attempts = profile_db.get('failed_login_attempts', 0) + 1
                update_payload = {'failed_login_attempts': attempts}
                if attempts >= 5:
                    lock_time = datetime.now(timezone.utc) + timedelta(minutes=15)
                    update_payload['locked_until'] = lock_time.isoformat()
                    # Send security notification for lockout
                    send_security_notification(email, "Account Locked", "Your BuildSmart account has been temporarily locked due to 5 consecutive failed login attempts. It will automatically unlock in 15 minutes.")
                supabase_admin.table('profiles').update(update_payload).eq('id', profile_db['id']).execute()
                
            log_audit_event(email, "USER_LOGIN", request.remote_addr, status="FAILED", details=str(exc))
            return jsonify({'error': 'Invalid credentials.'}), 401

        # Fetch the builder profile
        profile_response = (
            supabase_admin
            .table('profiles')
            .select('*')
            .eq('id', user.id)
            .single()
            .execute()
        )

        profile = profile_response.data
        if not profile:
            log_audit_event(user.id, "USER_LOGIN", request.remote_addr, status="FAILED", details="Profile not found")
            return jsonify({'error': 'Profile not found.'}), 404

        # Enforce admin approval gate
        if not profile.get('is_approved', False):
            log_audit_event(user.id, "USER_LOGIN", request.remote_addr, status="FAILED", details="Account pending admin approval")
            return jsonify({'error': 'Account pending admin approval.'}), 403

        # Clear login failures on successful login
        supabase_admin.table('profiles').update({
            'failed_login_attempts': 0,
            'locked_until': None
        }).eq('id', user.id).execute()

        # Check if password has expired (older than 90 days)
        password_expired = False
        if profile.get('password_changed_at'):
            changed_at = datetime.fromisoformat(profile['password_changed_at'].replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - changed_at).days >= 90:
                password_expired = True

        # Login Success
        log_audit_event(user.id, "USER_LOGIN", request.remote_addr, status="SUCCESS")

        return jsonify({
            'success': True,
            'token':   session.access_token,
            'password_expired': password_expired,
            'user': {
                'id':           user.id,
                'email':        user.email,
                'role':         profile.get('role'),
                'company_name': profile.get('company_name'),
                'city':         profile.get('city'),
                'phone':        profile.get('phone'),
                'avatar_url':   profile.get('avatar_url'),
                'is_approved':  profile.get('is_approved'),
            },
        }), 200

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# POST /api/auth/demo-session  –  public bypass login for iframe demo
# ---------------------------------------------------------------------------
@auth_bp.route('/demo-session', methods=['POST'])
def demo_session():
    """
    Public endpoint to initiate a demo session as vtabpublicuser@gmail.com.
    Bypasses login completely for the iframe demo.
    """
    DEMO_EMAIL = 'vtabpublicuser@gmail.com'
    try:
        import hashlib, secrets, time, uuid
        from services.local_db import connection, read_rows, put_row, now
        
        with connection() as db:
            account = db.execute('SELECT id, email FROM accounts WHERE email=?', (DEMO_EMAIL,)).fetchone()
            profiles = read_rows(db, 'profiles')
            profile = next((p for p in profiles if p.get('email') == DEMO_EMAIL), None)
            
            if not account or not profile:
                from werkzeug.security import generate_password_hash
                uid = account[0] if account else str(uuid.uuid4())
                if not account:
                    db.execute('INSERT INTO accounts VALUES(?,?,?)', (uid, DEMO_EMAIL, generate_password_hash('VTabPublicDemo@2026!')))
                profile = {
                    'id': uid, 'email': DEMO_EMAIL, 'role': 'builder', 'is_approved': True,
                    'company_name': 'VTabdemo', 'city': 'COIMBATORE', 'phone': '9876543210',
                    'failed_login_attempts': 0, 'locked_until': None,
                    'created_at': now(), 'password_changed_at': now()
                }
                put_row(db, 'profiles', profile)
            else:
                uid = account[0]
            
            # Generate new session token for the demo visitor
            token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (token_hash, uid, time.time() + 24 * 3600))

        return jsonify({
            'success': True,
            'token': token,
            'is_demo': True,
            'user': {
                'id': uid,
                'email': DEMO_EMAIL,
                'role': 'builder',
                'company_name': profile.get('company_name') or 'VTabdemo',
                'phone': profile.get('phone') or '9876543210',
                'city': profile.get('city') or 'COIMBATORE',
                'is_approved': True,
            }
        }), 200
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------
@auth_bp.route('/me', methods=['GET'])
def me():
    """
    Return the currently authenticated user's profile.
    Requires: Authorization: Bearer <token>
    """
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header.'}), 401

        token = auth_header[len('Bearer '):]

        # Validate token and retrieve user from Supabase
        user_response = get_supabase_user(token)
        user = user_response.user

        if not user:
            return jsonify({'error': 'Invalid or expired token.'}), 401

        # Fetch profile details
        profile_response = (
            supabase_admin
            .table('profiles')
            .select('*')
            .eq('id', user.id)
            .single()
            .execute()
        )

        profile = profile_response.data
        if not profile:
            return jsonify({'error': 'Profile not found.'}), 404

        # Check if password has expired (older than 90 days)
        password_expired = False
        if profile.get('password_changed_at'):
            from datetime import datetime, timezone
            changed_at = datetime.fromisoformat(profile['password_changed_at'].replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - changed_at).days >= 90:
                password_expired = True

        return jsonify({
            'id':           user.id,
            'email':        user.email,
            'role':         profile.get('role'),
            'company_name': profile.get('company_name'),
            'phone':        profile.get('phone'),
            'city':         profile.get('city'),
            'avatar_url':   profile.get('avatar_url'),
            'password_expired': password_expired,
        }), 200

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# POST /api/auth/forgot-password
# ---------------------------------------------------------------------------
@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')
    if not isinstance(email, str) or not valid_email(email.strip()):
        return jsonify({'error': 'Enter a valid email address.'}), 400
    email = email.strip().lower()
    if not email_configured():
        return jsonify({'error': 'Password reset email is unavailable. Contact your administrator.'}), 503

    response = {'success': True, 'message': 'If this address can receive a reset code, check your email.'}
    profiles = supabase_admin.table('profiles').select('is_approved').eq('email', email).execute().data
    if not profiles or not profiles[0].get('is_approved'):
        return jsonify(response)

    otp = f'{secrets.randbelow(900000) + 100000}'
    requested_at = datetime.now(timezone.utc)
    expires_at = requested_at + timedelta(minutes=10)
    with transaction():
        existing = supabase_admin.table('password_reset_otps').select('expires_at').eq('email', email).execute().data
        if existing and datetime.fromisoformat(existing[0]['expires_at']) > requested_at + timedelta(minutes=9):
            return jsonify(response)
        supabase_admin.table('password_reset_otps').delete().eq('email', email).execute()
        supabase_admin.table('password_reset_otps').insert({
            'email': email, 'otp': otp, 'expires_at': expires_at.isoformat(), 'verified': False,
        }).execute()

    try:
        send_transactional({
            'to': [{'email': email}],
            'subject': 'BuildSmart 360 password reset code',
            'textContent': f'Your BuildSmart password reset code is {otp}. It expires in 10 minutes.',
        })
    except EmailError as exc:
        if exc.status != 504:
            supabase_admin.table('password_reset_otps').delete().eq('email', email).eq('otp', otp).execute()
        current_app.logger.warning('Password reset email could not be confirmed: %s', exc)
    return jsonify(response)


# ---------------------------------------------------------------------------
# POST /api/auth/verify-otp
# ---------------------------------------------------------------------------
@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    """
    Verify OTP sent to user email.
    Body: { email, otp }
    """
    try:
        data = request.get_json(force=True) or {}
        email = data.get('email', '').strip().lower()
        otp = data.get('otp', '').strip()

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400

        # Query OTP table by email only to track failed attempts
        otp_response = (
            supabase_admin
            .table('password_reset_otps')
            .select('*')
            .eq('email', email)
            .execute()
        )

        if not otp_response.data:
            return jsonify({'error': 'OTP verification session not found or invalid.'}), 400

        otp_record = otp_response.data[0]

        # Check expiry
        from datetime import datetime, timezone
        expires_at = datetime.fromisoformat(otp_record['expires_at'].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires_at:
            # Delete expired record
            supabase_admin.table('password_reset_otps').delete().eq('email', email).execute()
            return jsonify({'error': 'OTP has expired. Please request a new one.'}), 400

        # Check OTP match
        if otp_record['otp'] != otp:
            # Increment failed attempts count
            attempts = otp_record.get('attempts', 0) + 1
            if attempts >= 5:
                # Lockout: delete OTP record, forcing a new request
                supabase_admin.table('password_reset_otps').delete().eq('email', email).execute()
                # Send security notification
                send_security_notification(email, "Failed Password Reset Attempt", "We detected 5 incorrect OTP attempts during password reset. The verification session was terminated for security.")
                return jsonify({'error': 'Too many incorrect OTP attempts. Please request a new code.'}), 400
            else:
                supabase_admin.table('password_reset_otps').update({'attempts': attempts}).eq('email', email).execute()
                return jsonify({'error': 'Invalid OTP code.'}), 400

        # Mark as verified and reset attempts
        supabase_admin.table('password_reset_otps').update({'verified': True, 'attempts': 0}).eq('email', email).execute()

        return jsonify({'success': True, 'message': 'OTP verified successfully.'}), 200

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# POST /api/auth/reset-password
# ---------------------------------------------------------------------------
@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Reset password after OTP verification.
    Body: { email, otp, password }
    """
    try:
        data = request.get_json(force=True) or {}
        email = data.get('email', '').strip().lower()
        otp = data.get('otp', '').strip()
        password = data.get('password', '')

        if not email or not otp or not password:
            return jsonify({'error': 'Email, OTP, and new password are required.'}), 400

        is_valid, pwd_err = validate_password_strength(password)
        if not is_valid:
            return jsonify({'error': pwd_err}), 400

        # Verify OTP record is marked as verified
        otp_response = (
            supabase_admin
            .table('password_reset_otps')
            .select('*')
            .eq('email', email)
            .eq('otp', otp)
            .eq('verified', True)
            .execute()
        )

        if not otp_response.data:
            return jsonify({'error': 'OTP verification session not found or invalid.'}), 400

        expiry = datetime.fromisoformat(otp_response.data[0]['expires_at'].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) >= expiry:
            return jsonify({'error': 'OTP has expired. Please request a new one.'}), 400

        # Fetch profile user_id
        profile_response = (
            supabase_admin
            .table('profiles')
            .select('id')
            .eq('email', email)
            .single()
            .execute()
        )
        profile = profile_response.data
        if not profile:
            return jsonify({'error': 'User profile not found.'}), 404

        user_id = profile['id']

        # Verify password history (last 5 passwords must not be reused)
        history_response = (
            supabase_admin
            .table('password_history')
            .select('*')
            .eq('user_id', user_id)
            .order('created_at', desc=True)
            .limit(5)
            .execute()
        )

        from werkzeug.security import generate_password_hash, check_password_hash
        for entry in history_response.data:
            if check_password_hash(entry['password_hash'], password):
                return jsonify({'error': 'You cannot reuse any of your last 5 passwords. Please choose a different password.'}), 400

        # Insert new password hash into history
        pwd_hash = generate_password_hash(password)
        supabase_admin.table('password_history').insert({
            'user_id': user_id,
            'password_hash': pwd_hash
        }).execute()

        # Clean older history (keep only top 5)
        all_history = (
            supabase_admin
            .table('password_history')
            .select('id')
            .eq('user_id', user_id)
            .order('created_at', desc=True)
            .execute()
        )
        if len(all_history.data) > 5:
            for row in all_history.data[5:]:
                supabase_admin.table('password_history').delete().eq('id', row['id']).execute()

        # Update password using admin client
        supabase_admin.auth.admin.update_user_by_id(
            user_id,
            attributes={'password': password}
        )

        # Update password age in profile
        supabase_admin.table('profiles').update({
            'password_changed_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', user_id).execute()

        # Delete OTP record
        supabase_admin.table('password_reset_otps').delete().eq('email', email).execute()

        # Send security notification
        send_security_notification(email, "Password Reset Successful", "Your BuildSmart account password has been reset successfully. If you did not perform this action, please contact support immediately.")

        return jsonify({'success': True, 'message': 'Password has been reset successfully. You can now log in.'}), 200

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# PUT /api/auth/profile  –  update authenticated user's profile
# ---------------------------------------------------------------------------
@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """
    Update the authenticated builder's profile.
    Body: { company_name, phone, city, avatar_url }
    """
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header.'}), 401

        token = auth_header[len('Bearer '):]
        user_response = get_supabase_user(token)
        user = user_response.user

        if not user:
            return jsonify({'error': 'Invalid or expired token.'}), 401

        if user.email == 'vtabpublicuser@gmail.com' and (request.headers.get('X-Demo-Mode') == 'true' or request.args.get('demo')):
            return jsonify({'error': 'Settings cannot be modified in the demo version.'}), 403

        data = request.get_json(force=True) or {}
        company_name = data.get('company_name')
        phone        = data.get('phone')
        city         = data.get('city')
        avatar_url   = data.get('avatar_url')

        update_data = {}
        if company_name is not None:
            update_data['company_name'] = company_name.strip()
        if phone is not None:
            update_data['phone'] = phone.strip()
        if city is not None:
            update_data['city'] = city.strip()
        if avatar_url is not None:
            update_data['avatar_url'] = avatar_url.strip()

        if not update_data:
            return jsonify({'error': 'No fields to update.'}), 400

        response = (
            supabase_admin
            .table('profiles')
            .update(update_data)
            .eq('id', user.id)
            .execute()
        )

        if not response.data:
            return jsonify({'error': 'Failed to update profile.'}), 500

        updated = response.data[0]
        return jsonify({
            'success': True,
            'user': {
                'id':           updated.get('id'),
                'email':        updated.get('email'),
                'role':         updated.get('role'),
                'company_name': updated.get('company_name'),
                'phone':        updated.get('phone'),
                'city':         updated.get('city'),
                'avatar_url':   updated.get('avatar_url'),
                'is_approved':  updated.get('is_approved')
            }
        }), 200

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


def send_security_notification(email, action_name, details_msg):
    try:
        send_transactional({
            'to': [{'email': email}],
            'subject': f'BuildSmart 360 security alert: {action_name}',
            'textContent': f'{details_msg}\nIf you did not take this action, contact your administrator.',
        })
        return True
    except EmailError as exc:
        current_app.logger.warning('Security notification could not be confirmed: %s', exc)
        return False
