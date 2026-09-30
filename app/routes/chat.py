from flask import request, jsonify
from app.utils.auth_middleware import token_required
from models.user import users_collection
from agents.graph import build_graph
from app.utils.profile_helper import get_unified_profile, update_unified_profile
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
        # Pre-sync: Ensure LangGraph state and MongoDB are 100% unified before invoking the graph
        get_unified_profile(graph, current_user['email'])

        state = graph.get_state(config)
        
        is_pending_verification = False
        if state and state.values:
            if state.values.get("profile_complete") and not state.values.get("identity_verified"):
                is_pending_verification = True

        invoke_data = {"user_query": user_message}
        
        # If they are blocked by verification, treat any chat message as an Aadhaar ID input
        if is_pending_verification:
            invoke_data["identity_verification_input"] = user_message.strip()

        # Invoke LangGraph just like in app.py
        result = graph.invoke(
            invoke_data, 
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

        # The graph's profile_node has already merged and saved the profile
        # into LangGraph state. Just read it — no need to re-update.
        unified_profile = get_unified_profile(graph, current_user['email'])

        unified_profile = get_unified_profile(graph, current_user['email'])

        # Only show profile confirmation if we are not blocking for identity verification
        identity_req = result.get("identity_verification_required", False)
        
        if result.get("profile_changed") and not identity_req:
            blocks.append({
                "type": "profile_confirmation",
                "data": unified_profile
            })

        # Ensure profile_changed is reset in state so it doesn't loop
        if result.get("profile_changed"):
            graph.update_state(config, {"profile_changed": False})

        return jsonify({
            'message': ai_message,
            'blocks': blocks,
            'citations': citations,
            'citizen_profile': unified_profile
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

@chat_bp.route('/api/verify-identity', methods=['POST'])
@token_required
def verify_identity(current_user):
    data = request.get_json(silent=True) or {}
    aadhaar_demo_id = data.get("aadhaar_demo_id")

    if not aadhaar_demo_id:
        return jsonify({"error": "aadhaar_demo_id is required"}), 400

    config = {
        "configurable": {
            "thread_id": current_user['email']
        }
    }

    try:
        # Pre-sync
        get_unified_profile(graph, current_user['email'])

        result = graph.invoke(
            {
                "identity_verification_input": aadhaar_demo_id,
                "user_query": ""
            },
            config=config
        )
        
        final_response_dict = result.get("final_response", {})
        
        # If the final_response is a dictionary, extract it
        if isinstance(final_response_dict, dict):
            ai_message = final_response_dict.get("message", "No message generated.")
            blocks = final_response_dict.get("blocks", [])
            citations = final_response_dict.get("citations", [])
        else:
            ai_message = final_response_dict
            blocks = []
            citations = []

        unified_profile = get_unified_profile(graph, current_user['email'])

        identity_req = result.get("identity_verification_required", False)
        if result.get("profile_changed") and not identity_req:
            blocks.append({
                "type": "profile_confirmation",
                "data": unified_profile
            })

        if result.get("profile_changed"):
            graph.update_state(config, {"profile_changed": False})

        return jsonify({
            'message': ai_message,
            'blocks': blocks,
            'citations': citations,
            'citizen_profile': unified_profile
        }), 200

    except Exception as e:
        print(f"Verify Identity Error: {e}")
        return jsonify({'message': 'An error occurred.', 'error': str(e)}), 500

