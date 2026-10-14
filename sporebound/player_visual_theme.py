"""Player-only art direction: warm illuminated manuscript over muted slate.

Pure palette selection and a single ttk skin. Does not alter Studio widgets,
gameplay state, preferences or serialized game data.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerPalette:
    background: str
    panel: str
    raised: str
    border: str
    text: str
    muted: str
    gold: str
    hover: str
    field: str
    ink: str


def player_palette(high_contrast=False):
    if high_contrast:
        return PlayerPalette(
            "#000000", "#101010", "#202020", "#ffffff", "#ffffff",
            "#ffffff", "#ffff00", "#383838", "#ffffff", "#000000")
    return PlayerPalette(
        "#141d25", "#202c33", "#2c3c40", "#687263", "#f4ead7",
        "#b8c4bc", "#e3b970", "#40514e", "#f0e8d9", "#1d272b")


def apply_player_theme(root, ttk, *, scale=1.0, high_contrast=False):
    """Style game screens as one client, not a patchwork of system widgets.

    Uses only standard clam ttk style options, with a readable HC variant.
    Importing this module has no Tk dependency (and can be unit tested).
    """
    p = player_palette(high_contrast)
    root.configure(background=p.background)
    style = ttk.Style(root)
    style.theme_use("clam")
    font_size = max(10, round(11 * scale))
    style.configure(".", background=p.background, foreground=p.text,
                    font=("Segoe UI", font_size))
    style.configure("TFrame", background=p.background)
    style.configure("TLabel", background=p.background, foreground=p.text)
    style.configure("TButton", padding=(12, 8), relief="flat", borderwidth=1,
                    bordercolor=p.border, background=p.panel, foreground=p.text,
                    focuscolor=p.gold)
    style.map("TButton",
              background=[("disabled", p.panel), ("pressed", p.gold),
                          ("active", p.hover)],
              foreground=[("disabled", p.muted), ("pressed", p.ink)])
    style.configure("Player.Accent.TButton", background=p.gold,
                    foreground=p.ink, bordercolor=p.gold)
    style.map("Player.Accent.TButton",
              background=[("disabled", p.panel), ("active", p.hover),
                          ("pressed", p.gold)],
              foreground=[("disabled", p.muted), ("active", p.text)])
    style.configure("TCombobox", fieldbackground=p.field,
                    foreground=p.ink, background=p.panel,
                    arrowcolor=p.gold, bordercolor=p.border)
    style.map("TCombobox", fieldbackground=[("readonly", p.field)],
              foreground=[("readonly", p.ink)])
    style.configure("TEntry", fieldbackground=p.field,
                    foreground=p.ink, bordercolor=p.border)
    style.configure("TLabelframe", background=p.background,
                    foreground=p.text, bordercolor=p.border,
                    relief="groove")
    style.configure("TLabelframe.Label", background=p.background,
                    foreground=p.gold,
                    font=("Georgia", max(11, round(12 * scale)), "bold"))
    style.configure("TCheckbutton", background=p.background,
                    foreground=p.text)
    style.map("TCheckbutton", background=[("active", p.background)],
              foreground=[("active", p.gold)])
    style.configure("TRadiobutton", background=p.background,
                    foreground=p.text)
    style.configure("TNotebook", background=p.background, borderwidth=0)
    style.configure("TNotebook.Tab", background=p.panel, foreground=p.muted,
                    padding=(14, 8))
    style.map("TNotebook.Tab", background=[("selected", p.raised),
                                           ("active", p.hover)],
              foreground=[("selected", p.gold), ("active", p.text)])
    style.configure("Treeview", background=p.panel,
                    fieldbackground=p.panel, foreground=p.text,
                    rowheight=max(24, round(27 * scale)),
                    borderwidth=0)
    style.map("Treeview", background=[("selected", p.gold)],
              foreground=[("selected", p.ink)])
    style.configure("Treeview.Heading", background=p.raised,
                    foreground=p.text)
    style.configure("Player.Title.TLabel", background=p.background,
                    foreground=p.text,
                    font=("Georgia", max(17, round(25 * scale)), "bold"))
    style.configure("Player.Subtitle.TLabel", background=p.background,
                    foreground=p.muted,
                    font=("Segoe UI", max(10, round(11 * scale))))
    return p
