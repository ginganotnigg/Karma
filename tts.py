import os
import asyncio
import edge_tts
import numpy as np

AUDIO_OUTPUT_DIR = "audio"

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

async def generate_edge_tts(text, filename, voice, speed_str):
    """
    Generates speech using Edge-TTS and saves it as a file.
    """
    os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
    try:
        tts = edge_tts.Communicate(text, voice=voice, rate=speed_str) 
        await tts.save(output_path)
        return output_path
    except Exception as e:
        print(f"Error generating Edge-TTS audio: {e}")
        return None

async def save_audio(text, filename, lang="en", gender="male", speed=0):
    """
    Saves the synthesized audio, selecting the appropriate voice.
    """
    voice = get_voice(lang, gender)
    sign = "+" if speed >= 0 else ""
    speed_str = f"{sign}{speed}%"
    return await generate_edge_tts(text, filename, voice, speed_str)

if __name__ == "__main__":
    async def main():
        print("\nTesting English Male TTS...")
        await save_audio("Hello! This is a test.", "test_en_male.wav", lang="en", gender="male")

        print("\nTesting English Female TTS...")
        await save_audio("Hello! This is a test.", "test_en_female.wav", lang="en", gender="female")

        print("\nTesting Vietnamese Male TTS...")
        await save_audio("Xin chào! Đây là bài kiểm tra.", "test_vi_male.wav", lang="vi", gender="male")

        print("\nTesting Vietnamese Female TTS...")
        await save_audio("Xin chào! Đây là bài kiểm tra.", "test_vi_female.wav", lang="vi", gender="female")

    asyncio.run(main())
