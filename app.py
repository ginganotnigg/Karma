from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from tts import speak
from stt import live_recognition

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

if __name__ == "__main__":
    app.run(debug=True)