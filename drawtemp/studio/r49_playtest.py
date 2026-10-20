"""R49.B3 local Player lifecycle: detached launches are not verified playtests.

Qt-free state tracker used by the Qt Studio supervisor. No session mutation,
sidecar files, telemetry, process commands from content or persistent paths.
"""
from __future__ import annotations

import codecs
from dataclasses import dataclass
from pathlib import Path

from drawtemp.studio.r18_navigation import WORKSPACES
from drawtemp.studio.r49_workspaces import FOCUS_REGIONS


TERMINAL = frozenset({"finished", "failed", "stopped"})
ACTIVE = frozenset({"starting", "running", "stopping"})
CHANNELS = ("stdout", "stderr")


@dataclass(frozen=True)
class EditorReturnContext:
    workspace: str
    resource_keys: tuple[tuple[str, str, str], ...]
    focus_region: str | None
    document_path: str
    session_identity: int

    def __post_init__(self):
        if self.workspace not in WORKSPACES:
            raise ValueError("Invalid Studio workspace")
        if self.focus_region is not None and self.focus_region not in FOCUS_REGIONS:
            raise ValueError("Invalid Studio focus region")
        if not isinstance(self.document_path, str) or not self.document_path.strip():
            raise ValueError("Playtest requires a saved document")
        if type(self.session_identity) is not int:
            raise ValueError("Invalid session identity")
        if not isinstance(self.resource_keys, tuple):
            raise ValueError("Resource keys must be a tuple")
        if any(not isinstance(k, tuple) or len(k) != 3 or
               any(not isinstance(v, str) for v in k)
               for k in self.resource_keys):
            raise ValueError("Invalid resource identity")

    def matches(self, session, content_path) -> bool:
        if content_path is None:
            return False
        return (id(session) == self.session_identity and
                Path(content_path).resolve(strict=False) ==
                Path(self.document_path).resolve(strict=False))


class PlaytestRun:
    """One supervised run; exit 0 after *started* is the only success.

    Status: idle -> starting -> running -> finished|failed
                        stopping -> stopped|failed
    A failure to start must not be reported as a completed playtest.
    """

    def __init__(self, *, max_output_chars=4096):
        if type(max_output_chars) is not int or not 128 <= max_output_chars <= 65536:
            raise ValueError("Invalid output budget")
        self.max_output_chars = max_output_chars
        self.phase = "idle"
        self.context: EditorReturnContext | None = None
        self.exit_code: int | None = None
        self.reason = ""
        self._logs = {name: "" for name in CHANNELS}
        self._truncated = {name: False for name in CHANNELS}
        self._decoders = {
            name: codecs.getincrementaldecoder("utf-8")("replace")
            for name in CHANNELS
        }

    @property
    def active(self) -> bool:
        return self.phase in ACTIVE

    @property
    def successful(self) -> bool:
        return self.phase == "finished" and self.exit_code == 0

    def begin(self, context: EditorReturnContext):
        if self.active:
            raise RuntimeError("Playtest already active")
        if not isinstance(context, EditorReturnContext):
            raise TypeError("EditorReturnContext required")
        self.phase = "starting"
        self.context = context
        self.exit_code = None
        self.reason = ""
        self._logs = {name: "" for name in CHANNELS}
        self._truncated = {name: False for name in CHANNELS}
        self._decoders = {
            name: codecs.getincrementaldecoder("utf-8")("replace")
            for name in CHANNELS
        }

    def started(self):
        if self.phase != "starting":
            return False
        self.phase = "running"
        return True

    def append(self, channel: str, chunk: bytes | str):
        if channel not in CHANNELS:
            raise ValueError("Unknown Player diagnostic channel")
        if not isinstance(chunk, (bytes, str)):
            raise TypeError("Player output must be bytes or text")
        if not self.active:
            return
        if isinstance(chunk, bytes):
            # Bound parsing costs for an exceptionally noisy child process.
            if len(chunk) > self.max_output_chars * 4:
                self._truncated[channel] = True
                chunk = chunk[-self.max_output_chars * 4:]
                self._decoders[channel].reset()
            piece = self._decoders[channel].decode(chunk)
        else:
            piece = chunk
        text = self._logs[channel] + piece
        if len(text) > self.max_output_chars:
            self._truncated[channel] = True
            text = text[-self.max_output_chars:]
        self._logs[channel] = text

    def stream(self, channel: str) -> str:
        if channel not in CHANNELS:
            raise ValueError("Unknown Player diagnostic channel")
        return (("[sortie tronquée]\n" if self._truncated[channel] else "") +
                self._logs[channel])

    def request_stop(self) -> bool:
        if self.phase in ("starting", "running"):
            self.phase = "stopping"
            return True
        return False

    def note_error(self, reason: str):
        if self.active:
            self.reason = str(reason)[:500]

    def failed_to_start(self, reason: str):
        if self.phase != "starting":
            return False
        self.reason = str(reason)[:500]
        self.phase = "failed"
        return True

    def finish(self, exit_code: int, *, crashed=False):
        if not self.active:
            return False
        if type(exit_code) is not int:
            raise ValueError("Exit code must be an integer")
        stopping = self.phase == "stopping"
        starting = self.phase == "starting"
        self.exit_code = exit_code
        if stopping:
            self.phase = "stopped"
        elif not crashed and not starting and not self.reason and exit_code == 0:
            self.phase = "finished"
        else:
            self.phase = "failed"
            if not self.reason:
                self.reason = ("Player stopped before startup was confirmed"
                               if starting else "Player crashed or exited with an error")
        return True

    def report(self) -> str:
        labels = {
            "idle": "Aucun playtest démarré",
            "starting": "Player en cours de démarrage",
            "running": "Player en cours d'exécution",
            "stopping": "Arrêt du Player demandé",
            "finished": "Player terminé normalement",
            "failed": "Échec du Player",
            "stopped": "Playtest interrompu à la demande",
        }
        lines = [labels[self.phase]]
        if self.exit_code is not None:
            lines.append("Code de sortie : " + str(self.exit_code))
        if self.reason:
            lines.append("Diagnostic : " + self.reason)
        for channel in CHANNELS:
            output = self.stream(channel).strip()
            if output:
                lines.append(channel.upper() + " (local, borné) :\n" + output)
        lines.append("Ce rapport ne certifie ni les fonctionnalités jouées ni l'export.")
        return "\n\n".join(lines)
