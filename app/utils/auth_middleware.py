import jwt
from functools import wraps
from flask import request, jsonify
from app.routes.auth import SECRET_KEY
from models.user import users_collection

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

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            # Decode the JWT
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            # Fetch the current user from the database
            current_user = users_collection.find_one({'email': data['email']})
            if not current_user:
                return jsonify({'message': 'Token is invalid: User does not exist!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except Exception as e:
            return jsonify({'message': 'Token is invalid!'}), 401

        # Pass the current_user to the route
        return f(current_user, *args, **kwargs)

    return decorated
