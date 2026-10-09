"""Optional Tk command center. Importing this module does not initialize Tk.

This is a thin presentation of MultiFrontSession, not a second simulation.
All orders go through replayable session APIs. The headless dashboard/REPL
remains available on platforms without Tk or a display.
"""
import json

from .command_center import handle
from .model import RuleError


def launch(session):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Sporebound — Commandement stratégique")
    root.geometry("1130x780")
    root.minsize(830, 600)
    current = [session]

    status = tk.StringVar(value="")
    front_name = tk.StringVar(value=session.timeline.focused)
    doctrine = tk.StringVar(value="hold")
    destination = tk.StringVar(value="courtyard")
    unit_id = tk.StringVar(value="")
    x_value = tk.StringVar(value="3")
    y_value = tk.StringVar(value="6")
    tactical = tk.StringVar(value='{"kind":"start_battle"}')

    main = ttk.Frame(root, padding=12)
    main.pack(fill="both", expand=True)
    header = ttk.Frame(main)
    header.pack(fill="x")
    ttk.Label(header, text="COMMAND CENTER", font=("TkDefaultFont", 17, "bold")).pack(side="left")
    ttk.Label(header, textvariable=status).pack(side="right")
    lists = ttk.Frame(main)
    lists.pack(fill="both", expand=True, pady=(12, 4))

    front_section = ttk.LabelFrame(lists, text="Fronts — initiative globale")
    front_section.pack(side="left", fill="both", expand=True, padx=(0, 5))
    fronts = ttk.Treeview(front_section, columns=("front", "doctrine", "ally", "enemy", "status"),
                          show="headings", selectmode="browse", height=11)
    for col, width in (("front", 130), ("doctrine", 100), ("ally", 65),
                       ("enemy", 65), ("status", 100)):
        fronts.heading(col, text=col.capitalize())
        fronts.column(col, width=width, stretch=(col == "front"), anchor="center")
    fronts.pack(fill="both", expand=True)

    convoy_section = ttk.LabelFrame(lists, text="Convois — délais & secours")
    convoy_section.pack(side="right", fill="both", expand=True, padx=(5, 0))
    convoys = ttk.Treeview(convoy_section,
                           columns=("id", "from", "to", "men", "eta", "state"),
                           show="headings", selectmode="browse", height=11)
    for col, width in (("id", 90), ("from", 90), ("to", 90),
                       ("men", 55), ("eta", 45), ("state", 130)):
        convoys.heading(col, text=col.capitalize())
        convoys.column(col, width=width, anchor="center")
    convoys.pack(fill="both", expand=True)

    controls = ttk.LabelFrame(main, text="Ordres du commandant")
    controls.pack(fill="x", pady=8)
    one = ttk.Frame(controls, padding=5)
    one.pack(fill="x")
    ttk.Label(one, text="Front").pack(side="left")
    front_selector = ttk.Combobox(one, textvariable=front_name,
                                   values=sorted(session.missions), state="readonly", width=14)
    front_selector.pack(side="left", padx=5)
    ttk.Label(one, text="Doctrine").pack(side="left")
    doctrine_selector = ttk.Combobox(one, textvariable=doctrine,
                                     values=("hold", "assault", "delay", "retreat"),
                                     state="readonly", width=12)
    doctrine_selector.pack(side="left", padx=5)

    second = ttk.Frame(controls, padding=5)
    second.pack(fill="x")
    ttk.Label(second, text="Destination").pack(side="left")
    dest_selector = ttk.Combobox(second, textvariable=destination,
                                 values=sorted(session.missions), state="readonly", width=14)
    dest_selector.pack(side="left", padx=5)
    ttk.Label(second, text="Unit ID").pack(side="left")
    ttk.Entry(second, textvariable=unit_id, width=18).pack(side="left", padx=5)
    ttk.Label(second, text="X").pack(side="left")
    ttk.Entry(second, textvariable=x_value, width=4).pack(side="left", padx=4)
    ttk.Label(second, text="Y").pack(side="left")
    ttk.Entry(second, textvariable=y_value, width=4).pack(side="left", padx=4)

    fourth = ttk.Frame(controls, padding=5)
    fourth.pack(fill="x")
    ttk.Label(fourth, text="Décisions de convoi").pack(side="left", padx=4)

    third = ttk.Frame(controls, padding=5)
    third.pack(fill="x")
    ttk.Label(third, text="Commande tactique JSON").pack(side="left")
    ttk.Entry(third, textvariable=tactical, width=50).pack(side="left", padx=5,
                                                             fill="x", expand=True)

    events_box = ttk.LabelFrame(main, text="Journal global — événements récents")
    events_box.pack(fill="both", expand=True)
    events = tk.Text(events_box, height=9, wrap="word", state="disabled")
    events.pack(fill="both", expand=True, padx=4, pady=4)

    def refresh():
        s = current[0]
        logistics = s.logistics
        stock = "No logistics"
        if logistics is not None:
            stock = ("Réserves J:" + str(logistics.reserves["player"])
                     + " | Escortes:" + str(logistics.escorts))
            if logistics.supplies is not None:
                stock += " | Provisions J:" + str(logistics.supplies["player"])
        rescue_text = ""
        if s.rescue_battles:
            cid, battle = next(iter(s.rescue_battles.items()))
            wagon = battle.unit(battle.mission.protected_id)
            rescue_text = (f" | SAUVETAGE {cid}: "
                           f"actif={battle.active_id or 'aucun'}, chariot={wagon.hp} PV")
        if s.pursuit_battles:
            cid, battle = next(iter(s.pursuit_battles.items()))
            rescue_text = (f" | POURSUITE {cid}: "
                           f"actif={battle.active_id or 'aucun'}")
        status.set(f"Tour {s.timeline.turn} | Focus : {s.timeline.focused} | {stock}"
                   + rescue_text)
        front_selector.configure(values=sorted(s.missions))
        dest_selector.configure(values=sorted(s.missions))
        selected_fronts = fronts.selection()
        selected_convoys = convoys.selection()
        for item in fronts.get_children():
            fronts.delete(item)
        for name, info in sorted(s.timeline.fronts.items()):
            fronts.insert("", "end", iid=name,
                          values=(("▶ " if name == s.timeline.focused else "") + name,
                                  info["doctrine"], info["strength"],
                                  info["opposition"], info["status"]))
        for item in selected_fronts:
            if fronts.exists(item):
                fronts.selection_add(item)
        for item in convoys.get_children():
            convoys.delete(item)
        if logistics is not None:
            for entry in logistics.in_transit:
                state = ("FIGHTING" if entry["id"] in s.rescue_battles
                         else "Rescue required" if entry.get("stranded")
                         else "Escorted" if entry.get("escorted") else "Travelling")
                convoys.insert("", "end", iid=entry["id"],
                               values=(entry["id"], entry["from"], entry["to"],
                                       len(entry["actors"]),
                                       max(0, entry["arrival"] - s.timeline.turn), state))
        for item in selected_convoys:
            if convoys.exists(item):
                convoys.selection_add(item)
        events.configure(state="normal")
        events.delete("1.0", "end")
        for e in s.timeline.events[-30:]:
            events.insert("end", f"T{e['turn']:03} {e['kind']}  "
                          + ", ".join(f"{k}={v}" for k, v in e.items()
                                      if k not in {"turn", "kind"}) + "\n")
        events.configure(state="disabled")

    def guarded(work):
        try:
            work()
            refresh()
        except (RuleError, ValueError, KeyError, TypeError, OSError, IndexError) as error:
            messagebox.showerror("Ordre refusé", str(error))

    def selected_convoy():
        chosen = convoys.selection()
        if not chosen:
            raise RuleError("Sélectionnez un convoi dans le tableau")
        return chosen[0]

    def selected_pursuit():
        selected = convoys.selection()
        if selected and selected[0] in current[0].pursuit_targets:
            return selected[0]
        targets = current[0].pursuit_targets
        if len(targets) == 1:
            return next(iter(targets))
        raise RuleError("Sélectionnez une cible de poursuite")

    def placement():
        if not unit_id.get().strip():
            raise RuleError("Indiquez l'identifiant d'une unité")
        return [int(x_value.get()), int(y_value.get())]

    def check_saved():
        filename = filedialog.asksaveasfilename(defaultextension=".json",
                      filetypes=[("Saved command session", "*.json")])
        if filename:
            current[0], _, _ = handle(current[0], f"save {json.dumps(filename)}")

    def load_saved():
        filename = filedialog.askopenfilename(filetypes=[("Saved command session", "*.json")])
        if filename:
            current[0], _, _ = handle(current[0], f"load {json.dumps(filename)}")
            front_name.set(current[0].timeline.focused)

    ttk.Button(one, text="Changer de front",
               command=lambda: guarded(lambda: current[0].switch(front_name.get()))).pack(side="left", padx=3)
    ttk.Button(one, text="Appliquer doctrine",
               command=lambda: guarded(lambda: current[0].set_doctrine(
                   front_name.get(), doctrine.get()))).pack(side="left", padx=3)
    ttk.Button(one, text="Tour stratégique +1",
               command=lambda: guarded(lambda: current[0].advance())).pack(side="right", padx=3)
    ttk.Button(second, text="Envoyer réserve",
               command=lambda: guarded(lambda: current[0].send_reserves(
                   destination.get(), [{"id": unit_id.get(), "name": unit_id.get(),
                                        "team": "player", "pos": placement()}]))).pack(side="left", padx=3)
    ttk.Button(second, text="Transférer unité",
               command=lambda: guarded(lambda: current[0].transfer_units(
                   destination.get(), {unit_id.get(): placement()}))).pack(side="left", padx=3)
    ttk.Button(second, text="Escorte",
               command=lambda: guarded(lambda: current[0].escort_convoy(
                   selected_convoy()))).pack(side="right", padx=3)
    ttk.Button(second, text="Secours",
               command=lambda: guarded(lambda: current[0].rescue_convoy(
                   selected_convoy()))).pack(side="right", padx=3)
    ttk.Button(second, text="Combat de secours",
               command=lambda: guarded(lambda: current[0].start_rescue(
                   selected_convoy()))).pack(side="right", padx=3)
    ttk.Button(second, text="Abandonner",
               command=lambda: guarded(lambda: current[0].abandon_convoy(
                   selected_convoy()))).pack(side="right", padx=3)
    ttk.Button(fourth, text="Évacuer équipage",
               command=lambda: guarded(lambda: current[0].evacuate_convoy(
                   selected_convoy()))).pack(side="left", padx=3)
    ttk.Button(fourth, text="Butin partiel",
               command=lambda: guarded(lambda: current[0].salvage_convoy(
                   selected_convoy()))).pack(side="left", padx=3)
    ttk.Button(fourth, text="Négocier",
               command=lambda: guarded(lambda: current[0].negotiate_convoy(
                   selected_convoy()))).pack(side="left", padx=3)
    ttk.Button(fourth, text="Poursuivre pillards",
               command=lambda: guarded(lambda: current[0].start_pursuit(
                   selected_pursuit()))).pack(side="left", padx=3)
    ttk.Button(fourth, text="Abandon poursuite",
               command=lambda: guarded(lambda: current[0].abandon_pursuit(
                   selected_pursuit()))).pack(side="left", padx=3)

    def play_tactical():
        command = json.loads(tactical.get())
        s = current[0]
        if s.pursuit_battles:
            cid = next(iter(s.pursuit_battles))
            s.execute_pursuit(cid, command)
        elif s.rescue_battles:
            cid = next(iter(s.rescue_battles))
            s.execute_rescue(cid, command)
        else:
            s.execute(command)

    ttk.Button(third, text="Jouer tactique",
               command=lambda: guarded(play_tactical)).pack(side="left", padx=3)
    ttk.Button(third, text="Enregistrer",
               command=lambda: guarded(check_saved)).pack(side="right", padx=3)
    ttk.Button(third, text="Reprendre",
               command=lambda: guarded(load_saved)).pack(side="right", padx=3)
    ttk.Button(third, text="Actualiser", command=refresh).pack(side="right", padx=3)

    def select_front(_event=None):
        selected = fronts.selection()
        if selected:
            front_name.set(selected[0])

    fronts.bind("<<TreeviewSelect>>", select_front)
    refresh()
    root.mainloop()
    return current[0]
