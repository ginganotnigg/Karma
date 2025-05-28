from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import asyncio
from service.edge_tts import edge_save_audio, edge_get_voice, generate_edge
from service.score import evaluate_fluency, get_fluency_feedback, calculate_overall_grade, generate_combined_feedback
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
    if not data or "submissions" not in data:
        return jsonify({"error": "Missing submissions parameter"}), 400

    submissions = data["submissions"]
    if not isinstance(submissions, list) or len(submissions) == 0:
        return jsonify({"error": "Submissions must be a non-empty array"}), 400

    results = []
    all_fluency_scores = []

    for i, submission in enumerate(submissions):
        try:
            # Process each submission
            index = submission.get("index", i + 1)
            text = submission.get("answer", "")
            audio_base64 = submission.get("recordProof", "")
            
            # Decode audio data
            try:
                audio_bytes = base64.b64decode(audio_base64)
            except Exception as e:
                return jsonify({"error": f"Invalid audio data for submission {index}: {str(e)}"}), 400
            
            # Evaluate fluency
            fluency_results = evaluate_fluency(audio_bytes, text)
            feedback = get_fluency_feedback(fluency_results)
            
            # Store the letter grade for overall skill calculation
            all_fluency_scores.append(fluency_results["percentage"])
            
            # Create comment from feedback
            comment = "; ".join(feedback) if feedback else ""
            
            # Add to results
            results.append({
                "index": index,
                "comment": comment,
                "score": fluency_results["overall_score"],
                "percentage": fluency_results["percentage"],
            })
            
        except Exception as e:
            # If one submission fails, add an error result but continue processing others
            results.append({
                "index": submission.get("index", 0),
                "comment": f"Error processing submission: {str(e)}",
                "score": "F"
            })
            
    # Calculate overall fluency skill grade
    total_fluency = calculate_overall_grade(all_fluency_scores)
    
    # Generate combined actionable feedback
    actionable_feedback = generate_combined_feedback(results)
    
    # Return the complete response
    return jsonify({
        "result": results,
        "skills": {
            "Fluency": total_fluency
        },
        "actionableFeedback": actionable_feedback
    }), 200


if __name__ == "__main__":
    app.run(debug=True)