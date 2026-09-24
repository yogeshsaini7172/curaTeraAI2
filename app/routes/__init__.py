from flask import Blueprint

auth_bp = Blueprint('auth', __name__)
chat_bp = Blueprint('chat', __name__)
profile_bp = Blueprint('profile', __name__)

from . import auth
from . import chat
from . import profile
