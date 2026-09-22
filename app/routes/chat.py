from flask import request, jsonify
from app.utils.auth_middleware import token_required
from agents.graph import build_graph
from . import chat_bp

# Build the LangGraph state machine once
graph = build_graph()

@chat_bp.route('/api/chat/message', methods=['POST'])
@token_required
def chat_message(current_user):
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'message': 'No message provided'}), 400

    user_message = data['message']
    
    # We use the authenticated user's email as the thread_id
    # This automatically loads their specific history and citizen_profile from MongoDB
    config = {
        "configurable": {
            "thread_id": current_user['email']
        }
    }

    try:
        # Invoke LangGraph just like in app.py
        result = graph.invoke(
            {"user_query": user_message}, 
            config=config
        )
        
        final_response_dict = result.get("final_response", {})
        
        # If the final_response is a dictionary (from ResponseEnvelope.model_dump), extract it
        if isinstance(final_response_dict, dict):
            ai_message = final_response_dict.get("message", "No message generated.")
            blocks = final_response_dict.get("blocks", [])
            citations = final_response_dict.get("citations", [])
        else:
            ai_message = final_response_dict
            blocks = []
            citations = []

        # Return the AI response without the raw profile data
        return jsonify({
            'message': ai_message,
            'blocks': blocks,
            'citations': citations
        }), 200

    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({'message': 'An error occurred while processing your message.', 'error': str(e)}), 500
