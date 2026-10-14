"""Tk cutscene stage shared by the Studio preview and the standalone Player.

The stage is presentation-only. It never edits Campaign, GameSession or Battle.
"""
from .cinematics import frame_at
from .audio_timeline import CinematicAudioDirector
from .cinematic_transport import CinematicTransport
from .tk_renderer import CanvasRenderer
from .model import require


def draw_frame(canvas, clip, ms, renderer=None):
    """Render a seekable preview using Tk primitives (no external media required)."""
    frame = frame_at(clip, ms)
    canvas.delete("all")
    w, h = max(320, canvas.winfo_width()), max(200, canvas.winfo_height())
    canvas.create_rectangle(0, 0, w, h, fill=frame.background, outline="")
    canvas.create_rectangle(0, h * .72, w, h, fill="#18273c", outline="")
    canvas.create_text(w / 2, 24, text=clip["name"], fill="#f7e6cb",
                       font=("TkDefaultFont", 14, "bold"))
    for actor, (x, y) in frame.actors:
        px = w * (.5 + (x - .5 - frame.camera[0]) * frame.zoom)
        py = h * (.5 + (y - .5 - frame.camera[1]) * frame.zoom)
        r = max(12, min(42, 22 * frame.zoom))
        sprite = ((renderer.image("sprite", actor) or
                   renderer.image("portrait", actor)) if renderer else None)
        if sprite is not None:
            canvas.create_image(px, py, image=sprite)
        else:
            canvas.create_oval(px-r, py-r, px+r, py+r, fill="#dfb577",
                               outline="#fce9ce", width=3)
            canvas.create_text(px, py, text=actor[:2].upper(), fill="#233249",
                               font=("TkDefaultFont", 10, "bold"))
        canvas.create_text(px, py+r+14, text=actor, fill="white")
    if frame.shot_transition:
        kind, phase = frame.shot_transition
        if kind == "wipe":
            canvas.create_rectangle(0, 0, w * (1 - phase), h,
                                    fill="#101a2b", outline="")
        else:
            stipple = ("gray75" if phase < .25 else "gray50"
                       if phase < .5 else "gray25" if phase < .75 else "gray12")
            canvas.create_rectangle(0, 0, w, h, fill="#101a2b",
                                    stipple=stipple, outline="")
    if frame.shot:
        canvas.create_text(w - 16, 22, anchor="ne", text=frame.shot,
                           fill="#cbd6df", font=("TkDefaultFont", 9))
    if frame.dialogue:
        speaker, message = frame.dialogue
        detail = frame.dialogue_presentation
        message = detail.visible_text if detail else message
        portrait = None
        if detail and detail.portrait and renderer:
            portrait = (renderer.image("portrait",
                                      f"{detail.portrait}_{detail.expression}") or
                        renderer.image("portrait", detail.portrait))
        canvas.create_rectangle(18, h * .73, w-18, h-12, fill="#091523",
                                outline="#c3a47d", width=2)
        text_x = 128 if portrait is not None else 32
        if portrait is not None:
            canvas.create_image(74, h * .84, image=portrait)
        expression = (f" · {detail.expression}" if detail and
                      detail.expression != "neutral" else "")
        canvas.create_text(text_x, h * .76, text=speaker + expression, anchor="nw",
                           fill="#f2c88b", font=("TkDefaultFont", 12, "bold"))
        canvas.create_text(text_x, h * .83, text=message, anchor="nw",
                           width=max(100, w-text_x-38), fill="#f4f5f7")
    if frame.fade:
        color, ratio = frame.fade
        if ratio > 0:
            stipple = ("gray12" if ratio < .25 else "gray25" if ratio < .5
                       else "gray50" if ratio < .75 else "gray75" if ratio < 1
                       else "")
            canvas.create_rectangle(0, 0, w, h, fill=color, outline="",
                                    stipple=stipple)
    return frame


class CinematicPlayback:
    """Autoplay, pause, restart, skip and deterministic seek. Callback exactly once."""
    def __init__(self, parent, tk, ttk, clip, finished, audio=None,
                 registry=None, asset_root=None, clock=None):
        self.parent, self.tk, self.ttk = parent, tk, ttk
        self.clip = clip
        self.finished = finished
        self._owns_audio = audio is None and registry is not None and asset_root is not None
        if self._owns_audio:
            from .audio_stage import AudioStage
            audio = AudioStage(registry, asset_root)
        self.audio = audio
        self.director = CinematicAudioDirector(clip, audio)
        self.transport = CinematicTransport(clip["duration_ms"], monotonic=clock)
        self.time_ms = 0
        self.playing = True
        self.closed = False
        self.job = None
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.frame, background="#101a2b",
                                highlightthickness=0, takefocus=1)
        self.canvas.pack(fill="both", expand=True)
        self.renderer = CanvasRenderer(self.canvas, registry=registry,
                                       asset_root=asset_root)
        footer = ttk.Frame(self.frame)
        footer.pack(fill="x", padx=12, pady=8)
        self.position = tk.StringVar()
        self.scrub = tk.DoubleVar(value=0)
        self._sync_scrub = False
        self.scrub_bar = ttk.Scale(self.frame, from_=0, to=clip["duration_ms"],
                                   variable=self.scrub, command=self._scrub_to)
        self.scrub_bar.pack(fill="x", padx=12)
        self.pause_button = ttk.Button(footer, text="Pause", command=self.toggle)
        self.pause_button.pack(side="left", padx=5)
        ttk.Button(footer, text="Recommencer", command=self.restart).pack(
            side="left", padx=5)
        ttk.Button(footer, text="Passer la cinématique", command=self.skip).pack(
            side="right", padx=5)
        ttk.Label(footer, textvariable=self.position).pack(side="right", padx=16)
        self.canvas.bind("<space>", lambda _: self.toggle())
        self.canvas.bind("<Escape>", lambda _: self.skip())
        self.canvas.bind("<Left>", lambda _: self.seek(self.time_ms - 1000))
        self.canvas.bind("<Right>", lambda _: self.seek(self.time_ms + 1000))
        self.canvas.bind("<Configure>", lambda _: self.render())
        self.canvas.focus_set()
        # UI/asset initialization must not consume the opening cinematic.
        self.transport.seek(0)
        self.director.advance(0)
        self.render()
        self._schedule()

    def render(self):
        if self.closed:
            return
        draw_frame(self.canvas, self.clip, self.time_ms, self.renderer)
        self._sync_scrub = True
        try:
            self.scrub.set(self.time_ms)
        finally:
            self._sync_scrub = False
        self.position.set(f"{self.time_ms / 1000:.1f} / "
                          f"{self.clip['duration_ms'] / 1000:.1f} s")

    def _scrub_to(self, value):
        # Tk may deliver programmatic Scale callbacks on a later idle cycle.
        # The current playhead value is never treated as a user seek.
        position = int(float(value))
        if not self._sync_scrub and abs(position - self.time_ms) > 1:
            self.seek(position)

    def seek(self, ms):
        """Seekable preview; historical audio one-shots must not refire."""
        if self.closed:
            return
        self.time_ms = self.transport.seek(int(ms))
        self.director.seek(self.time_ms)
        if not self.transport.playing:
            self.director.pause()
        self.render()

    def checkpoint(self):
        """In-memory, clip-bound presentation state; not a campaign save."""
        return {"clip_id": self.clip["id"],
                "duration_ms": self.clip["duration_ms"],
                **self.transport.checkpoint()}

    def restore(self, checkpoint):
        require(isinstance(checkpoint, dict)
                and set(checkpoint) ==
                    {"clip_id", "duration_ms", "time_ms", "playing"}
                and checkpoint["clip_id"] == self.clip["id"]
                and checkpoint["duration_ms"] == self.clip["duration_ms"],
                "Cinematic checkpoint belongs to another clip")
        # Strict validation occurs before cancelling any jobs or audio.
        position = self.transport.restore(
            {"time_ms": checkpoint["time_ms"],
             "playing": checkpoint["playing"]})
        if self.closed:
            return
        if self.job is not None:
            self.parent.after_cancel(self.job)
            self.job = None
        self.time_ms = position
        self.playing = self.transport.playing
        self.director.seek(self.time_ms)  # never re-emit past one-shots
        if self.playing:
            self.director.resume()
        else:
            self.director.pause()
        self.pause_button.configure(text="Pause" if self.playing else "Lire")
        self.render()
        self._schedule()

    def _schedule(self):
        if not self.closed and self.playing and self.job is None:
            self.job = self.parent.after(40, self._tick)

    def _tick(self):
        self.job = None
        if self.closed or not self.playing:
            return
        self.time_ms = self.transport.read()
        self.director.advance(self.time_ms)
        self.render()
        if self.time_ms >= self.clip["duration_ms"]:
            self.skip()
        else:
            self._schedule()

    def toggle(self):
        if self.closed:
            return
        if self.playing:
            self.time_ms = self.transport.pause()
            self.director.advance(self.time_ms)
            self.director.pause()
        else:
            self.transport.resume()
            self.director.resume()
        self.playing = self.transport.playing
        self.pause_button.configure(text="Pause" if self.playing else "Lire")
        if self.job is not None:
            self.parent.after_cancel(self.job)
            self.job = None
        self._schedule()

    def restart(self):
        if self.closed:
            return
        self.time_ms = self.transport.restart()
        self.director.restart()
        self.director.resume()
        self.playing = True
        self.pause_button.configure(text="Pause")
        self.render()
        self._schedule()

    def skip(self):
        if self.closed:
            return
        self.close()
        self.finished()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.job is not None:
            self.parent.after_cancel(self.job)
            self.job = None
        self.director.stop()
        if self._owns_audio:
            self.audio.close()
        self.renderer.dispose()
        self.frame.destroy()
