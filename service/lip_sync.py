import os
import json
import subprocess
import asyncio
import tempfile
from service.edge_tts import edge_save_audio
from service.py_tts import py_save_audio
from pydub import AudioSegment
import shutil
import logging
import yaml

# Load configuration from config.yaml
with open("config/config.yaml", 'r') as config_file:
    config = yaml.safe_load(config_file)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

LIP_SYNC_TOOL_DIR = config['lip_sync']['tool_dir']
SPEEDUP_FACTOR = config['lip_sync']['speedup_factor']
TIMEOUT = config['lip_sync']['timeout']
CLOSED_CUE_DURATION = config['lip_sync']['closed_cue_duration']


def get_audio_duration(audio_path):
    """Get the duration of an audio file in seconds using ffmpeg"""
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return None
        
    cmd = ["ffmpeg", "-i", audio_path, "-f", "null", "-"]
    try:
        logger.debug(f"Getting duration for audio file: {audio_path}")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        
        for line in output.split('\n'):
            if "Duration" in line:
                time_str = line.split("Duration: ")[1].split(",")[0].strip()
                h, m, s = time_str.split(':')
                duration = float(h) * 3600 + float(m) * 60 + float(s)
                logger.debug(f"Audio duration: {duration} seconds")
                return duration
        
        logger.warning("Could not find duration information in ffmpeg output")
        return 0.0
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting audio duration: {str(e)}")
        return 0.0

def load_template_json(audio_duration, template_path="template.json"):
    """Loads and cuts the template JSON based on audio duration."""
    logger.info(f"Loading template JSON with audio duration: {audio_duration}")
    try:
        with open(template_path, 'r') as f:
            template_data = json.load(f)
            logger.debug(f"Successfully loaded template from {template_path}")
    except FileNotFoundError:
        logger.error(f"Template file '{template_path}' not found")
        return None
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from '{template_path}'")
        return None

    if not isinstance(template_data, dict) or "mouthCues" not in template_data:
        logger.error("Invalid template JSON structure")
        return None

    if audio_duration is None:
        logger.warning("Audio duration is None, returning empty mouth cues")
        return {"mouthCues": []}
        
    mouth_cues = template_data["mouthCues"]
    logger.debug(f"Processing {len(mouth_cues)} mouth cues")
    filtered_mouth_cues = []
    for cue in mouth_cues:
        if cue["start"] < audio_duration:
            filtered_mouth_cues.append(cue)

    logger.debug(f"Filtered to {len(filtered_mouth_cues)} mouth cues")
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

    result = {
        "metadata": {
            "duration": audio_duration,
            "soundFile": "/tmp/tmpabcdef1.wav"
        },
        "mouthCues": filtered_mouth_cues
    }
    logger.info(f"Successfully processed template JSON with {len(filtered_mouth_cues)} mouth cues")
    return result

def adjust_timestamps(lipsync_data):
    """Adjusts timestamps in the Rhubarb JSON output."""
    logger.info(f"Adjusting timestamps with speedup factor: {SPEEDUP_FACTOR}")
    if "mouthCues" in lipsync_data and "metadata" in lipsync_data:
        lipsync_data["metadata"]["duration"] *= SPEEDUP_FACTOR
        
        for frame in lipsync_data["mouthCues"]:
            frame["start"] *= SPEEDUP_FACTOR
            frame["end"] *= SPEEDUP_FACTOR
    else:
        logger.warning("Invalid lipsync data structure, could not adjust timestamps")
    return lipsync_data

def convert_mp3_bytes_to_wav_bytes(mp3_bytes):
    """Converts MP3 bytes to WAV bytes (PCM 16-bit, 22.05kHz, mono) using ffmpeg and SPEEDUP_FACTOR."""
    if not shutil.which("ffmpeg"):
        logger.error("FFmpeg is not installed or not found in PATH")
        return None

    logger.info(f"Converting MP3 bytes to WAV bytes (length: {len(mp3_bytes) if mp3_bytes else 0})")
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
        logger.debug(f"Running FFmpeg command: {' '.join(command)}")
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info(f"Successfully converted MP3 to WAV: {temp_wav_path}")
        return temp_wav_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running FFmpeg command: {str(e)}")
        if e.stderr:
            logger.error(f"FFmpeg error output: {e.stderr.decode()}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during conversion: {str(e)}", exc_info=True)
        return None
    finally:
        if temp_mp3_path and os.path.exists(temp_mp3_path):
            try:
                os.remove(temp_mp3_path)
                logger.debug(f"Removed temporary MP3 file: {temp_mp3_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary MP3 file: {str(e)}")

def run_rhubarb_lip_sync_bytes(temp_wav_path, lang):
    """Runs Rhubarb Lip Sync on WAV bytes and generates a JSON output."""
    recognizer = "pocketSphinx" if lang == "us" else "phonetic"
    
    logger.info(f"Running Rhubarb lip sync with recognizer: {recognizer}")
    
    command = [
        os.path.join(LIP_SYNC_TOOL_DIR, "rhubarb"),
        temp_wav_path,
        "-f",
        "json",
        "-r",
        recognizer,
    ]
    
    duration = -1
    try:
        logger.debug(f"Executing Rhubarb command: {' '.join(command)}")
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                timeout=TIMEOUT)
        if temp_wav_path and os.path.exists(temp_wav_path):
            duration = get_audio_duration(temp_wav_path)
        logger.info("Rhubarb completed successfully")
        return json.loads(result.stdout), duration
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running Rhubarb: {str(e)}")
        if e.stderr:
            logger.error(f"Rhubarb error output: {e.stderr.decode()}")
        return None, -1
    except subprocess.TimeoutExpired:
        logger.error(f"Rhubarb process timed out after {TIMEOUT} seconds")
        logger.info(f"Falling back to template JSON with duration: {duration}")
        if duration >= 0:
            return load_template_json(duration), duration
        return None, -1
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Rhubarb JSON output: {str(e)}")
        return None, -1
    finally:
        if os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary WAV file: {str(e)}")

def sync_save_audio(text, audio_filename, voice, speed=0):
    """Synchronous wrapper for save_audio function"""
    logger.info(f"Synchronously saving audio for text of length {len(text)}")
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(edge_save_audio(text, audio_filename, voice, speed))
        logger.info("Successfully saved audio synchronously")
        return result
    except Exception as e:
        logger.error(f"Error in sync_save_audio: {str(e)}", exc_info=True)
        return None
    finally:
        loop.close()
        logger.debug("Closed asyncio event loop")

def audio_to_mouthshape_json(mp3_bytes, voice):
    """Converts text to a Rhubarb Lip Sync JSON file."""
    logger.info(f"Converting MP3 audio to mouth shape JSON with voice: {voice}")
    if mp3_bytes is None:
        logger.error("Failed to generate audio bytes")
        return None

    try:
        logger.debug(f"Processing MP3 audio of length: {len(mp3_bytes)}")
        wav_bytes = convert_mp3_bytes_to_wav_bytes(mp3_bytes)
        if wav_bytes is None:
            logger.error("Failed to convert MP3 bytes to WAV bytes")
            return None

        lang = voice[:2]
        logger.debug(f"Detected language: {lang}")
        lipsync_data, duration = run_rhubarb_lip_sync_bytes(wav_bytes, lang)
        
        if lipsync_data:
            logger.info("Adjusting timestamps for lip sync data")
            lipsync_data = adjust_timestamps(lipsync_data)
            logger.info("Lip sync JSON generated successfully!")
        else:
            logger.info(f"Falling back to template JSON with duration: {duration}")
            if duration >= 0:
                lipsync_data = load_template_json(duration)
        
        return lipsync_data
    except Exception as e:
        logger.error(f"Unexpected error in audio_to_mouthshape_json: {str(e)}", exc_info=True)
        return None
    

if __name__ == "__main__":
    logger.info("Lip sync module loaded")