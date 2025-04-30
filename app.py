from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import asyncio
from service.edge_tts import edge_save_audio, edge_get_voice, generate_edge
from service.score import evaluate_fluency, get_fluency_feedback
from service.lip_sync import audio_to_mouthshape_json
import base64
import logging
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    voice = data.get("voiceId", edge_get_voice(lang, gender))
    speed = data.get("speed", "0")
    if "filename" in data:
        filename = data["filename"]
        output_data = asyncio.run(generate_edge(text, voice, filename))
        return send_file(output_data, as_attachment=True, download_name=filename)

    speed = int(speed)
    if speed > 20 or speed < -20:
        return jsonify({"Error": "Invalid speed value."}), 400

    try:
        # Try using edge_tts first
        output_data = asyncio.run(edge_save_audio(text, voice, speed))
        if output_data is None:
            raise Exception("Edge TTS failed to generate audio.")
        audio_base64 = base64.b64encode(output_data).decode('utf-8')
        return jsonify({"audio": audio_base64})
    except Exception as e:
        # logger.error(f"Edge TTS error: {str(e)}")
        # logger.info("Falling back to py_tts")

        # try:
            # Fallback to py_tts
            #     voice = py_get_voice(lang, gender)  # Get voice for py_tts
            #     output_data = asyncio.run(py_save_audio(text, voice, speed))
            #     if output_data is None:
            #         return jsonify({"Error": "Failed to generate audio with py_tts."}), 500
            #     audio_base64 = base64.b64encode(output_data).decode('utf-8')
            #     return jsonify({"audio": audio_base64})
            # except Exception as e:
            #     logger.error(f"Py TTS error: {str(e)}")
        return jsonify({"Error": str(e)}), 500
   

@app.route('/api/lip-sync', methods=['POST'])
def lip_sync():
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"Error": "Missing 'content' parameter"}), 400

    text = data["content"]
    gender = data.get("gender", "male").lower()
    lang = data.get("language", "en").lower()
    speed = data.get("speed", "0")
    voice = data.get("voiceId", edge_get_voice(lang, gender))

    speed = int(speed)
    if speed > 20 or speed < -20:
        return jsonify({"Error": "Invalid speed value."}), 400

    try:
        output_data = asyncio.run(edge_save_audio(text, voice, speed))
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
    
@app.route('/api/audio-score', methods=['POST'])
def score():
    data = request.get_json()
    if not data or "transcript" not in data or "recordProof" not in data:
        return jsonify({"Error": "Missing parameter"}), 400

    text = data["transcript"]
    audio_base64 = data["recordProof"]
    audio_bytes = base64.b64decode(audio_base64)
    try:
        fluency_results = evaluate_fluency(audio_bytes, text)
        feedback = get_fluency_feedback(fluency_results)
        return jsonify({"results": fluency_results,
                        "actionableFeedback": feedback}), 200
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)