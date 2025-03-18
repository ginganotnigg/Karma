from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import asyncio
import os
from tts import save_audio
from lip_sync import text_to_mouthshape_json
import time

AUDIO_DIR = "audio"

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/audio/<path:filename>', methods=['GET'])
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route("/api/tts", methods=["POST"])
def tts_api():
    """
    Generates and returns a TTS audio file.
    """
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"Error": "Missing 'content' parameter"}), 400

    text = data["content"]
    gender = data.get("gender", "male").lower()
    lang = data.get("language", "en").lower()
    speed = data.get("speed", 0)

    if gender not in ["male", "female"]:
        return jsonify({"Error": "Invalid gender value. Use 'male' or 'female'."}), 400
    if lang not in ["male", "female"]:
        return jsonify({"Error": "Invalid language value. Use 'en' or 'vi'."}), 400
    if speed > 20 or speed < -20:
        return jsonify({"Error": "Invalid speed value."}), 400
    
    filename = f"output_{int(time.time())}.mp3"

    try:
        if os.path.exists(AUDIO_DIR):
            for filename in os.listdir(AUDIO_DIR):
                audio_path = os.path.join(AUDIO_DIR, filename)
                try:
                    os.unlink(audio_path)
                except Exception as e:
                    print(f"Failed to delete {audio_path}. Reason: {e}")
        output_path = asyncio.run(save_audio(text, filename, lang, gender))
        if output_path is None:
            return jsonify({"Error": "Failed to generate audio."}), 500
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"Error": str(e)}), 500
    
@app.route('/api/lip-sync', methods=['POST'])
def lip_sync():
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"Error": "Missing 'content' parameter"}), 400

    text = data["content"]
    gender = data.get("gender", "male").lower()
    lang = data.get("language", "en").lower()
    filename = f"output_{int(time.time())}.mp3"

    if gender not in ["male", "female"]:
        return jsonify({"Error": "Invalid gender value. Use 'male' or 'female'."}), 400

    try:
        # Call the text_to_mouthshape_json function
        lipsync_data = text_to_mouthshape_json(text, filename, lang, gender)
        
        if lipsync_data is None:
            return jsonify({"error": "Failed to generate lip sync data"}), 500
        
        return jsonify(lipsync_data), 200
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)