import sys
import io
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence

r = sr.Recognizer()

def transcribe_audio(audio_file, language):
    """
    Transcribes the given audio file-like object using Google Speech Recognition.
    
    Parameters:
        audio_file: A file-like object containing WAV data.
        language: The language code (e.g., "en-US").
        
    Returns:
        The transcribed text.
    """
    with sr.AudioFile(audio_file) as source:
        audio_listened = r.record(source)
        text = r.recognize_google(audio_listened, language=language)
    return text

def get_large_audio_transcription_on_silence(audio_data, language):
    """
    Processes the provided sr.AudioData by converting it to an AudioSegment,
    splitting it based on silence, and transcribing each chunk. It returns the
    combined transcription text.
    
    Parameters:
        audio_data: An instance of sr.AudioData (recorded speech).
        language: The language code used for transcription.
    """
    # Convert the audio_data to WAV bytes and wrap it in a BytesIO object
    wav_bytes = audio_data.get_wav_data()
    wav_buffer = io.BytesIO(wav_bytes)
    
    # Create an AudioSegment from the in-memory WAV data
    sound = AudioSegment.from_file(wav_buffer, format="wav")
    
    # Split the audio where silence is at least 500ms long with a threshold relative to the audio's dBFS
    chunks = split_on_silence(
        sound,
        min_silence_len=500,
        silence_thresh=sound.dBFS - 12,
        keep_silence=500,
    )
    
    whole_text = ""
    for i, chunk in enumerate(chunks, start=1):
        # Export each chunk into an in-memory WAV file
        chunk_buffer = io.BytesIO()
        chunk.export(chunk_buffer, format="wav")
        chunk_buffer.seek(0)
        try:
            text = transcribe_audio(chunk_buffer, language)
        except sr.UnknownValueError as e:
            print("Error:", str(e))
        else:
            text = f"{text.capitalize()}. "
            print(f"Chunk {i}:", text)
            whole_text += text
    return whole_text

def live_recognition(language):
    """
    Listens to live speech from the microphone and stops recording when a silence 
    duration longer than 3 seconds is detected. This is achieved by setting the recognizer's 
    pause_threshold to 3 seconds.
    
    Parameters:
        language: The language code for transcription (e.g., "en-US")
        
    Returns:
        The transcription string.
    """
    with sr.Microphone() as source:
        print("Calibrating ambient noise... Please be silent for 1 second.")
        r.adjust_for_ambient_noise(source, duration=1)
        
        print("Please talk! (Recording will auto-stop after 3 seconds of silence)")
        # Set pause_threshold to 3 seconds so that once speech starts,
        # 3 seconds of silence will stop the recording.
        r.pause_threshold = 3.0
        
        # timeout: Maximum seconds to wait for phrase to start.
        # Once speech is detected, pause_threshold manages when to stop.
        try:
            audio_data = r.listen(source, timeout=5)
        except sr.WaitTimeoutError:
            print("No speech detected within timeout period.")
            return ""
    
    transcription = get_large_audio_transcription_on_silence(audio_data, language)
    print(transcription)
    return transcription
