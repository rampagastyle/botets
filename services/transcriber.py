# Kept for compatibility with older imports. AI transcription is now handled by Gemini video analysis.
from services.gemini import analyze_video


def transcribe_file_to_vtt(video_path, out_vtt, language='ru') -> bool:
    # Gemini metadata generation intentionally does not create local speech-to-text files.
    # Source captions remain the lowest-load subtitle path.
    return False
