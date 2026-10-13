"""Optional, low-overhead Tk latency observations for real Studio callbacks.

Enable by starting the Studio with SPOREBOUND_UI_TRACE=/absolute/path/events.jsonl.
Never emit project content, paths, identifiers of actors or dialogue text.
The observation is callback-start -> next Tk idle, NOT physical input-to-photon.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter

TRACE_PATH = os.environ.get("SPOREBOUND_UI_TRACE", "")


def begin_ui():
    """Return a timer only when the author explicitly enables tracing."""
    return perf_counter() if TRACE_PATH else None


def finish_ui(operation, started, widget, *, counts=None):
    """Record callback duration then defer event-loop completion to Tk idle.

    If the widget is destroyed before idle, the sample is safely discarded.
    This is diagnostic instrumentation, never a correctness dependency.
    """
    if started is None:
        return
    callback_done = perf_counter()
    numbers = {
        key: value for key, value in (counts or {}).items()
        if isinstance(value, (int, float, bool)) and not isinstance(value, str)
    }

    def on_idle():
        elapsed = perf_counter()
        report = {
            "schema": "drawtemp-ui-trace-v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "callback_ms": round((callback_done - started) * 1000, 3),
            "callback_to_idle_ms": round((elapsed - started) * 1000, 3),
            "queued_idle_ms": round((elapsed - callback_done) * 1000, 3),
            "scope": "Tk callback to next idle; excludes input dispatch and physical presentation",
            "counts": numbers,
        }
        try:
            path = Path(TRACE_PATH)
            # Explicit absolute paths prevent the trace from polluting a game project.
            if not path.is_absolute():
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(report, sort_keys=True) + "\n")
        except OSError:
            # Profiling must not prevent gameplay or editing.
            pass

    try:
        widget.after_idle(on_idle)
    except Exception:
        # Tk was destroyed or tracing is unavailable; never break editing.
        pass
