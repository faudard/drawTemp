"""DrawTemp 5.0 cinematic authoring and presentation; legacy model remains canonical."""
from .document import CinematicDocument
from .projection import frame_payload, audio_payload

__all__ = ["CinematicDocument", "frame_payload", "audio_payload"]
