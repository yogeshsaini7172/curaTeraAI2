from flask import request, jsonify
from app.utils.auth_middleware import token_required
from models.user import users_collection
from agents.graph import build_graph
from app.utils.profile_helper import get_unified_profile, update_unified_profile
from . import profile_bp

# Build the LangGraph state machine once
graph = build_graph()

@profile_bp.route('/api/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    try:
        # Fetch unified profile directly from LangGraph state
        unified_profile = get_unified_profile(graph, current_user['email'])
        
        user = users_collection.find_one({'email': current_user['email']})
        full_name = unified_profile.get('fullName') or (user.get('fullName') if user else '') or ''

        print("PROFILE: ", unified_profile)
        
        return jsonify({
            'profile': unified_profile,
            'fullName': full_name,
            'email': current_user['email']
        }), 200
        
    except Exception as e:
        print(f"Profile API Error: {e}")
        return jsonify({'message': 'An error occurred fetching the profile.', 'error': str(e)}), 500

@profile_bp.route('/api/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No profile data provided'}), 400
        
    try:
        # Update LangGraph state synchronously
        updated_profile = update_unified_profile(graph, current_user['email'], data)
        
        return jsonify({
            'message': 'Profile updated successfully',
            'profile': updated_profile
        }), 200
        
    except Exception as e:
        print(f"Profile API Error: {e}")
        return jsonify({'message': 'An error occurred updating the profile.', 'error': str(e)}), 500

