import jwt
import os
from functools import wraps
from flask import request, jsonify
from models.user import users_collection
from firebase_admin import auth as firebase_auth
import datetime

SECRET_KEY = os.getenv("JWT_SECRET", "SUPER_SECRET_KEY_CURATERRA_GOV_INDIA_2026_SECURE_TOKEN")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Extract token from the Authorization header (e.g. "Bearer eyJhbGci...")
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split(" ")
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]
            else:
                token = auth_header

        current_user = None

        if token:
            # 1. Try decoding as application HS256 JWT
            try:
                data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                user_email = data.get('email')
                if user_email:
                    current_user = users_collection.find_one({'email': user_email})
                    if not current_user:
                        current_user = {
                            'email': user_email,
                            'name': user_email.split('@')[0],
                            'role': data.get('role', 'user')
                        }
            except Exception:
                pass

            # 2. Try decoding as Firebase ID token (from Google Sign-In)
            if not current_user:
                try:
                    decoded = firebase_auth.verify_id_token(token)
                    fb_email = decoded.get('email') or f"{decoded.get('phone_number', 'citizen').replace('+', '')}@curatera.local"
                    current_user = users_collection.find_one({'email': fb_email})
                    if not current_user:
                        current_user = {
                            'email': fb_email,
                            'name': decoded.get('name', fb_email.split('@')[0]),
                            'role': 'user',
                            'created_at': datetime.datetime.now(datetime.timezone.utc)
                        }
                        users_collection.insert_one(current_user)
                except Exception:
                    pass

        # 3. For chat endpoints: allow guest citizen session if unauthenticated
        if not current_user:
            if request.path.startswith('/api/chat'):
                current_user = {
                    'email': 'guest_citizen@curatera.gov.in',
                    'name': 'Citizen Guest',
                    'role': 'user'
                }
            else:
                return jsonify({'message': 'Authentication required. Token is missing or invalid!'}), 401

        # Pass the current_user to the route
        return f(current_user, *args, **kwargs)

    return decorated
