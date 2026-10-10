"""Tk Sound Studio: import, bind and audition project-local music and effects."""
from pathlib import Path

from .audio_authoring import bind_sound, import_sound, remove_sound, suggested_slots
from .audio_stage import AudioStage
from .model import RuleError


class AudioStudio:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.tk, self.ttk = owner.tk, owner.ttk
        self.preview_stage = None
        self.entry_ids = []
        self.binding_slots = []
        self.tab = self.ttk.Frame(notebook)
        notebook.add(self.tab, text="Son & musique")
        self._build()

    def _build(self):
        ttk = self.ttk
        tk = self.tk
        self.asset_id = tk.StringVar()
        self.slot = tk.StringVar(value="title")
        self.asset = tk.StringVar()
        self.category = tk.StringVar(value="Musique")
        ttk.Label(
            self.tab,
            text="Bibliothèque WAV / OGG — musiques, ambiances et effets. "
                 "Les sons sont stockés à côté du fichier .game.json.",
            wraplength=1000,
        ).pack(fill="x", padx=9, pady=8)
        body = ttk.Frame(self.tab)
        body.pack(fill="both", expand=True, padx=9, pady=5)
        left = ttk.LabelFrame(body, text="Bibliothèque sonore", padding=8)
        right = ttk.LabelFrame(body, text="Déclencheurs et préécoute", padding=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        right.pack(side="left", fill="both", expand=True, padx=(5, 0))
        self.asset_list = tk.Listbox(left, height=11, exportselection=False)
        self.asset_list.pack(fill="both", expand=True, pady=6)
        self.asset_list.bind("<<ListboxSelect>>", self._select_asset)
        ttk.Label(left, text="ID stable (lettres, chiffres, _, - ou .)").pack(anchor="w")
        ttk.Entry(left, textvariable=self.asset_id).pack(fill="x", pady=4)
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=5)
        ttk.Button(buttons, text="Importer WAV / OGG…",
                   command=lambda: self.owner._run(self.import_file)).pack(side="left", padx=3)
        ttk.Button(buttons, text="Retirer du catalogue",
                   command=lambda: self.owner._run(self.remove)).pack(side="left", padx=3)

        ttk.Label(right, text="Type de son").pack(anchor="w")
        kind = ttk.Combobox(right, textvariable=self.category, state="readonly",
                            values=["Musique", "Effet"], width=30)
        kind.pack(fill="x", pady=4)
        kind.bind("<<ComboboxSelected>>", lambda _: self._slots())
        ttk.Label(right, text="Déclencheur (libre ou proposé)").pack(anchor="w")
        self.slot_box = ttk.Combobox(right, textvariable=self.slot, width=42)
        self.slot_box.pack(fill="x", pady=4)
        ttk.Label(right, text="Fichier sonore lié").pack(anchor="w")
        self.asset_box = ttk.Combobox(right, textvariable=self.asset,
                                      state="readonly", width=42)
        self.asset_box.pack(fill="x", pady=4)
        ttk.Button(right, text="Associer au déclencheur",
                   command=lambda: self.owner._run(self.bind)).pack(fill="x", pady=3)
        ttk.Button(right, text="Délier le déclencheur",
                   command=lambda: self.owner._run(self.unbind)).pack(fill="x", pady=3)
        self.bindings = ttk.Treeview(right, columns=("slot", "asset"),
                                     show="headings", height=7, selectmode="browse")
        self.bindings.heading("slot", text="Déclencheur")
        self.bindings.heading("asset", text="Son")
        self.bindings.column("slot", width=170)
        self.bindings.column("asset", width=120)
        self.bindings.pack(fill="both", expand=True, pady=5)
        self.bindings.bind("<<TreeviewSelect>>", self._select_binding)
        controls = ttk.Frame(right)
        controls.pack(fill="x", pady=4)
        ttk.Button(controls, text="Écouter la sélection",
                   command=lambda: self.owner._run(self.preview)).pack(side="left", padx=3)
        ttk.Button(controls, text="Stop",
                   command=self.stop).pack(side="left", padx=3)
        ttk.Button(controls, text="Vérifier les fichiers",
                   command=lambda: self.owner._run(self.diagnose)).pack(side="left", padx=3)
        self.message = tk.StringVar(value="Importez un fichier, puis assignez-le à une scène ou un événement.")
        ttk.Label(self.tab, textvariable=self.message, wraplength=1000).pack(
            fill="x", padx=10, pady=8)

    def _project(self):
        if self.owner.project is None:
            raise RuleError("Projet de jeu non chargé")
        return self.owner.project

    def _root(self):
        return Path(self.owner.project_path).parent

    def _commit(self, updated, message):
        self.stop()
        self.owner.project = updated
        self.owner.project_status.config(text="Audio modifié — enregistrer le projet de jeu.")
        self.message.set(message)
        self.refresh()

    def import_file(self):
        from tkinter import filedialog
        name = filedialog.askopenfilename(
            title="Importer un son dans le projet",
            filetypes=[("Audio WAV / OGG", "*.wav *.ogg"), ("Tous les fichiers", "*.*")])
        if not name:
            return
        if not self.asset_id.get().strip():
            import re
            self.asset_id.set(re.sub(r"[^A-Za-z0-9_.-]", "_", Path(name).stem)[:80] or "sound")
        updated = import_sound(self._project(), self.owner._content(), name,
                               self._root(), self.asset_id.get().strip())
        self._commit(updated, "Son importé : " + self.asset_id.get())

    def remove(self):
        selected = self.asset_list.curselection()
        if not selected:
            raise RuleError("Sélectionner un son dans la bibliothèque")
        asset_id = self.entry_ids[selected[0]]
        updated = remove_sound(self._project(), self.owner._content(), asset_id)
        self._commit(updated, "Son retiré du catalogue (fichier conservé) : " + asset_id)

    def bind(self):
        if not self.asset.get():
            raise RuleError("Choisir un fichier sonore à associer")
        updated = bind_sound(self._project(), self.owner._content(),
                             self.slot.get().strip(), self.asset.get())
        self._commit(updated, "Déclencheur audio associé : " + self.slot.get())

    def unbind(self):
        updated = bind_sound(self._project(), self.owner._content(),
                             self.slot.get().strip())
        self._commit(updated, "Déclencheur audio délié : " + self.slot.get())

    def _select_asset(self, _event=None):
        selected = self.asset_list.curselection()
        if selected and selected[0] < len(self.entry_ids):
            self.asset.set(self.entry_ids[selected[0]])
            self.asset_id.set(self.entry_ids[selected[0]])

    def _select_binding(self, _event=None):
        selected = self.bindings.selection()
        if selected:
            slot = self.bindings.item(selected[0], "values")[0]
            self.slot.set(slot)
            self.asset.set(self._project().assets["bindings"]["sound"][slot])
            if slot in ("title", "campaign", "battle") or slot.startswith(
                    ("mission_", "music_scene_")):
                self.category.set("Musique")
            else:
                self.category.set("Effet")
            self._slots()

    def _slots(self):
        if self.owner.project is None:
            return
        music, effects = suggested_slots(self.owner._content(), self._project())
        self.slot_box["values"] = music if self.category.get() == "Musique" else effects

    def refresh(self):
        if self.owner.project is None:
            return
        assets = self._project().asset_registry().to_dict()
        entries = [entry for entry in assets["entries"] if entry["kind"] == "sound"]
        self.entry_ids = [entry["id"] for entry in entries]
        previous = self.asset.get()
        self.asset_list.delete(0, "end")
        for entry in entries:
            self.asset_list.insert("end", f'{entry["id"]} — {entry["path"]}')
        self.asset_box["values"] = self.entry_ids
        if previous and previous not in self.entry_ids:
            self.asset.set("")
        for row in self.bindings.get_children():
            self.bindings.delete(row)
        for slot, asset_id in sorted(assets["bindings"].get("sound", {}).items()):
            self.bindings.insert("", "end", values=(slot, asset_id))
        self._slots()

    def preview(self):
        name = self.asset.get()
        if not name:
            raise RuleError("Choisir un son pour l'écouter")
        self.stop()
        opts = self._project().options
        stage = AudioStage(self._project().asset_registry(), self._root(),
                           effects_volume=opts["effects_volume"],
                           music_volume=opts["music_volume"])
        self.preview_stage = stage
        if not stage.preview_asset(name, music=self.category.get() == "Musique"):
            self.stop()
            self.message.set(
                "Préécoute indisponible : vérifier le fichier, le périphérique "
                "audio et l'installation de pygame-ce.")
        else:
            self.message.set("Préécoute : " + name)

    def stop(self):
        if self.preview_stage is not None:
            self.preview_stage.close()
            self.preview_stage = None

    def diagnose(self):
        problems = self._project().asset_registry().diagnostics(self._root())
        audio_ids = set(self.entry_ids)
        problems = [p for p in problems if p["asset_id"] in audio_ids]
        if problems:
            self.message.set(" | ".join(p["message"] for p in problems[:5]))
        else:
            self.message.set("Tous les fichiers audio déclarés sont valides.")
