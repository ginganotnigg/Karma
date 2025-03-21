import edge_tts
import numpy as np

ENGLISH_VOICES = { 
    "male": [ "en-US-GuyNeural", "en-GB-RyanNeural", "en-AU-WilliamNeural", "en-CA-LiamNeural", "en-IN-PrabhatNeural" ], 
    "female": [ "en-US-JennyNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural", "en-CA-ClaraNeural", "en-IN-NeerjaNeural" ] 
}

VIETNAMESE_VOICES = {
    "male": "vi-VN-NamMinhNeural",
    "female": "vi-VN-HoaiMyNeural"
}

def get_voice(lang, gender):
    """
    Selects a voice based on language and gender.
    Defaults to male if gender is invalid.
    """
    if lang == "en":
        return np.random.choice(ENGLISH_VOICES[gender])
    return VIETNAMESE_VOICES[gender]

async def generate_edge_tts(text, voice, speed_str):
    """
    Generates speech using Edge-TTS and returns audio bytes.
    """
    try:
        communicate = edge_tts.Communicate(text, voice=voice, rate=speed_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception as e:
        print(f"Error generating Edge-TTS audio: {e}")
        return None

async def save_audio(text, voice, speed=0):
    """
    Saves the synthesized audio, selecting the appropriate voice.
    """
    sign = "+" if speed >= 0 else ""
    speed_str = f"{sign}{speed}%"
    return await generate_edge_tts(text, voice, speed_str)

if __name__ == "__main__":
    pass