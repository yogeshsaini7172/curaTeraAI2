from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from . import auth_bp
from models.user import users_collection
from firebase_admin import auth as firebase_auth

import random
import string
from app.utils.email_service import send_welcome_email, send_otp_email

SECRET_KEY = "SUPER_SECRET_KEY"  # Replace with environment variable in production

@auth_bp.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No JSON payload provided'}), 400

    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name') or data.get('name') or (email.split('@')[0] if email else 'User')

    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400

    # Check if user already exists
    existing_user = users_collection.find_one({'email': email})
    if existing_user:
        return jsonify({'message': 'User already exists'}), 409

    # Hash the password
    hashed_password = generate_password_hash(password)
    new_user = {
        'email': email,
        'name': full_name,
        'password': hashed_password,
        'role':'user',
        'created_at': datetime.datetime.now(datetime.timezone.utc)
    }

    # Save to MongoDB
    users_collection.insert_one(new_user)

    # Send Welcome Email via SMTP
    try:
        send_welcome_email(email, full_name)
    except Exception as err:
        print("Welcome email trigger failed:", err)

    return jsonify({'message': 'User created successfully', 'user': {'email': email, 'name': full_name}}), 201

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No JSON payload provided'}), 400

    email = data.get('email')
    password = data.get('password')
    fcm_token = data.get('fcm_token')

    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400

    # Find the user by email
    user = users_collection.find_one({'email': email})
    
    # Check if user exists and password is correct
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'message': 'Invalid credentials'}), 401

    # Generate JWT Token
    role = user.get('role', 'user')
    token = jwt.encode({
        'email': user['email'],
        'role': role,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=20)
    }, SECRET_KEY, algorithm="HS256")

    if fcm_token:
        users_collection.update_one({'email': email}, {'$set': {'fcm_token': fcm_token}})

    return jsonify({
        'token': token,
        'message': 'Login successful',
        'user': {
            'email': user['email'],
            'name': user.get('name', user['email'].split('@')[0])
        },
        'email': user['email'],
        'role': role
    }), 200

@auth_bp.route('/api/auth/firebase', methods=['POST'])
def firebase_login():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No JSON payload provided'}), 400

    id_token = data.get('id_token')
    fcm_token = data.get('fcm_token')
    mode = data.get('mode', 'auto')  # Default to 'auto' mode (auto-login if exists, auto-register if new)
    
    if not id_token:
        return jsonify({'message': 'Missing Firebase ID token'}), 400
        
    try:
        # Verify the Firebase token
        decoded_token = firebase_auth.verify_id_token(id_token)
        
        # Get email or phone number
        email = decoded_token.get('email')
        phone_number = decoded_token.get('phone_number')
        name = decoded_token.get('name', 'Citizen')
        
        if not email and not phone_number:
            return jsonify({'message': 'No email or phone number found in token'}), 400
            
        if not email:
            email = f"{phone_number.replace('+', '')}@curatera.local"
            
        # Check if user exists
        user = users_collection.find_one({'email': email})
        
        if mode == 'login':
            # LOGIN MODE: user must already exist
            if not user:
                return jsonify({'message': 'No account found with this Google account. Please register first.'}), 404
            # Update fcm_token if changed
            if fcm_token:
                users_collection.update_one({'_id': user['_id']}, {'$set': {'fcm_token': fcm_token}})
                
        elif mode == 'signup':
            # SIGNUP MODE: user must NOT already exist
            if user:
                return jsonify({'message': 'This Google account is already registered. Please Sign In instead.'}), 409
            # Register new user
            new_user = {
                'email': email,
                'phone': phone_number or '',
                'name': name,
                'password': '',  # No password needed for OAuth
                'role': 'user',
                'created_at': datetime.datetime.now(datetime.timezone.utc),
                'fcm_token': fcm_token
            }
            users_collection.insert_one(new_user)
            user = new_user
            # Send confirmation/welcome email on Google Signup
            try:
                send_welcome_email(email, name)
            except Exception as ge:
                print("Google Signup email error:", ge)
        else:
            # Fallback: auto mode (register if not exists, login if exists)
            if not user:
                new_user = {
                    'email': email,
                    'phone': phone_number or '',
                    'name': name,
                    'password': '',
                    'role': 'user',
                    'created_at': datetime.datetime.now(datetime.timezone.utc),
                    'fcm_token': fcm_token
                }
                users_collection.insert_one(new_user)
                user = new_user
                try:
                    send_welcome_email(email, name)
                except Exception as ge:
                    print("Google Signup email error:", ge)
            elif fcm_token:
                users_collection.update_one({'_id': user['_id']}, {'$set': {'fcm_token': fcm_token}})
            
        # Generate our own JWT Token so the rest of the app works identically
        role = user.get('role', 'user')
        token = jwt.encode({
            'email': user['email'],
            'role': role,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=20)
        }, SECRET_KEY, algorithm="HS256")
        
        return jsonify({
            'token': token,
            'message': 'Firebase login successful',
            'user': {
                'email': user['email'],
                'phone': user.get('phone', ''),
                'name': user.get('name', 'Citizen')
            },
            'email': user['email'],
            'role': role
        }), 200

    except Exception as e:
        print("Firebase token verification error:", e)
        return jsonify({'message': f'Invalid token: {str(e)}'}), 401


@auth_bp.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({'message': 'Email is required'}), 400

    email = data.get('email').strip().lower()
    user = users_collection.find_one({'email': email})
    
    if not user:
        # For security, return success message even if email not registered
        return jsonify({'message': 'If an account exists with this email, an OTP has been sent.'}), 200

    # Generate 6-digit OTP
    otp_code = ''.join(random.choices(string.digits, k=6))
    expiry_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)

    # Save OTP to MongoDB user record
    users_collection.update_one(
        {'email': email},
        {'$set': {'reset_otp': otp_code, 'otp_expiry': expiry_time}}
    )

    # Send OTP email asynchronously
    send_otp_email(email, otp_code, purpose="Password Reset")

    return jsonify({'message': 'If an account exists with this email, an OTP has been sent.'}), 200


@auth_bp.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No JSON payload provided'}), 400

    email = data.get('email', '').strip().lower()
    otp_code = data.get('otp', '').strip()

    if not email or not otp_code:
        return jsonify({'message': 'Email and OTP code are required'}), 400

    user = users_collection.find_one({'email': email})
    if not user:
        return jsonify({'message': 'Invalid request or user not found'}), 400

    saved_otp = user.get('reset_otp')
    otp_expiry = user.get('otp_expiry')

    if not saved_otp or saved_otp != otp_code:
        return jsonify({'message': 'Invalid OTP code. Please check and try again.'}), 400

    if otp_expiry:
        if isinstance(otp_expiry, datetime.datetime) and otp_expiry.tzinfo is None:
            otp_expiry = otp_expiry.replace(tzinfo=datetime.timezone.utc)
        
        if datetime.datetime.now(datetime.timezone.utc) > otp_expiry:
            return jsonify({'message': 'OTP code has expired. Please request a new one.'}), 400

    return jsonify({'success': True, 'message': 'OTP verified successfully. Please enter your new password.'}), 200


@auth_bp.route('/api/auth/reset-password', methods=['POST'])

def reset_password():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No JSON payload provided'}), 400

    email = data.get('email', '').strip().lower()
    otp_code = data.get('otp', '').strip()
    new_password = data.get('new_password', '')

    if not email or not otp_code or not new_password:
        return jsonify({'message': 'Email, OTP code, and new password are required'}), 400

    user = users_collection.find_one({'email': email})
    if not user:
        return jsonify({'message': 'Invalid request'}), 400

    saved_otp = user.get('reset_otp')
    otp_expiry = user.get('otp_expiry')

    if not saved_otp or saved_otp != otp_code:
        return jsonify({'message': 'Invalid OTP code'}), 400

    if otp_expiry:
        # Ensure aware datetime comparison
        if isinstance(otp_expiry, datetime.datetime) and otp_expiry.tzinfo is None:
            otp_expiry = otp_expiry.replace(tzinfo=datetime.timezone.utc)
        
        if datetime.datetime.now(datetime.timezone.utc) > otp_expiry:
            return jsonify({'message': 'OTP code has expired. Please request a new one.'}), 400

    # Update password and clear OTP
    hashed_password = generate_password_hash(new_password)
    users_collection.update_one(
        {'email': email},
        {
            '$set': {'password': hashed_password},
            '$unset': {'reset_otp': '', 'otp_expiry': ''}
        }
    )

    return jsonify({'message': 'Password reset successful. You can now login with your new password.'}), 200


