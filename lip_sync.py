import os
import json
import subprocess
import asyncio
from tts import save_audio
from pydub import AudioSegment
import shutil

LIP_SYNC_TOOL_DIR = "Rhubarb"
JSON_OUTPUT_DIR = "json"
SPEEDUP_FACTOR = 4.0
TIMEOUT = 15
CLOSED_CUE_DURATION = 0.1

def get_audio_duration(audio_path):
    """Get the duration of an audio file in seconds using ffmpeg"""
    if not os.path.exists(audio_path):
        return None
        
    cmd = ["ffmpeg", "-i", audio_path, "-f", "null", "-"]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        
        for line in output.split('\n'):
            if "Duration" in line:
                time_str = line.split("Duration: ")[1].split(",")[0].strip()
                h, m, s = time_str.split(':')
                duration = float(h) * 3600 + float(m) * 60 + float(s)
                return duration
        
        return 0.0
    except subprocess.CalledProcessError:
        return 0.0


def load_template_json(audio_duration, template_path="template.json"):
    """Loads and cuts the template JSON based on audio duration."""
    try:
        with open(template_path, 'r') as f:
            template_data = json.load(f)
    except FileNotFoundError:
        print(f"Template file '{template_path}' not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON from '{template_path}'.")
        return None

    if not isinstance(template_data, dict) or "mouthCues" not in template_data:
        print("Invalid template JSON structure.")
        return None

    if audio_duration is None:
        return {"mouthCues": []}
    mouth_cues = template_data["mouthCues"]
    filtered_mouth_cues = []
    for cue in mouth_cues:
        if cue["start"] < audio_duration:
            filtered_mouth_cues.append(cue)

    if filtered_mouth_cues:
        last_cue_end = filtered_mouth_cues[-1]["end"]
        if last_cue_end > audio_duration:
            filtered_mouth_cues[-1]["end"] = audio_duration - CLOSED_CUE_DURATION
            filtered_mouth_cues[-1]["start"] = min(filtered_mouth_cues[-1]["start"], filtered_mouth_cues[-1]["end"])

        closed_cue = {
            "start": audio_duration - CLOSED_CUE_DURATION,
            "end": audio_duration,
            "value": "X"
        }
        filtered_mouth_cues.append(closed_cue)
    else:
        filtered_mouth_cues.append({"start": audio_duration - CLOSED_CUE_DURATION, "end": audio_duration, "value": "X"})

    return {
        "metadata": {
            "duration": audio_duration,
            "soundFile": "/app/audio/output_0000000000.wav"
        },
        "mouthCues": filtered_mouth_cues
    }


def adjust_timestamps(lipsync_data):
    """Adjusts timestamps in the Rhubarb JSON output."""
    if "mouthCues" in lipsync_data and "metadata" in lipsync_data:
        lipsync_data["metadata"]["duration"] *= SPEEDUP_FACTOR
        lipsync_data
        for frame in lipsync_data["mouthCues"]:
            frame["start"] *= SPEEDUP_FACTOR
            frame["end"] *= SPEEDUP_FACTOR
    return lipsync_data


def convert_mp3_to_wav(mp3_path):
    """
    Converts the generated MP3 file to a WAV file (PCM 16-bit, 22.05kHz, mono).
    """
    if not shutil.which("ffmpeg"):
        print("FFmpeg is not installed or not found in PATH.")
        return None
    
    wav_path = mp3_path.replace(".mp3", ".wav")
    command = [
        "ffmpeg",
        "-i",
        mp3_path,
        "-filter:a",
        f"atempo={SPEEDUP_FACTOR}", #speed up the audio
        "-ac",
        "1",
        "-ar",
        "22050",
        "-sample_fmt",
        "s16",
        "-y",
        wav_path,
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return wav_path
    except subprocess.CalledProcessError as e:
        print(f"Error converting MP3 to WAV: {e}")
        return None


def run_rhubarb_lip_sync(wav_path, lang): 
    """Runs Rhubarb Lip Sync on the WAV file and generates a JSON output."""
    recognizer = "pocketSphinx" if lang == "us" else "phonetic"
    command = [
        os.path.join(LIP_SYNC_TOOL_DIR, "rhubarb"),
        wav_path,
        "-f",
        "json",
        "-r",
        recognizer,
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                timeout=TIMEOUT)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running Rhubarb: {e}")
        return None
    except subprocess.TimeoutExpired:
        print("Rhubarb process timed out after 15 seconds")
        return None


def sync_save_audio(text, audio_filename, lang="en", gender="male"):
    """Synchronous wrapper for save_audio function"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(save_audio(text, audio_filename, lang, gender))
    finally:
        loop.close()


def text_to_mouthshape_json(text, audio_filename, lang="en", gender="male"): 
    """Converts text to a Rhubarb Lip Sync JSON file."""
    # Use the synchronous wrapper instead of asyncio.run()
    mp3_path = sync_save_audio(text, audio_filename, lang, gender)
    if mp3_path is None:
        print("Failed to generate audio file.")
        return None
    
    wav_path = convert_mp3_to_wav(mp3_path)
    if wav_path is None:
        print("Failed to convert MP3 to WAV.")
        return None
    
    lipsync_data = run_rhubarb_lip_sync(wav_path, lang)
    
    if lipsync_data:
        lipsync_data = adjust_timestamps(lipsync_data)
        print("Lip sync JSON generated successfully!")
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
        return lipsync_data
    else:
        audio_duration = get_audio_duration(mp3_path)
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
        print("Failed to generate lip sync JSON.")
        return load_template_json(audio_duration)
    

# Example usage
if __name__ == "__main__":
    text = "WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead."
    audio_filename = "output.mp3"
    lipsync_result = text_to_mouthshape_json(text, audio_filename)
    print(json.dumps(lipsync_result, indent=2))