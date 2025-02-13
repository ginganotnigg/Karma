import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from tts_shadow import speak
from stt_darkin import live_recognition

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route("/api/tts", methods=["POST"])
def tts_api():
    """
    TTS API route.
    Expects a JSON payload with:
      - "text" (required)
      - "gender" (optional, defaults to "female")
      - "lang" (optional, defaults to "en_US")
    
    Returns the synthesized speech as a WAV file.
    """
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"Error": "Missing 'content' parameter"}), 400

    text = data["content"]
    # Convert readerIndex to an integer, defaulting to 0 if not provided.
    try:
        reader_id = int(data.get("reader", 0))
    except ValueError:
        return jsonify({"Error": "Invalid reader index value"}), 400
    lang = data.get("lang", "en_US")

    try:
        _ = speak(text, reader_id, lang)
    except Exception as e:
        return jsonify({"Error": str(e)}), 500
    return jsonify({"Message": "TTS triggered successfully!"})

@app.route("/api/stt", methods=["POST"])
def stt_api():
    """
    STT API route.
    This endpoint is triggered by a POST request when the user clicks the "Answer" button.
    No audio file is provided; instead, the function captures live speech directly from the server's microphone.
    
    It listens and stops recording automatically once there is more than 3 seconds of silence after speech.
    The transcription is then returned as JSON.
    
    Optional form field:
      - "language": defaults to "en-US"
    """
    language = request.form.get("language", "en-US")

    try:
        transcription = live_recognition(language)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"Transcription": transcription})

if __name__ == "__main__":
    app.run(debug=True)