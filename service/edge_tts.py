# edge_tts.py
import edge_tts
import numpy as np
from typing import Optional
import yaml
import logging

# Load configuration from config.yaml
with open("config/config.yaml", 'r') as config_file:
    config = yaml.safe_load(config_file)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Voice mappings using config.yaml
ENGLISH_VOICES = {
    "male": config['tts']['edge_tts']['english_voices'].get('male', []),
    "female": config['tts']['edge_tts']['english_voices'].get('female', [])
}

VIETNAMESE_VOICES = {
    "male": config['tts']['edge_tts']['vietnamese_voice'].get('male'),
    "female": config['tts']['edge_tts']['vietnamese_voice'].get('female')
}

def edge_get_voice(lang: str, gender: str) -> Optional[str]:
    """
    Selects a voice based on language and gender using configuration.
    Returns voice name for edge-tts or None if not found.
    """
    logger.debug(f"Selecting Edge-TTS voice for language: {lang}, gender: {gender}")
    try:
        if lang == "en":
            voices = ENGLISH_VOICES.get(gender)
            if voices:
                selected_voice = np.random.choice(voices)
                logger.debug(f"Selected English (Edge-TTS) voice: {selected_voice}")
                return selected_voice
            else:
                logger.warning(f"No English (Edge-TTS) voices found for gender: {gender}")
                return None
        elif lang == "vi":
            voice = VIETNAMESE_VOICES.get(gender)
            if voice:
                logger.debug(f"Selected Vietnamese (Edge-TTS) voice: {voice}")
                return voice
            else:
                logger.warning(f"No Vietnamese (Edge-TTS) voice found for gender: {gender}")
                return None
        else:
            logger.warning(f"Unsupported language for Edge-TTS: {lang}")
            return None
    except Exception as e:
        logger.error(f"Error selecting Edge-TTS voice: {e}")
        return None

async def generate_edge_tts(text: str, voice: str, speed_str: str) -> Optional[bytes]:
    """
    Generates speech using Edge-TTS and returns audio bytes.
    """
    logger.info(f"Generating Edge-TTS audio for text of length {len(text)} with voice: {voice}, speed: {speed_str}")
    try:
        communicate = edge_tts.Communicate(text, voice=voice, rate=speed_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        logger.info(f"Successfully generated {len(audio_data)} bytes of Edge-TTS audio")
        return audio_data
    except Exception as e:
        logger.error(f"Error generating Edge-TTS audio: {e}", exc_info=True)
        return None

async def edge_save_audio(text: str, voice: str, speed: int = 0) -> Optional[bytes]:
    """
    Saves the synthesized audio using Edge-TTS, selecting the appropriate voice.
    """
    logger.info(f"Saving Edge-TTS audio for text with voice: {voice}, speed: {speed}")
    sign = "+" if speed >= 0 else ""
    speed_str = f"{sign}{speed}%"
    return await generate_edge_tts(text, voice, speed_str)

if __name__ == "__main__":
    pass