"""Shared, accessible visual language for the standalone Tk Studio.

This module is presentation-only and intentionally imports Tk only when an
appearance is applied. The tactical renderer retains control of tile colours,
sprite atlases, hit testing, and map geometry.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StudioPalette:
    background: str
    surface: str
    elevated: str
    border: str
    text: str
    muted: str
    accent: str
    accent_text: str
    selected: str
    selected_text: str
    canvas: str
    danger: str
    success: str
    warning: str


PALETTES = {
    "light": StudioPalette(
        background="#F2F5FA", surface="#FFFFFF", elevated="#E8EEF7",
        border="#C8D2E0", text="#152338", muted="#4A5D75",
        accent="#2456BD", accent_text="#FFFFFF", selected="#DFEAFE",
        selected_text="#173C86", canvas="#E4EAF2",
        danger="#A62439", success="#176448", warning="#905514",
    ),
    "dark": StudioPalette(
        background="#141C2A", surface="#202C3D", elevated="#2B3950",
        border="#52627C", text="#F2F6FC", muted="#C2CCDC",
        accent="#91B6FF", accent_text="#0E1A2E", selected="#354C71",
        selected_text="#FFFFFF", canvas="#182435",
        danger="#FF9DAC", success="#8BE0B9", warning="#FFCF82",
    ),
}


def palette_for(name):
    """Validate user-supplied settings without executing arbitrary styles."""
    if name not in PALETTES:
        raise ValueError("Unknown Studio appearance: " + str(name))
    return PALETTES[name]


def _channel(hex_rgb):
    digits = hex_rgb.lstrip("#")
    return [int(digits[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def contrast_ratio(foreground, background):
    """WCAG-style luminance ratio, suitable for static theme regression gates."""
    def luminance(hex_rgb):
        rgb = _channel(hex_rgb)
        linear = [n / 12.92 if n <= .04045
                  else ((n + .055) / 1.055) ** 2.4 for n in rgb]
        return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + .05) / (a + .05)


class StudioAppearance:
    """One ttk theme setup for the Studio, with reversible light/dark tokens."""

    def __init__(self, root, ttk):
        self.root, self.ttk = root, ttk
        self.mode = "light"
        self.style = ttk.Style(root)
        self._texts = []
        self._canvases = []
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
        self.apply("light")

    def register_text(self, widget):
        self._texts.append(widget)
        self._style_text(widget, palette_for(self.mode))

    def register_canvas(self, widget, *, background="canvas"):
        self._canvases.append((widget, background))
        self._style_canvas(widget, palette_for(self.mode), background)

    @staticmethod
    def _style_text(widget, palette):
        widget.configure(
            background=palette.surface, foreground=palette.text,
            insertbackground=palette.text, selectbackground=palette.selected,
            selectforeground=palette.selected_text, relief="flat",
            borderwidth=0, highlightthickness=1,
            highlightbackground=palette.border,
            highlightcolor=palette.accent, padx=9, pady=8)

    @staticmethod
    def _style_canvas(widget, palette, background):
        widget.configure(background=getattr(palette, background))

    def apply(self, mode):
        palette = palette_for(mode)
        self.mode = mode
        style = self.style
        # Explicit widget styling avoids changing native Player windows.
        style.configure(".", background=palette.background,
                        foreground=palette.text,
                        font=("TkDefaultFont", 10))
        style.configure("TFrame", background=palette.background)
        style.configure("TLabel", background=palette.background,
                        foreground=palette.text, padding=(1, 2))
        style.configure("TLabelframe", background=palette.background,
                        relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=palette.background,
                        foreground=palette.muted, font=("TkDefaultFont", 10, "bold"),
                        padding=(5, 4))
        style.configure("TButton", background=palette.elevated,
                        foreground=palette.text, borderwidth=1,
                        bordercolor=palette.border, relief="flat",
                        padding=(11, 7))
        style.map("TButton",
                  background=[("pressed", palette.selected),
                              ("active", palette.selected)],
                  foreground=[("disabled", palette.muted)])
        style.configure("TMenubutton", background=palette.elevated,
                        foreground=palette.text, borderwidth=1,
                        padding=(10, 7))
        style.map("TMenubutton", background=[("active", palette.selected)])
        style.configure("TEntry", fieldbackground=palette.surface,
                        foreground=palette.text, bordercolor=palette.border,
                        padding=(6, 6))
        style.configure("TCombobox", fieldbackground=palette.surface,
                        background=palette.elevated, foreground=palette.text,
                        arrowcolor=palette.text, bordercolor=palette.border,
                        padding=(5, 5))
        style.map("TCombobox",
                  fieldbackground=[("readonly", palette.surface),
                                   ("disabled", palette.elevated)],
                  foreground=[("readonly", palette.text),
                              ("disabled", palette.muted)],
                  selectbackground=[("readonly", palette.surface)],
                  selectforeground=[("readonly", palette.text)])
        style.configure("TSpinbox", fieldbackground=palette.surface,
                        foreground=palette.text, bordercolor=palette.border,
                        padding=(5, 5))
        for widget_type in ("TCheckbutton", "TRadiobutton"):
            style.configure(widget_type, background=palette.background,
                            foreground=palette.text, padding=(4, 5))
            style.map(widget_type,
                      background=[("active", palette.background)],
                      foreground=[("disabled", palette.muted)])
        style.configure("TNotebook", background=palette.background,
                        borderwidth=0, tabmargins=(5, 5, 5, 0))
        style.configure("TNotebook.Tab", background=palette.elevated,
                        foreground=palette.muted, borderwidth=0,
                        padding=(14, 8))
        style.map("TNotebook.Tab",
                  background=[("selected", palette.surface),
                              ("active", palette.selected)],
                  foreground=[("selected", palette.text),
                              ("active", palette.text)])
        style.configure("Treeview", background=palette.surface,
                        fieldbackground=palette.surface,
                        foreground=palette.text, rowheight=30,
                        borderwidth=0, relief="flat")
        style.map("Treeview",
                  background=[("selected", palette.selected)],
                  foreground=[("selected", palette.selected_text)])
        style.configure("Treeview.Heading", background=palette.elevated,
                        foreground=palette.text,
                        font=("TkDefaultFont", 10, "bold"),
                        padding=(8, 8), relief="flat")
        style.map("Treeview.Heading",
                  background=[("active", palette.selected)])
        style.configure("TPanedwindow", background=palette.border)
        style.configure("TScrollbar", background=palette.elevated,
                        troughcolor=palette.background, arrowcolor=palette.muted)

        # Named variants used only where visual hierarchy matters.
        style.configure("Studio.Header.TFrame", background=palette.surface)
        style.configure("Studio.Header.TLabel", background=palette.surface,
                        foreground=palette.text, font=("TkDefaultFont", 12, "bold"))
        style.configure("Studio.Section.TFrame", background=palette.surface)
        style.configure("Studio.Section.TLabel", background=palette.surface,
                        foreground=palette.muted,
                        font=("TkDefaultFont", 10, "bold"))
        style.configure("Studio.Muted.TLabel", foreground=palette.muted,
                        background=palette.background)
        style.configure("Studio.Primary.TButton", background=palette.accent,
                        foreground=palette.accent_text,
                        bordercolor=palette.accent,
                        font=("TkDefaultFont", 10, "bold"),
                        padding=(14, 8))
        style.map("Studio.Primary.TButton",
                  background=[("active", palette.accent),
                              ("pressed", palette.accent)],
                  foreground=[("disabled", palette.muted)])
        style.configure("Studio.Nav.Toolbutton",
                        background=palette.surface, foreground=palette.muted,
                        padding=(11, 8), borderwidth=0, relief="flat")
        style.map("Studio.Nav.Toolbutton",
                  background=[("selected", palette.selected),
                              ("active", palette.elevated)],
                  foreground=[("selected", palette.selected_text),
                              ("active", palette.text)])
        style.configure("Studio.Status.TLabel",
                        background=palette.surface, foreground=palette.muted,
                        padding=(9, 6))
        style.configure("Studio.Dock.TNotebook",
                        background=palette.background, borderwidth=0)
        for widget in tuple(self._texts):
            if widget.winfo_exists():
                self._style_text(widget, palette)
        for widget, background in tuple(self._canvases):
            if widget.winfo_exists():
                self._style_canvas(widget, palette, background)
        self.root.configure(background=palette.background)
        return palette


class AppearancePreferences:
    """Separate project-local atomic UI preference, never written to saves."""

    def __init__(self, path):
        from pathlib import Path
        self.path = Path(path)

    def load(self):
        import json
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return "light"
        if (isinstance(raw, dict) and
                isinstance(raw.get("theme"), str) and
                raw["theme"] in PALETTES):
            return raw["theme"]
        return "light"

    def save(self, mode):
        import json
        palette_for(mode)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps({"theme": mode}), encoding="utf-8")
        temporary.replace(self.path)
