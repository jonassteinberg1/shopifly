"""Transcription module for interview recordings.

Supports two transcription paths:
- Path A: Import VTT transcripts from Zoom (preferred)
- Path B: Local transcription using OpenAI Whisper (fallback)

Both paths produce a unified Transcript JSON format for downstream processing.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single segment of transcribed speech."""

    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str = Field(description="Transcribed text for this segment")


class Transcript(BaseModel):
    """Unified transcript format for interview recordings."""

    source_file: str = Field(description="Original source file (VTT or audio)")
    transcribed_at: datetime = Field(default_factory=datetime.utcnow)
    method: str = Field(description="Transcription method: 'zoom_vtt' or 'whisper'")
    model: Optional[str] = Field(default=None, description="Whisper model used (if applicable)")
    duration_seconds: Optional[float] = Field(default=None, description="Total duration")
    language: str = Field(default="en", description="Detected/assumed language")
    segments: list[TranscriptSegment] = Field(default_factory=list)
    full_text: str = Field(default="", description="Complete transcript text")
    participant_id: Optional[str] = Field(default=None, description="Linked participant ID")

    def to_json_file(self, output_path: Path) -> Path:
        """Save transcript to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(self.model_dump_json(indent=2))
        return output_path

    @classmethod
    def from_json_file(cls, path: Path) -> "Transcript":
        """Load transcript from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


def parse_vtt_timestamp(timestamp: str) -> float:
    """Parse VTT timestamp (HH:MM:SS.mmm) to seconds."""
    # Handle both HH:MM:SS.mmm and MM:SS.mmm formats
    parts = timestamp.strip().split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    else:
        raise ValueError(f"Invalid VTT timestamp: {timestamp}")


def parse_vtt(vtt_content: str) -> list[TranscriptSegment]:
    """Parse VTT content into transcript segments.

    VTT format:
    WEBVTT

    00:00:00.000 --> 00:00:05.000
    First line of speech.

    00:00:05.500 --> 00:00:12.000
    Second line of speech.
    """
    segments = []

    # Split into blocks (separated by blank lines)
    blocks = re.split(r"\n\s*\n", vtt_content.strip())

    for block in blocks:
        lines = block.strip().split("\n")

        # Skip header and empty blocks
        if not lines or lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE"):
            continue

        # Find timestamp line (contains "-->")
        timestamp_line = None
        text_lines = []

        for i, line in enumerate(lines):
            if "-->" in line:
                timestamp_line = line
                text_lines = lines[i + 1 :]
                break

        if not timestamp_line:
            continue

        # Parse timestamp
        try:
            # Handle optional cue settings after timestamp
            timestamp_part = timestamp_line.split("-->")
            start_str = timestamp_part[0].strip()
            # End might have additional settings, take only the time part
            end_str = timestamp_part[1].strip().split()[0]

            start = parse_vtt_timestamp(start_str)
            end = parse_vtt_timestamp(end_str)

            # Join text lines, removing any HTML-like tags
            text = " ".join(text_lines)
            text = re.sub(r"<[^>]+>", "", text)  # Remove HTML tags
            text = text.strip()

            if text:
                segments.append(TranscriptSegment(start=start, end=end, text=text))

        except (ValueError, IndexError) as e:
            # Skip malformed segments
            continue

    return segments


def import_vtt_file(
    vtt_path: Path,
    participant_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Transcript:
    """Import a Zoom VTT transcript file and convert to unified format.

    Args:
        vtt_path: Path to the VTT file
        participant_id: Optional participant ID to link
        output_dir: Optional output directory for JSON (defaults to data/interviews/transcripts/)

    Returns:
        Transcript object
    """
    if not vtt_path.exists():
        raise FileNotFoundError(f"VTT file not found: {vtt_path}")

    with open(vtt_path, "r", encoding="utf-8") as f:
        vtt_content = f.read()

    segments = parse_vtt(vtt_content)

    # Build full text from segments
    full_text = " ".join(seg.text for seg in segments)

    # Calculate duration from last segment
    duration = segments[-1].end if segments else None

    transcript = Transcript(
        source_file=str(vtt_path),
        method="zoom_vtt",
        duration_seconds=duration,
        segments=segments,
        full_text=full_text,
        participant_id=participant_id,
    )

    # Save to output directory if specified
    if output_dir:
        output_path = output_dir / f"{vtt_path.stem}.json"
        transcript.to_json_file(output_path)

    return transcript


def transcribe_audio_whisper(
    audio_path: Path,
    model_name: str = "base",
    participant_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Transcript:
    """Transcribe an audio file using OpenAI Whisper.

    Args:
        audio_path: Path to the audio file (mp3, wav, m4a, etc.)
        model_name: Whisper model to use ('tiny', 'base', 'small', 'medium', 'large')
        participant_id: Optional participant ID to link
        output_dir: Optional output directory for JSON

    Returns:
        Transcript object

    Raises:
        ImportError: If openai-whisper is not installed
        FileNotFoundError: If audio file doesn't exist
    """
    try:
        import whisper
    except ImportError:
        raise ImportError(
            "openai-whisper is not installed. Install with: pip install openai-whisper"
        )

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Load model and transcribe
    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path))

    # Convert Whisper segments to our format
    segments = []
    for seg in result.get("segments", []):
        segments.append(
            TranscriptSegment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip(),
            )
        )

    # Get full text
    full_text = result.get("text", "").strip()

    # Calculate duration from last segment or audio file
    duration = segments[-1].end if segments else None

    transcript = Transcript(
        source_file=str(audio_path),
        method="whisper",
        model=model_name,
        duration_seconds=duration,
        language=result.get("language", "en"),
        segments=segments,
        full_text=full_text,
        participant_id=participant_id,
    )

    # Save to output directory if specified
    if output_dir:
        output_path = output_dir / f"{audio_path.stem}.json"
        transcript.to_json_file(output_path)

    return transcript


def get_default_transcript_dir() -> Path:
    """Get the default transcript output directory."""
    # Try to find project root
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent / "data" / "interviews" / "transcripts"
    # Fallback to current directory
    return current / "data" / "interviews" / "transcripts"
