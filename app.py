from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import asyncio
from service.tts import save_audio, get_voice
from service.lip_sync import audio_to_mouthshape_json
import base64

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route("/api/tts", methods=["POST"])
def tts_api():
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"Error": "Missing 'content' parameter"}), 400

    text = data["content"]
    gender = data.get("gender", "male").lower()
    lang = data.get("language", "en").lower()
    voice = data.get("voiceId", get_voice(lang, gender))
    speed = data.get("speed", "0")

    speed = int(speed)
    if speed > 20 or speed < -20:
        return jsonify({"Error": "Invalid speed value."}), 400

    try:
        output_data = asyncio.run(save_audio(text, voice, speed))
        if output_data is None:
            return jsonify({"Error": "Failed to generate audio."}), 500
        audio_base64 = base64.b64encode(output_data).decode('utf-8')
        return jsonify({"audio": audio_base64})
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
    voice = data.get("voiceId", get_voice(lang, gender))
    speed = data.get("speed", "0")

    speed = int(speed)
    if speed > 20 or speed < -20:
        return jsonify({"Error": "Invalid speed value."}), 400

    try:
        output_data = asyncio.run(save_audio(text, voice, speed))
        if output_data is None:
            return jsonify({"Error": "Failed to generate audio."}), 500
        audio_base64 = base64.b64encode(output_data).decode('utf-8')
        lipsync_data = audio_to_mouthshape_json(output_data, voice)

        if lipsync_data is None:
            return jsonify({"error": "Failed to generate lip sync data"}), 500

        return jsonify({"audio": audio_base64,
                        "lipsync": lipsync_data}), 200
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)