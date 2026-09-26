from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file

from app.routes import auth_bp, chat_bp, profile_bp
from app.routes.schemes import schemes_bp
from app.routes.tts import tts_bp

app = Flask(__name__)
# Enable CORS for all routes so the frontend can connect
CORS(app)

# Register API blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(schemes_bp)
app.register_blueprint(tts_bp)

@app.route('/')
def home():
    return {"message": "Welcome to CuraTerra API Server"}

if __name__ == '__main__':
    print("Starting CuraTerra API Server on port 5000...")
    app.run(debug=True, host='0.0.0.0', port=5000)
