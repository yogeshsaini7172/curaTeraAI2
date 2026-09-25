import firebase_admin
from firebase_admin import credentials, messaging
import os
from pathlib import Path

# Path to the service account key (root of CuraTerra-AI)
SERVICE_ACCOUNT_PATH = Path(__file__).resolve().parents[2] / "firebase-adminsdk.json"

_initialized = False

def init_firebase():
    global _initialized
    if not _initialized:
        if SERVICE_ACCOUNT_PATH.exists():
            try:
                cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
                firebase_admin.initialize_app(cred)
                _initialized = True
                print("Firebase Admin initialized successfully.")
            except ValueError:
                # App already initialized
                _initialized = True
        else:
            print("Firebase Admin SDK key not found at:", SERVICE_ACCOUNT_PATH)

def send_push_notification(fcm_token: str, title: str, body: str, data: dict = None):
    if not _initialized:
        init_firebase()
        
    if not _initialized:
        print("Cannot send FCM notification: Firebase not initialized.")
        return False
        
    if not fcm_token:
        print("Cannot send FCM notification: No token provided.")
        return False

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data if data else {},
        token=fcm_token,
    )

    try:
        response = messaging.send(message)
        print(f"Successfully sent FCM push notification: {response}")
        return True
    except Exception as e:
        print(f"Error sending FCM message: {e}")
        return False
