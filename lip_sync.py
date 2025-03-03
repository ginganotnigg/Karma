import os
import json
import subprocess
import asyncio
from tts import save_audio
from pydub import AudioSegment
import shutil

LIP_SYNC_TOOL_DIR = "Rhubarb"
JSON_OUTPUT_DIR = "json"

def convert_mp3_to_wav(mp3_path):
    """
    Converts the generated MP3 file to a WAV file (PCM 16-bit, 44.1kHz, mono).
    """
    try:
        # Check if ffmpeg is available
        if not shutil.which("ffmpeg"):
            print("FFmpeg is not installed or not found in PATH.")
            return None
        
        wav_path = mp3_path.replace(".mp3", ".wav")
        audio = AudioSegment.from_file(mp3_path, format="mp3")
        audio = audio.set_frame_rate(44100).set_channels(1).set_sample_width(2)  # 16-bit PCM
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as e:
        print(f"Error converting MP3 to WAV: {e}")
        return None

def run_rhubarb_lip_sync(wav_path, json_filename): 
    """Runs Rhubarb Lip Sync on the WAV file and generates a JSON output."""
    os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)
    output_json_path = os.path.join(JSON_OUTPUT_DIR, json_filename)
    command = [os.path.join(LIP_SYNC_TOOL_DIR, "rhubarb"), wav_path, "-f", "json"]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running Rhubarb: {e}")
        return None

def text_to_mouthshape_json(text, audio_filename, lang="en", gender="male"): 
    """Converts text to a Rhubarb Lip Sync JSON file."""
    mp3_path = asyncio.run(save_audio(text, audio_filename, lang, gender))
    wav_path = convert_mp3_to_wav(mp3_path)
    lipsync_data = run_rhubarb_lip_sync(wav_path, audio_filename.replace(".mp3", ".json"))

    os.remove(mp3_path)
    os.remove(wav_path)
    
    if lipsync_data:
        print("Lip sync JSON generated successfully!")
    else:
        print("Failed to generate lip sync JSON.")
    
    return lipsync_data

# Example usage
if __name__ == "__main__":
    text = "WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead."
    audio_filename = "output.mp3"
    lipsync_result = text_to_mouthshape_json(text, audio_filename)
    print(json.dumps(lipsync_result, indent=2))
