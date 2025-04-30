import librosa
from librosa.feature.spectral import rms
import numpy as np
import re
from collections import Counter
from pydub import AudioSegment
import io
import logging


FILLER_WORDS_EN = set(["um", "uh", "er", "like", "you", "know", "i", "mean", "so", "actually"])
FILLER_WORDS_VI = set(["à", "ừ", "ờ", "ư", "thì", "mà", "là", "kiểu", "tức là", "vậy đó"])

SAMPLE_RATE = 22050
FRAME_SIZE = 512
HOP_LENGTH = 256
MIN_SILENCE_DURATION = 0.5  # seconds
SILENCE_THRESHOLD_FACTOR = 0.5

# English ranges
WPM_RANGE_EN = [80, 220, 150]
PAUSE_FREQ_RANGE_EN = [0, 40, 12]
AVG_PAUSE_DURATION_RANGE_EN = [0.2, 1.5, 0.6]
FILLER_WORD_RATIO_RANGE_EN = [0.02, 0.3, 0.06]
PITCH_VARIATION_RANGE_EN = [50, 300, 130]

# Vietnamese ranges (adjusted for Vietnamese speech patterns)
WPM_RANGE_VI = [70, 200, 140]  # Vietnamese may have slightly slower speech
PAUSE_FREQ_RANGE_VI = [0, 45, 15]  # May have more frequent pauses due to tonal patterns
AVG_PAUSE_DURATION_RANGE_VI = [0.2, 1.7, 0.7]  # Similar but slightly adjusted
FILLER_WORD_RATIO_RANGE_VI = [0.02, 0.3, 0.06]  # Similar to English
PITCH_VARIATION_RANGE_VI = [80, 350, 160]  # Higher variation due to tonal nature
DIGITS_AFTER_DECIMAL = 2


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def round_score(num):
    return round(num, DIGITS_AFTER_DECIMAL)

def detect_language(text):
    """
    Detect if text is Vietnamese or English (simplified approach).
    Returns 'vi' for Vietnamese, 'en' for English.
    """
    # Check for Vietnamese-specific characters
    vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ')
    
    # Convert text to lowercase
    text_lower = text.lower()
    
    # Check if any Vietnamese-specific character is present
    for char in vietnamese_chars:
        if char in text_lower:
            return 'vi'
    
    return 'en'  # Default to English if no Vietnamese characters found

def get_filler_words_for_language(language='en'):
    """Return appropriate filler words set based on language."""
    return FILLER_WORDS_VI if language == 'vi' else FILLER_WORDS_EN

def get_ranges_for_language(language='en'):
    """Return appropriate parameter ranges based on language."""
    if language == 'vi':
        return {
            'wpm': WPM_RANGE_VI,
            'pause_freq': PAUSE_FREQ_RANGE_VI,
            'pause_duration': AVG_PAUSE_DURATION_RANGE_VI, 
            'filler_ratio': FILLER_WORD_RATIO_RANGE_VI,
            'pitch_variation': PITCH_VARIATION_RANGE_VI
        }
    else:
        return {
            'wpm': WPM_RANGE_EN,
            'pause_freq': PAUSE_FREQ_RANGE_EN,
            'pause_duration': AVG_PAUSE_DURATION_RANGE_EN,
            'filler_ratio': FILLER_WORD_RATIO_RANGE_EN,
            'pitch_variation': PITCH_VARIATION_RANGE_EN
        }

def load_mp3_as_np(audio_bytes, sr=SAMPLE_RATE):
    """
    Loads an MP3 audio from bytes using pydub and converts to numpy array.
    Avoids librosa.load() which can cause memory issues in Docker.
    """
    try:
        # Load audio with pydub which has better memory management
        audio_file = io.BytesIO(audio_bytes)
        audio_segment = AudioSegment.from_file(audio_file)
        
        # Check if audio loaded correctly
        if not audio_segment or len(audio_segment) == 0:
            logger.error("Failed to load audio data - empty audio segment")
            return None, None
            
        # Get original sample rate
        original_sr = audio_segment.frame_rate
        logger.info(f"Audio loaded: duration={len(audio_segment)/1000}s, sr={original_sr}")
        
        # Convert to mono if stereo
        if audio_segment.channels > 1:
            audio_segment = audio_segment.set_channels(1)
            
        # Convert to numpy array (scaled to [-1.0, 1.0] range)
        samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
        # Convert from pydub's default bit depth to float in [-1, 1]
        samples = samples / (2**(audio_segment.sample_width * 8 - 1))
        
        # Resample if needed using a simpler approach
        if original_sr != sr:
            try:
                # Simple resampling without librosa
                # Calculate the resampling ratio
                ratio = sr / original_sr
                # Use numpy's interp function for basic resampling (less memory intensive)
                original_length = len(samples)
                new_length = int(original_length * ratio)
                resampled_indices = np.linspace(0, original_length - 1, new_length)
                samples = np.interp(resampled_indices, np.arange(original_length), samples)
                logger.info(f"Audio resampled to {sr}Hz using numpy")
            except Exception as e:
                logger.error(f"Resampling failed: {e}, falling back to original sample rate")
                sr = original_sr
                
        return samples, sr
        
    except MemoryError:
        logger.error("Memory error while loading audio - file may be too large")
        return None, None
    except Exception as e:
        logger.error(f"Error loading audio from bytes: {e}", exc_info=True)
        return None, None

def extract_audio_features(audio_bytes):
    """Extract basic audio features for analysis with improved memory efficiency."""
    y, sr = load_mp3_as_np(audio_bytes, sr=SAMPLE_RATE)
    
    if y is None or sr is None:
        logger.error("Failed to load audio data for feature extraction.")
        raise ValueError("Failed to load audio data")
        
    # Get audio duration
    duration = len(y) / sr if sr > 0 else 0
    logger.info(f"Audio duration: {duration:.2f} seconds")
    
    # Set reasonable maximum duration to prevent memory issues
    MAX_DURATION = 300  # 5 minutes
    if duration > MAX_DURATION:
        logger.warning(f"Audio too long ({duration:.2f}s), truncating to {MAX_DURATION}s")
        y = y[:int(MAX_DURATION * sr)]
        duration = MAX_DURATION
    
    try:
        # Calculate RMS energy with smaller frame size for memory efficiency
        energy = rms(
            y=y, 
            frame_length=min(FRAME_SIZE, 1024),  # Use smaller frame size
            hop_length=min(HOP_LENGTH, 512)  # Use smaller hop length
        )[0].astype(np.float32)
        
        # Use more efficient pitch tracking with bounds
        if len(y) > 0:
            try:
                # For pitch extraction, use a more memory-efficient approach
                f0, voiced_flag, voiced_probs = librosa.pyin(
                    y,
                    fmin=librosa.note_to_hz('C2'),
                    fmax=librosa.note_to_hz('C7'),
                    sr=sr,
                    hop_length=HOP_LENGTH * 2,  # Increase hop length for efficiency
                    fill_na=0.0
                )
                if f0 is None:
                    f0 = np.zeros(len(y) // HOP_LENGTH + 1)
            except Exception as e:
                logger.warning(f"Failed to extract pitch: {e}, using zero array")
                f0 = np.zeros(len(y) // HOP_LENGTH + 1)
        else:
            f0 = np.array([0.0])
            
        logger.info("Extracted energy and pitch features.")
        return y, sr, duration, energy, f0
    except Exception as e:
        logger.error(f"Error extracting audio features: {e}", exc_info=True)
        # Return minimal features to allow the rest of the pipeline to continue
        energy = np.array([0.0])
        f0 = np.array([0.0])
        return y, sr, duration, energy, f0

def detect_silence(energy, sr, hop_length=HOP_LENGTH, threshold_factor=SILENCE_THRESHOLD_FACTOR):
    """Detect silence segments in audio with improved error handling."""
    try:
        if len(energy) < 2:
            return []  # Not enough data for silence detection
            
        silence_threshold = np.mean(energy) * threshold_factor
        
        # Simple silence detection instead of using librosa.effects.split
        # to avoid potential memory issues
        is_silence = energy < silence_threshold
        silence_segments = []
        
        in_silence = False
        silence_start = 0
        
        for i, silent in enumerate(is_silence):
            if silent and not in_silence:
                in_silence = True
                silence_start = i
            elif not silent and in_silence:
                in_silence = False
                silence_end = i
                duration = (silence_end - silence_start) * hop_length / sr
                if duration >= MIN_SILENCE_DURATION:
                    silence_segments.append((
                        silence_start * hop_length / sr,
                        silence_end * hop_length / sr
                    ))
        
        # Check for silence at the end
        if in_silence:
            silence_end = len(is_silence)
            duration = (silence_end - silence_start) * hop_length / sr
            if duration >= MIN_SILENCE_DURATION:
                silence_segments.append((
                    silence_start * hop_length / sr,
                    silence_end * hop_length / sr
                ))
                
        return silence_segments
    except Exception as e:
        logger.error(f"Error detecting silence: {e}", exc_info=True)
        return []  # Return empty list on error

def calculate_wpm(num_words, duration):
    """Calculate words per minute."""
    if duration > 0:
        return num_words / (duration / 60)
    return 0

def count_filler_words(transcript, language='en'):
    """Count filler words in transcript."""
    filler_words = get_filler_words_for_language(language)
    words = transcript.lower().split()
    count = sum(1 for word in words if word in filler_words)
    return count

def calculate_pause_frequency(silence_segments, duration):
    """Calculate pause frequency (pauses per minute)."""
    if duration > 0:
        return len(silence_segments) / (duration / 60)
    return 0

def calculate_average_pause_duration(silence_segments):
    """Calculate average pause duration in seconds."""
    if silence_segments:
        total_duration = sum(end - start for start, end in silence_segments)
        return total_duration / len(silence_segments)
    return 0

def calculate_pitch_variation(f0):
    """Calculate pitch variation (standard deviation of pitch)."""
    f0_voiced = f0[f0 > 0]
    if len(f0_voiced) > 1:
        return np.std(f0_voiced)
    return 0

def detect_repetitions(transcript):
    """
    Detect excessive word repetitions in transcript.
    Returns tuple of (repetition_count, repeated_words)
    """
    words = re.findall(r'\b\w+\b', transcript.lower())
    word_counts = Counter(words)
    
    # Identify words that appear more than 3 times and aren't common function words
    common_words = {'the', 'a', 'an', 'and', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 
                   'of', 'là', 'và', 'thì', 'ở', 'trong', 'ngoài', 'đó', 'này', 'kia'}
    
    repetitions = {word: count for word, count in word_counts.items() 
                  if count > 3 and word not in common_words and len(word) > 1}
    
    return sum(repetitions.values()), list(repetitions.keys())

def calculate_speech_rate_consistency(audio_bytes):
    """
    Calculate speech rate consistency with memory-efficient processing.
    """
    try:
        y, sr = load_mp3_as_np(audio_bytes, sr=SAMPLE_RATE)
        if y is None or sr is None or len(y) < sr:
            return 1.0  # Default to consistent if audio invalid
            
        # Use smaller chunks for memory efficiency
        chunk_duration = 3  # seconds
        chunk_samples = int(chunk_duration * sr)
        
        # Limit to analyzing at most 60 seconds of audio
        max_samples = min(len(y), 60 * sr)
        y = y[:max_samples]
        
        chunks = [y[i:i+chunk_samples] for i in range(0, len(y), chunk_samples) 
                 if i+chunk_samples//2 <= len(y)]
        
        if len(chunks) < 2:
            return 1.0  # Not enough data for analysis
        
        # Simplified rate analysis
        chunk_rates = []
        for chunk in chunks:
            try:
                # Use a simpler onset detection method
                onset_env = librosa.onset.onset_strength(
                    y=chunk, 
                    sr=sr,
                    hop_length=512,  # Larger hop length for memory efficiency
                    n_fft=1024  # Smaller FFT size
                )
                
                # Simple peak picking instead of onset detect
                peaks = librosa.util.peak_pick(onset_env, 3, 3, 3, 5, 0.5, 10)
                
                if len(peaks) > 0:
                    rate = len(peaks) / chunk_duration
                    chunk_rates.append(rate)
            except Exception as e:
                logger.warning(f"Error processing chunk: {e}")
                continue
        
        # Ensure we have rates to analyze
        if not chunk_rates or len(chunk_rates) < 2:
            return 1.0
            
        # Calculate consistency
        mean_rate = np.mean(chunk_rates)
        if mean_rate > 0:
            cv = np.std(chunk_rates) / mean_rate
            consistency = max(0, min(1, 1 - (cv / 0.5)))
            return consistency
        
        return 1.0
    except Exception as e:
        logger.error(f"Error calculating speech rate consistency: {e}", exc_info=True)
        return 1.0  # Default to consistent on error

def detect_ai_generated_text(transcript):
    """
    Detect if transcript appears to be AI-generated.
    Returns a score between 0 and 1, where 1 is likely human-generated.
    """
    # Feature 1: Lexical diversity
    words = re.findall(r'\b\w+\b', transcript.lower())
    if len(words) < 10:
        return 1.0  # Not enough text to analyze
        
    unique_words = set(words)
    lexical_diversity = len(unique_words) / len(words)
    
    # Feature 2: Sentence length variation
    sentences = re.split(r'[.!?]+', transcript)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) < 2:
        return 1.0  # Not enough sentences to analyze
        
    sent_lengths = [len(re.findall(r'\b\w+\b', s)) for s in sentences]
    sent_length_variation = np.std(sent_lengths) / max(1, np.mean(sent_lengths))
    
    # Feature 3: Repetition of phrases
    three_grams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
    three_gram_counts = Counter(three_grams)
    repetitive_phrases = sum(1 for count in three_gram_counts.values() if count > 1)
    repetition_score = min(1, repetitive_phrases / max(1, len(three_grams) / 10))
    
    # Feature 4: Over-formality score
    language = detect_language(transcript)
    formal_markers_en = ['therefore', 'thus', 'consequently', 'furthermore', 'moreover', 'however', 'nevertheless', 'regarding']
    formal_markers_vi = ['tuy nhiên', 'mặc dù', 'vì vậy', 'do đó', 'theo đó', 'ngoài ra', 'đồng thời', 'xét về']
    
    formal_markers = formal_markers_vi if language == 'vi' else formal_markers_en
    formal_count = sum(1 for word in words if word.lower() in formal_markers)
    formality_score = min(1, formal_count / max(1, len(words) / 20))
    
    # Feature 5: Natural disfluencies
    disfluencies_en = ['um', 'uh', 'like', 'you know', 'i mean', 'sort of']
    disfluencies_vi = ['à', 'ừ', 'kiểu', 'thì là', 'tức là']
    
    disfluencies = disfluencies_vi if language == 'vi' else disfluencies_en
    disfluency_count = sum(1 for word in words if word.lower() in disfluencies)
    disfluency_score = min(1, disfluency_count / max(1, len(words) / 30))
    
    # Calculate combined score
    # For human speech: higher lexical diversity, higher sentence variation, lower repetition, lower formality, higher disfluencies
    human_score = (lexical_diversity * 0.3 + 
                   sent_length_variation * 0.2 + 
                   (1 - repetition_score) * 0.2 + 
                   (1 - formality_score) * 0.15 + 
                   disfluency_score * 0.15)
    
    # Adjust the scale to better reflect human vs AI probability
    adjusted_score = min(1.0, max(0.0, human_score))
    return adjusted_score

def analyze_audio_transcript_mismatch(audio_bytes, transcript):
    """
    Detect if the audio and transcript match each other.
    Returns a score between 0 and 1, where 1 means they likely match.
    """
    # Extract audio features
    y, sr, duration, energy, _ = extract_audio_features(audio_bytes)
    
    # Transcript features
    word_count = len(transcript.split())
    expected_duration = word_count * 0.5  # Average of 0.5 seconds per word
    
    # Check 1: Duration match
    duration_ratio = min(duration, expected_duration) / max(duration, expected_duration)
    
    # Check 2: Energy pattern
    # Split audio into num_segments equal parts, matching the number of sentences
    sentences = re.split(r'[.!?]+', transcript)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    num_segments = max(len(sentences), 3)  # At least 3 segments for analysis
    segment_length = len(energy) // num_segments
    
    if segment_length < 5:  # Need enough frames for analysis
        return 0.8  # Default to reasonable match if not enough data
    
    segment_energies = [np.mean(energy[i:i+segment_length]) for i in range(0, len(energy), segment_length) if i+segment_length <= len(energy)]
    
    # Check if energy pattern has reasonable variation
    energy_variation = np.std(segment_energies) / np.mean(segment_energies) if np.mean(segment_energies) > 0 else 0
    
    # Natural speech energy variation is typically 0.2-0.6
    energy_match_score = min(1.0, energy_variation / 0.4) if energy_variation <= 0.6 else max(0.0, 1.0 - (energy_variation - 0.6) / 0.4)
    
    # Check 3: Silence distribution
    # Natural speech has pauses between sentences
    silence_segments = detect_silence(energy, sr)
    expected_silence_count = max(1, len(sentences) - 1)  # Expect silence between sentences
    silence_ratio = min(len(silence_segments), expected_silence_count) / expected_silence_count
    
    # Calculate final mismatch score
    match_score = (duration_ratio * 0.4 + energy_match_score * 0.4 + silence_ratio * 0.2)
    
    return min(1.0, max(0.0, match_score))

def normalize_score(value, range_values):
    """
    Normalize a score to [0, 1] based on how close 'value' is to the ideal within [min_val, max_val].
    If ideal_val is not specified, assumes best performance is at the midpoint.
    Penalizes values outside the range more sharply.
    """
    min_val, max_val, ideal_val = range_values
    
    if ideal_val is None:
        ideal_val = (min_val + max_val) / 2

    if min_val == max_val:
        return 1.0  # Avoid division by zero, assume perfect score

    ideal_range = (max_val - min_val)
    if value < min_val:
        return max(0.0, 1 - abs(min_val - value) / ideal_range)
    elif value > max_val:
        return max(0.0, 1 - abs(value - max_val) / ideal_range)
    else:
        # Inside range, now penalize based on distance from ideal
        distance = abs(value - ideal_val)
        return max(0.0, 1 - (distance / ideal_range))

def evaluate_fluency(audio_bytes, transcript):
    """
    Evaluate speech fluency with improved error handling.
    """
    try:
        # Detect language
        language = detect_language(transcript)
        logger.info(f"Detected language: {language}")
        
        # Extract audio features with protection against errors
        try:
            y, sr, duration, energy, f0 = extract_audio_features(audio_bytes)
        except Exception as e:
            logger.error(f"Failed to extract audio features: {e}")
            # Return minimal results if audio processing fails
            return {
                "language": language,
                "overall_score": "F",
                "error": "Audio processing failed",
                "wpm": 0,
                "pause_frequency": 0,
                "average_pause_duration": 0,
                "filler_word_count": 0,
                "pitch_variation": 0,
                "repetition_count": 0,
                "repetitive_words": [],
                "speech_rate_consistency": 0
            }
        
        # Safety checks
        if duration <= 0:
            logger.error("Invalid audio duration")
            duration = 1.0  # Prevent division by zero
            
        # Detect silence segments with error handling
        try:
            silence_segments = detect_silence(energy, sr)
        except Exception as e:
            logger.error(f"Failed to detect silence: {e}")
            silence_segments = []
            
        # Basic metrics with error handling
        num_words = len(transcript.split())
        wpm = calculate_wpm(num_words, duration)
        pause_freq = calculate_pause_frequency(silence_segments, duration) 
        avg_pause_duration = calculate_average_pause_duration(silence_segments)
        filler_count = count_filler_words(transcript, language)
        
        # Pitch variation with error handling
        try:
            pitch_variation = calculate_pitch_variation(f0)
        except Exception as e:
            logger.error(f"Failed to calculate pitch variation: {e}")
            pitch_variation = 0
            
        # Get appropriate ranges for normalization
        ranges = get_ranges_for_language(language)
        
        # Calculate basic fluency score with bounds checking
        try:
            basic_fluency_score = (
                0.25 * normalize_score(wpm, ranges['wpm']) +
                0.25 * normalize_score(pause_freq, ranges['pause_freq']) +
                0.2 * normalize_score(avg_pause_duration, ranges['pause_duration']) +
                0.2 * normalize_score(filler_count / max(1, num_words), ranges['filler_ratio']) +
                0.1 * normalize_score(pitch_variation, ranges['pitch_variation'])
            )
            
            # Ensure score is within valid bounds
            basic_fluency_score = max(0, min(1, basic_fluency_score))
        except Exception as e:
            logger.error(f"Error calculating fluency score: {e}")
            basic_fluency_score = 0.0
            
        scores = ["A", "B", "C", "D", "F", "F"]
        score_index = min(5, max(0, int(5 - basic_fluency_score * 5)))
        score = scores[score_index]
        
        # Additional metrics
        try:
            repetition_count, repetitive_words = detect_repetitions(transcript)
        except Exception as e:
            logger.error(f"Error detecting repetitions: {e}")
            repetition_count, repetitive_words = 0, []
            
        # Calculate speech rate consistency with error handling
        try:
            speech_rate_consistency = calculate_speech_rate_consistency(audio_bytes)
        except Exception as e:
            logger.error(f"Error calculating speech rate consistency: {e}")
            speech_rate_consistency = 1.0
            
        # Prepare result dictionary
        result = {
            "language": language,
            "overall_score": score,
            "wpm": round_score(wpm),
            "pause_frequency": round_score(pause_freq),
            "average_pause_duration": round_score(avg_pause_duration),
            "filler_word_count": round_score(filler_count),
            "pitch_variation": round_score(pitch_variation),
            "repetition_count": repetition_count,
            "repetitive_words": repetitive_words,
            "speech_rate_consistency": round_score(speech_rate_consistency)
        }
        
        # For Vietnamese, add AI detection with error handling
        if language == 'vi':
            try:
                ai_detection_score = detect_ai_generated_text(transcript)
                audio_transcript_match = analyze_audio_transcript_mismatch(audio_bytes, transcript)
                
                result["human_likelihood_score"] = ai_detection_score
                result["audio_transcript_match"] = audio_transcript_match
                
                # Adjust overall score
                if ai_detection_score < 0.5:
                    result["overall_score"] = scores[min(5, max(0, score_index + 1))]
                
                if audio_transcript_match < 0.7:
                    result["overall_score"] = scores[min(5, max(0, score_index + 1))]
            except Exception as e:
                logger.error(f"Error calculating AI detection scores: {e}")
                result["human_likelihood_score"] = 1.0
                result["audio_transcript_match"] = 1.0
                
        return result
    except Exception as e:
        logger.error(f"Unexpected error in evaluate_fluency: {e}", exc_info=True)
        return {
            "language": "en",
            "overall_score": "F",
            "error": f"Evaluation failed: {str(e)}",
            "wpm": 0,
            "pause_frequency": 0,
            "average_pause_duration": 0,
            "filler_word_count": 0, 
            "pitch_variation": 0,
            "repetition_count": 0,
            "repetitive_words": [],
            "speech_rate_consistency": 0
        }

def get_fluency_feedback(fluency_results):
    """
    Generate human-readable feedback based on fluency results.
    """
    feedback = []
    language = fluency_results["language"]
    
    # Speaking rate
    wpm = fluency_results["wpm"]
    ranges = get_ranges_for_language(language)
    wpm_min, wpm_max, _ = ranges["wpm"]
    
    if wpm < wpm_min:
        feedback.append(f"Your speaking rate of {wpm:.1f} words per minute is slower than the recommended {wpm_min}-{wpm_max} wpm range. Consider practicing speaking at a slightly faster pace.")
    elif wpm > wpm_max:
        feedback.append(f"Your speaking rate of {wpm:.1f} words per minute is faster than the recommended {wpm_min}-{wpm_max} wpm range. Try slowing down a bit to improve clarity.")
    
    # Pauses
    pause_freq = fluency_results["pause_frequency"]
    avg_pause = fluency_results["average_pause_duration"]
    
    if pause_freq > ranges["pause_freq"][1]:
        feedback.append(f"You're pausing too frequently ({pause_freq:.1f} pauses per minute). Try to speak in longer, more complete phrases.")
    
    if avg_pause > ranges["pause_duration"][1]:
        feedback.append(f"Your pauses are quite long (average {avg_pause:.2f} seconds). Work on reducing pause duration to maintain listener engagement.")
    
    # Filler words
    filler_count = fluency_results["filler_word_count"]
    if filler_count > 0:
        feedback.append(f"You used {filler_count} filler words. Reducing these will make your speech sound more confident.")
    
    # Repetitions
    repetition_count = fluency_results["repetition_count"]
    if repetition_count > 5:
        feedback.append(f"You repeated some words excessively ({repetition_count} instances). Try to use more varied vocabulary.")
    
    # Speech rate consistency
    consistency = fluency_results["speech_rate_consistency"]
    if consistency < 0.6:
        feedback.append("Your speaking pace varies considerably. Practice maintaining a more consistent rate of speech.")
    
    # For Vietnamese only
    if language == 'vi':
        human_score = fluency_results.get("human_likelihood_score", 1.0)
        if human_score < 0.7:
            feedback.append("Your speech patterns seem somewhat artificial or rehearsed. Try to speak more naturally and conversationally.")
        
        match_score = fluency_results.get("audio_transcript_match", 1.0)
        if match_score < 0.7:
            feedback.append("There appears to be some mismatch between your audio and transcript. Please ensure you're speaking the exact words in the transcript.")
    
    return feedback

if __name__ == "__main__":
    audio_file = "test.mp3"  # Use your existing MP3 file
    spoken_transcript = "There are no libraries in my neighborhood because I'm living in rural area, so the last time I went there is five months ago."

    # Convert file to bytes
    with open(audio_file, 'rb') as f:
        audio_bytes = f.read()
    # Example with English
    fluency_results = evaluate_fluency(audio_bytes, spoken_transcript)
    print("Fluency Evaluation:")
    for key, value in fluency_results.items():
        print(f"{key}: {value}")
    
    # Generate feedback
    feedback = get_fluency_feedback(fluency_results)
    print("\nFeedback:")
    for item in feedback:
        print(f"- {item}")