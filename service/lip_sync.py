import os
import json
import subprocess
import asyncio
import tempfile
from service.edge_tts import edge_save_audio
from pydub import AudioSegment
import shutil
from service.shared import logger


def set_lipsync_config(_config):
    global config, LIP_SYNC_TOOL_DIR, SPEEDUP_FACTOR, TIMEOUT, CLOSED_CUE_DURATION, TEMPLATE_PATH, DIGITS_AFTER_DECIMAL
    config = _config
    LIP_SYNC_TOOL_DIR = config['lip_sync']['tool_dir']
    SPEEDUP_FACTOR = config['lip_sync']['speedup_factor']
    TIMEOUT = config['lip_sync']['timeout']
    CLOSED_CUE_DURATION = config['lip_sync']['closed_cue_duration']
    TEMPLATE_PATH = config['path']['template']
    DIGITS_AFTER_DECIMAL = 2
    


def round_time(num):
    return round(num, DIGITS_AFTER_DECIMAL)

def get_audio_duration(audio_path):
    """Get the duration of an audio file in seconds using pydub"""
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return -1
    
    try:
        logger.debug(f"Getting duration for audio file: {audio_path}")
        audio = AudioSegment.from_file(audio_path)
        duration = len(audio) / 1000.0
        return duration
    except Exception as e:
        logger.error(f"Error getting audio duration: {str(e)}")
        return -1

def load_template_json(audio_duration, template_path=None):
    """Loads and cuts the template JSON based on audio duration."""
    if template_path is None:
        template_path = TEMPLATE_PATH
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
            filtered_mouth_cues[-1]["end"] = round_time(audio_duration - CLOSED_CUE_DURATION)
            filtered_mouth_cues[-1]["start"] = round_time(min(filtered_mouth_cues[-1]["start"], filtered_mouth_cues[-1]["end"]))

        closed_cue = {
            "start": round_time(audio_duration - CLOSED_CUE_DURATION),
            "end": round_time(audio_duration),
            "value": "X"
        }
        filtered_mouth_cues.append(closed_cue)
    else:
        filtered_mouth_cues.append({
            "start": round_time(audio_duration - CLOSED_CUE_DURATION), 
            "end": round_time(audio_duration), 
            "value": "X"
        })

    result = {
        "metadata": {
            "duration": round_time(audio_duration),
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
        lipsync_data["metadata"]["duration"] = round_time(lipsync_data["metadata"]["duration"] * SPEEDUP_FACTOR)
        
        for frame in lipsync_data["mouthCues"]:
            frame["start"] = round_time(frame["start"] * SPEEDUP_FACTOR)
            frame["end"] = round_time(frame["end"] * SPEEDUP_FACTOR)
            
            # Ensure start and end values are not identical
            if frame["start"] == frame["end"] and frame["start"] > 0:
                frame["start"] = round_time(frame["start"] - 0.01)
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
    recognizer = "pocketSphinx" if lang == "en" else "phonetic"
    
    logger.info(f"Running Rhubarb lip sync with recognizer: {recognizer}")

    command = [
        os.path.join(LIP_SYNC_TOOL_DIR, "rhubarb"),
        temp_wav_path,
        "-f",
        "json",
        "-r",
        recognizer,
    ]

    try:
        logger.debug(f"Executing Rhubarb command: {' '.join(command)}")
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                timeout=TIMEOUT)
        logger.info("Rhubarb completed successfully")
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running Rhubarb: {str(e)}")
        if e.stderr:
            logger.error(f"Rhubarb error output: {e.stderr.decode()}")
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"Rhubarb process timed out after {TIMEOUT} seconds")
        logger.info(f"Falling back to template JSON")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Rhubarb JSON output: {str(e)}")
        return None
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

        # Calculate audio duration once
        duration = -1
        if wav_bytes and os.path.exists(wav_bytes):
            duration = get_audio_duration(wav_bytes)
            logger.info(f"Audio duration with speedup: {duration} seconds")

        if "vi" in voice:
            lang = "vi"
        else:
            lang = "en"
        logger.debug(f"Detected language: {lang}")
        
        lipsync_data = run_rhubarb_lip_sync_bytes(wav_bytes, lang)
        
        if lipsync_data:
            logger.info("Adjusting timestamps for lip sync data")
            lipsync_data = adjust_timestamps(lipsync_data)
        else:
            lipsync_data = load_template_json(duration * SPEEDUP_FACTOR)
        logger.info("Lip sync JSON generated successfully!")
        return lipsync_data
    except Exception as e:
        logger.error(f"Unexpected error in audio_to_mouthshape_json: {str(e)}", exc_info=True)
        return None
    

if __name__ == "__main__":
    logger.info("Lip sync module loaded")