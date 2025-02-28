from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import asyncio
from tts import save_audio
import time

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route("/api/tts", methods=["POST"])
def tts_api():
    """
    Generates and returns a TTS audio file.
    """
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"Error": "Missing 'content' parameter"}), 400

    text = data["content"]
    gender = data.get("gender", "female").lower()
    lang = data.get("lang", "en").lower()

    if gender not in ["male", "female"]:
        return jsonify({"Error": "Invalid gender value. Use 'male' or 'female'."}), 400

    filename = f"output_{int(time.time())}.mp3"

    try:
        output_path = asyncio.run(save_audio(text, filename, lang, gender))
        return jsonify({
            "message": "Audio generated successfully",
            "filename": filename,
            "path": output_path
        })
    except Exception as e:
        return jsonify({"Error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)