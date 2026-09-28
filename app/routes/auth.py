from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from . import auth_bp
from models.user import users_collection
from firebase_admin import auth as firebase_auth

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
    mode = data.get('mode', 'login')  # 'login' or 'signup'
    
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

