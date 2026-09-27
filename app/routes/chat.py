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

@chat_bp.route('/api/chat/history', methods=['GET'])
@token_required
def get_chat_history(current_user):
    config = {
        "configurable": {
            "thread_id": current_user['email']
        }
    }
    
    try:
        state = graph.get_state(config)
        messages_history = []
        
        if state and state.values and 'messages' in state.values:
            for msg in state.values['messages']:
                # Depending on how messages are stored (dict or LangChain message object)
                if isinstance(msg, dict):
                    role = "user" if msg.get("role") in ["user", "human"] else "bot"
                    content = msg.get("content", "")
                    msg_id = msg.get("id", f"msg_{len(messages_history)}")
                else:
                    role = "user" if msg.type == "human" else "bot"
                    content = msg.content
                    msg_id = getattr(msg, "id", f"msg_{len(messages_history)}")
                
                # If content is a JSON string of ResponseEnvelope, parse it
                if role == "bot" and isinstance(content, str) and content.strip().startswith("{"):
                    try:
                        import json
                        parsed_content = json.loads(content)
                        if "message" in parsed_content:
                            content = parsed_content["message"]
                    except:
                        pass
                        
                messages_history.append({
                    "id": str(msg_id) if msg_id else f"msg_{len(messages_history)}",
                    "sender": role,
                    "text": content,
                })
                
        return jsonify({'messages': messages_history}), 200
        
    except Exception as e:
        print(f"History Error: {e}")
        return jsonify({'error': str(e)}), 500
