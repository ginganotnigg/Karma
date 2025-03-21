import os
import json
import subprocess
import asyncio
import tempfile
from service.tts import save_audio
from pydub import AudioSegment
import shutil

LIP_SYNC_TOOL_DIR = "Rhubarb"
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


def convert_mp3_bytes_to_wav_bytes(mp3_bytes):
    """Converts MP3 bytes to WAV bytes (PCM 16-bit, 22.05kHz, mono) using ffmpeg and SPEEDUP_FACTOR."""
    if not shutil.which("ffmpeg"):
        print("FFmpeg is not installed or not found in PATH.")
        return None

    temp_mp3_path = None
    temp_wav_path = None

    try:
        # Create a temporary MP3 file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_mp3:
            temp_mp3.write(mp3_bytes)
            temp_mp3_path = temp_mp3.name

        # Create a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            temp_wav_path = temp_wav.name

        # Run ffmpeg command
        command = [
            "ffmpeg",
            "-i",
            temp_mp3_path,
            "-filter:a",
            f"atempo={SPEEDUP_FACTOR}",
            "-ac",
            "1",
            "-ar",
            "22050",
            "-sample_fmt",
            "s16",
            "-y",
            temp_wav_path,
        ]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return temp_wav_path
    except subprocess.CalledProcessError as e:
        print(f"Error converting MP3 bytes to WAV bytes: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None
    finally:
        if temp_mp3_path and os.path.exists(temp_mp3_path):
            os.remove(temp_mp3_path)


def run_rhubarb_lip_sync_bytes(temp_wav_path, lang):
    """Runs Rhubarb Lip Sync on WAV bytes and generates a JSON output."""
    recognizer = "pocketSphinx" if lang == "us" else "phonetic"
    
    command = [
        os.path.join(LIP_SYNC_TOOL_DIR, "rhubarb"),
        temp_wav_path,
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
        if temp_wav_path and os.path.exists(temp_wav_path):
            duration = get_audio_duration(temp_wav_path)
            os.remove(temp_wav_path)
        return load_template_json(duration)
    finally:
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)


def sync_save_audio(text, audio_filename, voice, speed=0):
    """Synchronous wrapper for save_audio function"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(save_audio(text, audio_filename, voice, speed))
    finally:
        loop.close()


def audio_to_mouthshape_json(mp3_bytes, voice):
    """Converts text to a Rhubarb Lip Sync JSON file."""
    if mp3_bytes is None:
        print("Failed to generate audio bytes.")
        return None

    wav_bytes = convert_mp3_bytes_to_wav_bytes(mp3_bytes)
    if wav_bytes is None:
        print("Failed to convert MP3 bytes to WAV bytes.")
        return None

    lang = voice[:2]
    lipsync_data = run_rhubarb_lip_sync_bytes(wav_bytes, lang)
    
    if lipsync_data:
        lipsync_data = adjust_timestamps(lipsync_data)
        print("Lip sync JSON generated successfully!")
    else:
        print("Failed to generate lip sync JSON.")
    return lipsync_data
    

if __name__ == "__main__":
    pass