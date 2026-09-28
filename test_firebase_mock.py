from unittest.mock import patch
from flask import Flask
from app.routes import auth_bp
from models.user import users_collection

app = Flask(__name__)
app.register_blueprint(auth_bp)

def test():
    with patch('app.routes.auth.firebase_auth.verify_id_token') as mock_verify:
        mock_verify.return_value = {
            'email': 'mockuser@example.com',
            'name': 'Mock User'
        }
        users_collection.delete_one({'email': 'mockuser@example.com'})
        
        with app.test_client() as c:
            rv = c.post('/api/auth/firebase', json={'id_token': 'dummy', 'mode': 'signup'})
            print(rv.status_code, rv.data)

test()
