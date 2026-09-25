from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from . import auth_bp
from models.user import users_collection

SECRET_KEY = "SUPER_SECRET_KEY"  # Replace with environment variable in production

@auth_bp.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No JSON payload provided'}), 400

    email = data.get('email')
    password = data.get('password')

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
        'password': hashed_password,
        'role':'user',
        'created_at': datetime.datetime.now(datetime.timezone.utc)
    }

    # Save to MongoDB
    users_collection.insert_one(new_user)
    return jsonify({'message': 'User created successfully'}), 201

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
    token = jwt.encode({
        'email': user['email'],
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=20)
    }, SECRET_KEY, algorithm="HS256")

    #store fcm token of user
    users_collection.update_one({'email': email}, {'$set': {'fcm_token': fcm_token}})

    return jsonify({'token': token, 'message': 'Login successful'}), 200
