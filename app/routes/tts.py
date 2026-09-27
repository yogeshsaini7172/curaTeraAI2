import os
import re
import hashlib
import asyncio
import edge_tts
from flask import Blueprint, request, send_file, Response, jsonify

tts_bp = Blueprint('tts_bp', __name__)

# Cache directory for generated voice files (instant zero-delay playback for repeated text)
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'tts')
os.makedirs(CACHE_DIR, exist_ok=True)

# Hinglish vocabulary markers to detect Roman-script Hindi
HINGLISH_KEYWORDS = {
    'aap', 'aapka', 'aapki', 'aapke', 'apne', 'apna', 'apni', 'hai', 'hain', 'ho', 'hoon',
    'kya', 'kyun', 'kaise', 'karen', 'karein', 'karna', 'kariye', 'yojana', 'sarkar', 'sarkari',
    'madad', 'sahayata', 'aavedan', 'patrata', 'labh', 'paisa', 'paise', 'rupaye', 'milenge',
    'milega', 'milti', 'nahi', 'nahin', 'matlab', 'chahiye', 'bataiye', 'shukriya', 'namaste',
    'dhanyawad', 'kripya', 'dekhein', 'liye', 'baare', 'mein', 'par', 'bhi', 'aur', 'saath',
    'kisan', 'awas', 'yojna', 'dastavej', 'aavedak', 'aavedan', 'suvidha', 'shuru'
}

def clean_markdown_for_speech(text: str) -> str:
    """Strip markdown symbols, URLs, and noisy syntax so the voice speaks naturally."""
    # 1. Replace markdown links [text](url) with just text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 2. Remove raw http(s) URLs
    text = re.sub(r'https?://\S+', '', text)
    # 3. Strip bold / italic markers (**text** or *text*)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    # 4. Remove markdown headers (### Header)
    text = re.sub(r'#+\s*', '', text)
    # 5. Turn bullet points and list markers into natural conversational pauses
    text = re.sub(r'^\s*[-*•]\s+', ', ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', ', ', text, flags=re.MULTILINE)
    # 6. Remove code backticks
    text = re.sub(r'```[^`]*```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # 7. Remove markdown table markers (|)
    text = text.replace('|', ', ')
    # 8. Keep clean letters, numbers, punctuation, Hindi Unicode, currency symbols
    text = re.sub(r'[^\w\s\u0900-\u097F.,!?₹\-–—]', '', text)
    # 9. Clean extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def detect_language_mode(text: str, requested_lang: str = 'auto') -> tuple[str, str, str]:
    """
    Intelligently determines the best voice, rate, and pitch for Hindi, English, and Hinglish.
    Returns (voice_name, rate, pitch).
    
    Voices used:
    - Hindi: hi-IN-MadhurNeural (Warm, natural, conversational male voice - far superior to robotic Swara)
    - Hinglish: en-IN-NeerjaNeural (Indian English voice with natural Indian phonetics for Roman Hindi)
    - English: en-US-AvaMultilingualNeural (Next-gen Gemini / ChatGPT style expressive conversational voice)
    """
    if requested_lang == 'madhur':
        return ('hi-IN-MadhurNeural', '+4%', '+0Hz')
    elif requested_lang == 'neerja':
        return ('en-IN-NeerjaNeural', '+5%', '+0Hz')
    elif requested_lang == 'ava' or requested_lang == 'gemini':
        return ('en-US-AvaMultilingualNeural', '+3%', '+0Hz')

    # 1. Check for Devanagari Hindi characters
    hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
    total_letters = len(re.findall(r'[a-zA-Z\u0900-\u097F]', text))
    
    if total_letters > 0 and (hindi_chars / total_letters) > 0.12:
        # Pure or predominantly Devanagari Hindi
        # hi-IN-MadhurNeural is the top-rated natural Hindi voice (warm, friendly, non-robotic)
        return ('hi-IN-MadhurNeural', '+4%', '+0Hz')

    # 2. Check for Hinglish (Latin alphabet with Hindi words)
    words = re.findall(r'[a-zA-Z]+', text.lower())
    if len(words) > 0:
        hinglish_count = sum(1 for w in words if w in HINGLISH_KEYWORDS)
        if (hinglish_count / len(words)) >= 0.07 or requested_lang in ('hinglish', 'hi'):
            # Text is in Latin alphabet but contains Hindi words (Hinglish)
            # en-IN-NeerjaNeural pronounces Roman Hindi authentically without Americanization
            return ('en-IN-NeerjaNeural', '+5%', '+0Hz')

    # 3. Default to English (Gemini / OpenAI style warm conversational voice)
    return ('en-US-AvaMultilingualNeural', '+3%', '+0Hz')

async def synthesize_speech(text: str, voice: str, rate: str, pitch: str, output_path: str):
    """Generate audio using Edge TTS and save to disk."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)

@tts_bp.route('/api/chat/tts', methods=['GET', 'POST'])
def get_tts():
    # Support both GET query parameters and POST JSON body
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        raw_text = data.get('text', '')
        requested_lang = data.get('lang', 'auto')
    else:
        raw_text = request.args.get('text', '')
        requested_lang = request.args.get('lang', 'auto')

    if not raw_text or not raw_text.strip():
        return jsonify({"error": "No text provided"}), 400

    # 1. Clean markdown and format speech for maximum clarity
    speech_text = clean_markdown_for_speech(raw_text)
    if not speech_text:
        speech_text = raw_text.strip()

    # 2. Select the optimal high-fidelity voice
    voice, rate, pitch = detect_language_mode(speech_text, requested_lang)

    # 3. Cache lookup for instant zero-latency playback on subsequent calls
    cache_key = hashlib.md5(f"{voice}_{rate}_{pitch}_{speech_text}".encode('utf-8')).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.mp3")

    try:
        if not os.path.exists(cache_file) or os.path.getsize(cache_file) == 0:
            # Generate audio file
            asyncio.run(synthesize_speech(speech_text, voice, rate, pitch, cache_file))

        # Serving via send_file provides Content-Length & Accept-Ranges headers,
        # which lets Android MediaPlayer start playback in <200ms without buffering lag!
        return send_file(
            cache_file,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="speech.mp3"
        )
    except Exception as e:
        print(f"[TTS Error] Synthesis failed: {e}")
        return jsonify({"error": f"TTS synthesis failed: {str(e)}"}), 500
