"""Research module for merchant interview data collection and analysis."""

from research.interview_schema import (
    InterviewParticipant,
    InterviewInsight,
    InterviewFrequency,
    BusinessImpact,
    CorrelationReport,
)
from research.interview_storage import InterviewStorage
from research.transcription import (
    Transcript,
    TranscriptSegment,
    import_vtt_file,
    transcribe_audio_whisper,
    get_default_transcript_dir,
)
from research.transcript_classifier import (
    TranscriptClassifier,
    TranscriptAnalysis,
    ExtractedPainPoint,
    ExtractedWTPSignal,
    ExtractedProfile,
)

__all__ = [
    # Interview schema
    "InterviewParticipant",
    "InterviewInsight",
    "InterviewFrequency",
    "BusinessImpact",
    "CorrelationReport",
    "InterviewStorage",
    # Transcription
    "Transcript",
    "TranscriptSegment",
    "import_vtt_file",
    "transcribe_audio_whisper",
    "get_default_transcript_dir",
    # Transcript classification
    "TranscriptClassifier",
    "TranscriptAnalysis",
    "ExtractedPainPoint",
    "ExtractedWTPSignal",
    "ExtractedProfile",
]
