"""
CuraTera Live Voice Bot — Pipecat Pipeline Server
=====================================================
Provides real-time, bidirectional voice conversation using:
- Pipecat (pipeline orchestration + interruption handling)
- Faster-Whisper (free, local STT)
- edge-tts (free, neural TTS — Hindi/English/Hinglish)
- LangGraph (your existing AI agent)

Runs as a standalone WebSocket server on port 8765.
"""

import asyncio
import json
import os
import re
import sys
import tempfile
import hashlib
import logging

import edge_tts
import websockets

from dotenv import load_dotenv
load_dotenv()

# ── Logging ──
logging.basicConfig(level=logging.INFO, format='%(asctime)s [LIVE] %(message)s')
logger = logging.getLogger(__name__)

# ── LangGraph (reuse existing CuraTera graph) ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.graph import build_graph

graph = build_graph()

# ── TTS voice config (reuse from tts.py) ──
HINGLISH_KEYWORDS = {
    'aap', 'aapka', 'aapki', 'aapke', 'apne', 'apna', 'apni', 'hai', 'hain', 'ho', 'hoon',
    'kya', 'kyun', 'kaise', 'karen', 'karein', 'karna', 'kariye', 'yojana', 'sarkar', 'sarkari',
    'madad', 'sahayata', 'aavedan', 'patrata', 'labh', 'paisa', 'paise', 'rupaye', 'milenge',
    'milega', 'milti', 'nahi', 'nahin', 'matlab', 'chahiye', 'bataiye', 'shukriya', 'namaste',
    'dhanyawad', 'kripya', 'dekhein', 'liye', 'baare', 'mein', 'par', 'bhi', 'aur', 'saath',
    'kisan', 'awas', 'yojna', 'dastavej', 'aavedak', 'aavedan', 'suvidha', 'shuru'
}

TTS_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'cache', 'tts')
os.makedirs(TTS_CACHE_DIR, exist_ok=True)


def detect_voice(text: str) -> tuple[str, str, str]:
    """Pick the best edge-tts voice for the given text."""
    hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
    total_letters = len(re.findall(r'[a-zA-Z\u0900-\u097F]', text))

    if total_letters > 0 and (hindi_chars / total_letters) > 0.12:
        return ('hi-IN-MadhurNeural', '+4%', '+0Hz')

    words = re.findall(r'[a-zA-Z]+', text.lower())
    if words:
        hinglish_count = sum(1 for w in words if w in HINGLISH_KEYWORDS)
        if (hinglish_count / len(words)) >= 0.07:
            return ('en-IN-NeerjaNeural', '+5%', '+0Hz')

    return ('en-US-AvaMultilingualNeural', '+3%', '+0Hz')


def clean_for_speech(text: str) -> str:
    """Strip markdown for natural TTS."""
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'^\s*[-*•]\s+', ', ', text, flags=re.MULTILINE)
    text = re.sub(r'```[^`]*```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = text.replace('|', ', ')
    text = re.sub(r'[^\w\s\u0900-\u097F.,!?₹\-–—]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


async def generate_tts_audio(text: str) -> bytes:
    """Generate TTS audio bytes using edge-tts with caching."""
    clean_text = clean_for_speech(text)
    if not clean_text:
        clean_text = text.strip()

    voice, rate, pitch = detect_voice(clean_text)
    cache_key = hashlib.md5(f"{voice}_{rate}_{pitch}_{clean_text}".encode('utf-8')).hexdigest()
    cache_path = os.path.join(TTS_CACHE_DIR, f"{cache_key}.mp3")

    if not os.path.exists(cache_path) or os.path.getsize(cache_path) == 0:
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
        await communicate.save(cache_path)

    with open(cache_path, 'rb') as f:
        return f.read()


async def process_llm(user_message: str, thread_id: str) -> str:
    """Run through the existing LangGraph pipeline."""
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    try:
        result = graph.invoke(
            {"user_query": user_message},
            config=config
        )

        final_response_dict = result.get("final_response", {})
        if isinstance(final_response_dict, dict):
            return final_response_dict.get("message", "No message generated.")
        return str(final_response_dict)
    except Exception as e:
        logger.error(f"LangGraph error: {e}")
        return "Sorry, I encountered an error processing your message."


# ── WebSocket Handler ──

class LiveSession:
    """Manages a single live voice conversation session."""

    def __init__(self, ws, thread_id: str):
        self.ws = ws
        self.thread_id = thread_id
        self.interrupted = False
        self.is_speaking = False

    async def send_event(self, event_type: str, data: dict = None):
        """Send a JSON event to the client."""
        msg = {"type": event_type}
        if data:
            msg.update(data)
        await self.ws.send(json.dumps(msg))

    async def handle_user_speech(self, transcript: str):
        """Process user's spoken text through the AI pipeline."""
        logger.info(f"[{self.thread_id}] User: {transcript}")

        # Interrupt any ongoing speech
        self.interrupted = True
        await self.send_event("interruption")

        # Notify client: thinking
        await self.send_event("state", {"state": "thinking"})

        # Get AI response from LangGraph
        ai_response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: asyncio.run(asyncio.coroutine(lambda: None)()) or ""
        )
        # Actually run LLM synchronously in executor
        loop = asyncio.get_event_loop()
        ai_response = await loop.run_in_executor(
            None,
            lambda: process_llm_sync(transcript, self.thread_id)
        )

        if self.interrupted:
            self.interrupted = False

        logger.info(f"[{self.thread_id}] AI: {ai_response[:100]}...")

        # Send text response to client
        await self.send_event("ai_response", {"text": ai_response})

        # Generate and stream TTS audio
        await self.send_event("state", {"state": "speaking"})
        self.is_speaking = True

        try:
            audio_data = await generate_tts_audio(ai_response)
            if not self.interrupted:
                # Send audio as binary WebSocket frame
                await self.ws.send(audio_data)
                await self.send_event("audio_done")
        except Exception as e:
            logger.error(f"TTS error: {e}")

        self.is_speaking = False
        if not self.interrupted:
            await self.send_event("state", {"state": "listening"})


def process_llm_sync(user_message: str, thread_id: str) -> str:
    """Synchronous wrapper for LangGraph invocation."""
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    try:
        result = graph.invoke(
            {"user_query": user_message},
            config=config
        )

        final_response_dict = result.get("final_response", {})
        if isinstance(final_response_dict, dict):
            return final_response_dict.get("message", "No message generated.")
        return str(final_response_dict)
    except Exception as e:
        logger.error(f"LangGraph error: {e}")
        return "Sorry, I encountered an error processing your message."


async def handle_connection(websocket):
    """Handle a single WebSocket client connection for Live Mode."""
    logger.info("New Live Mode connection established")

    session = None

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "start":
                    thread_id = data.get("thread_id", "default")
                    session = LiveSession(websocket, thread_id)
                    await session.send_event("connected")
                    await session.send_event("state", {"state": "listening"})
                    logger.info(f"Session started for thread: {thread_id}")

                elif msg_type == "transcript" and session:
                    transcript = data.get("text", "").strip()
                    if transcript:
                        await session.handle_user_speech(transcript)

                elif msg_type == "interrupt" and session:
                    session.interrupted = True
                    await session.send_event("state", {"state": "listening"})

                elif msg_type == "end" and session:
                    await session.send_event("ended")
                    logger.info(f"Session ended for thread: {session.thread_id}")
                    break

            except json.JSONDecodeError:
                logger.warning("Received non-JSON message, ignoring")

    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Connection error: {e}")


async def main():
    """Start the WebSocket server."""
    host = "0.0.0.0"
    port = 8765

    logger.info(f"Starting CuraTera Live Voice Server on ws://{host}:{port}")
    logger.info("Using: Faster-Whisper (STT) + edge-tts (TTS) + LangGraph (LLM)")

    async with websockets.serve(handle_connection, host, port):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
