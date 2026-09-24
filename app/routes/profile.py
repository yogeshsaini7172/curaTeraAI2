from flask import request, jsonify
from app.utils.auth_middleware import token_required
from agents.graph import build_graph
from . import profile_bp

# Build the LangGraph state machine once
graph = build_graph()

@profile_bp.route('/api/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    config = {
        "configurable": {
            "thread_id": current_user['email']
        }
    }
    
    try:
        # Fetch current state from LangGraph memory
        state = graph.get_state(config)
        
        # Access the current values in the state
        state_values = state.values if state else {}
        citizen_profile = state_values.get("citizen_profile", {})
        
        return jsonify({'profile': citizen_profile}), 200
        
    except Exception as e:
        print(f"Profile API Error: {e}")
        return jsonify({'message': 'An error occurred fetching the profile.', 'error': str(e)}), 500

@profile_bp.route('/api/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No profile data provided'}), 400
        
    config = {
        "configurable": {
            "thread_id": current_user['email']
        }
    }
    
    try:
        # Fetch current state from LangGraph memory
        state = graph.get_state(config)
        state_values = state.values if state else {}
        current_profile = state_values.get("citizen_profile", {})
        
        # Merge new data into existing profile
        updated_profile = {**current_profile, **data}
        
        # We must also ensure any other required state variables are preserved. 
        # Update the state directly into the LangGraph checkpointer.
        graph.update_state(config, {"citizen_profile": updated_profile})
        
        return jsonify({'message': 'Profile updated successfully', 'profile': updated_profile}), 200
        
    except Exception as e:
        print(f"Profile API Error: {e}")
        return jsonify({'message': 'An error occurred updating the profile.', 'error': str(e)}), 500
