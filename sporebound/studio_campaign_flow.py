"""R5.B Studio campaign inspection and bounded path QA, independent of the Player.

Presentation-only Tk window. Campaign, flow and save state remain owned by the
existing GameProject and Campaign models. No implicit save or mutation.
"""
from __future__ import annotations

import json

from .campaign_flow import audit_campaign, inspect_campaign, verify_save
from .model import RuleError


def studio_campaign_snapshot(owner):
    """Validated read-only snapshot for the currently selected campaign."""
    content = owner._content()
    owner.project.validate(content)
    campaign_id = owner.campaign_id.get()
    progress = (owner.session if owner.session is not None
                and owner.session_campaign == campaign_id
                else owner.project.new_game(campaign_id, content))
    verify_save(progress, owner.project.campaign_flow)
    return inspect_campaign(progress, owner.project.campaign_flow)


def studio_campaign_qa(owner):
    """Bounded path report; a symbolic route is never claimed to be a Battle replay."""
    content = owner._content()
    return audit_campaign(content, owner.project, owner.campaign_id.get())


def _report_view(owner, title, payload):
    window = owner.tk.Toplevel()
    window.title(title)
    window.geometry("840x650")
    frame = owner.ttk.Frame(window, padding=10)
    frame.pack(fill="both", expand=True)
    owner.ttk.Label(frame, text=title, font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
    owner.ttk.Label(frame, text="Lecture seule · aucune modification ni sauvegarde",
                    ).pack(anchor="w", pady=(0, 8))
    body = owner.ttk.Frame(frame)
    body.pack(fill="both", expand=True)
    scroll = owner.ttk.Scrollbar(body)
    scroll.pack(side="right", fill="y")
    view = owner.tk.Text(body, wrap="word", yscrollcommand=scroll.set)
    scroll.configure(command=view.yview)
    view.pack(fill="both", expand=True)
    view.insert("1.0", json.dumps(payload, indent=2, sort_keys=True,
                                  ensure_ascii=False) + "\n")
    view.configure(state="disabled")
    footer = owner.ttk.Frame(frame)
    footer.pack(fill="x", pady=8)
    owner.ttk.Button(footer, text="Fermer", command=window.destroy).pack(side="right")
    return window


def open_campaign_inspector(owner):
    return _report_view(owner, "R5.8 — État de campagne",
                        studio_campaign_snapshot(owner))


def open_campaign_qa(owner):
    return _report_view(owner, "R5.11 — QA de campagne",
                        studio_campaign_qa(owner))
