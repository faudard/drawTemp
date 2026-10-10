"""Playable Tk title screen and tactical client, with no authoring controls.

All game mechanics still run through Battle/Campaign; only UI state lives here.
"""
from pathlib import Path

from .game_project import GameProject
from .model import Content, RuleError
from .player_session import PlayerSession
from .siege import available_operations


def launch(content_path, project_path=None, profile_path=None):
    import tkinter as tk
    from tkinter import ttk, messagebox

    content=Content.load(content_path)
    project_path=Path(project_path) if project_path else Path(content_path).with_suffix('.game.json')
    project=(GameProject.load(project_path,content) if project_path.is_file()
             else GameProject.default(content))
    profile_path=Path(profile_path) if profile_path else (
        Path.home()/'.sporebound'/project_path.name)
    session=PlayerSession(content,project,profile_path)
    root=tk.Tk()
    root.title(project.title)
    root.geometry('1100x800')
    root.minsize(800,580)
    campaign_var=tk.StringVar(value=project.campaigns[0]['id'])
    slot_var=tk.StringVar(value='1')
    mission_var=tk.StringVar()
    command_var=tk.StringVar(value='move')
    facing_var=tk.StringVar(value='south')
    deploy_var=tk.StringVar()
    selected=[0,0]
    view=tk.Frame(root)
    view.pack(fill='both',expand=True)

    def safe(fn):
        def invoke(*args):
            try:
                fn(*args)
            except (RuleError, ValueError, TypeError, OSError, KeyError, StopIteration) as exc:
                messagebox.showerror('Commande refusée',str(exc))
        return invoke

    def clear():
        for child in view.winfo_children():
            child.destroy()

    def title_bar(container,heading):
        ttk.Label(container,text=heading,font=('TkDefaultFont',20,'bold')).pack(pady=14)

    def title_screen():
        clear()
        title_bar(view,project.title)
        ttk.Label(view,text=project.subtitle).pack(pady=(0,22))
        form=ttk.Frame(view)
        form.pack(pady=10)
        ttk.Label(form,text='Campagne').grid(row=0,column=0,sticky='e',padx=8,pady=7)
        ttk.Combobox(form,textvariable=campaign_var,state='readonly',
            values=[c['id'] for c in project.campaigns],width=23).grid(row=0,column=1,padx=8)
        ttk.Label(form,text='Emplacement de sauvegarde').grid(row=1,column=0,sticky='e',padx=8,pady=7)
        ttk.Combobox(form,textvariable=slot_var,state='readonly',
            values=[str(n) for n in range(1,project.save_slots+1)],width=23).grid(row=1,column=1,padx=8)
        ttk.Button(view,text='Nouvelle partie',command=safe(new_game)).pack(pady=6)
        ttk.Button(view,text='Continuer / charger',command=safe(load_game)).pack(pady=6)
        ttk.Button(view,text='Options',command=options_screen).pack(pady=6)
        ttk.Button(view,text='Quitter',command=root.destroy).pack(pady=6)

    def options_screen():
        clear()
        title_bar(view,'Options')
        for key,label in [('language','Langue'),('music_volume','Volume musique (%)'),
                          ('effects_volume','Volume effets (%)'),('fullscreen','Plein écran')]:
            ttk.Label(view,text=f"{label} : {project.options[key]}").pack(pady=8)
        ttk.Label(view,text='Paramètres déclarés dans le projet. Audio et vidéo ne sont pas encore pilotés par ce client.').pack(pady=15)
        ttk.Button(view,text='Retour',command=title_screen).pack(pady=10)

    def new_game():
        # UI confirms overwrite of an existing named save.
        from .game_project import _slot_path
        if _slot_path(session.profile,project,campaign_var.get(),int(slot_var.get())).exists():
            if not messagebox.askyesno('Nouvelle partie','Écraser cette sauvegarde ?'):
                return
        session.new_game(campaign_var.get(),int(slot_var.get()))
        campaign_screen()

    def load_game():
        session.load_game(campaign_var.get(),int(slot_var.get()))
        campaign_screen()

    def campaign_screen():
        clear()
        title_bar(view,project.campaign(session.campaign_id)['name'])
        ttk.Label(view,text=f"Or : {session.progress.gold}   Missions terminées : {len(session.progress.completed)}").pack(pady=8)
        scene=session.active_scene()
        if scene is not None:
            chapter=ttk.LabelFrame(view,text=scene['title'])
            chapter.pack(fill='both',expand=True,padx=95,pady=15)
            if scene['speaker']:
                ttk.Label(chapter,text=scene['speaker'],
                          font=('TkDefaultFont',12,'bold')).pack(pady=(15,7))
            ttk.Label(chapter,text=scene['text'],wraplength=760,
                      justify='left').pack(padx=25,pady=15)
            ttk.Label(chapter,text='Votre décision :').pack(pady=(5,10))
            for choice in session.available_choices():
                ttk.Button(chapter,text=choice['label'],
                           command=safe(lambda selected=choice['id']: choose_story(selected))).pack(
                               fill='x',padx=70,pady=6)
        else:
            available=session.available_missions()
            ttk.Label(view,text='Sélectionner une mission disponible :').pack(pady=5)
            if not available:
                ttk.Label(view,text='Campagne terminée : aucune nouvelle mission disponible.').pack(pady=8)
            for mid in available:
                mission=content.missions[mid]
                ttk.Button(view,text=f'{mission.name}  —  {mission.objective}',
                           command=safe(lambda target=mid: start_battle(target))).pack(
                               fill='x',padx=170,pady=5)
        actions=ttk.Frame(view);actions.pack(pady=16)
        ttk.Button(actions,text='Sauvegarder',command=safe(lambda: (session.save(),messagebox.showinfo(
            'Sauvegarde','Progression enregistrée.')))).pack(side='left',padx=8)
        ttk.Button(actions,text='Menu principal',command=title_screen).pack(side='left',padx=8)

    def choose_story(choice_id):
        session.choose_story(choice_id)
        campaign_screen()

    def start_battle(mid):
        session.begin(mid)
        selected[:]=[0,0]
        command_var.set('move')
        battle_screen()

    def choose_cell(event,canvas,scale):
        battle=session.battle
        x=int(canvas.canvasx(event.x)//scale);y=int(canvas.canvasy(event.y)//scale)
        if not battle.board.contains((x,y)):
            return
        selected[:]=[x,y]
        battle_screen()

    def battle_screen():
        clear()
        battle=session.battle
        if battle is None:
            campaign_screen()
            return
        title_bar(view,battle.mission.name)
        ttk.Label(view,text=f'Tick {battle.tick}  |  '+(
            f'Résultat : {battle.result}' if battle.result else
            'Déploiement' if battle.deploying else
            f'Actif : {battle.active.name} ({battle.active.team})' if battle.active else
            'Ordonnancement en cours')).pack(pady=3)
        if session.finalized:
            ttk.Label(view,text='Combat terminé : progression enregistrée.').pack(pady=10)
            ttk.Button(view,text='Retour à la campagne',command=safe(return_to_campaign)).pack(pady=9)
        elif battle.active and battle.active.team=='enemy':
            ttk.Button(view,text='Tour IA',command=safe(ai_turn)).pack(pady=8)
        else:
            controls=ttk.Frame(view);controls.pack(fill='x',padx=10,pady=8)
            if battle.deploying:
                actions=['deploy','start_battle']
            elif battle.active:
                actions=['move','attack',*battle.active.skills,'item:potion','item:ether',
                         'item:phoenix',*['object:'+o['id'] for o in battle.mission.objects],
                         *available_operations(battle,battle.active)]
            else:
                actions=[]
            if command_var.get() not in actions:
                command_var.set(actions[0] if actions else '')
            if battle.deploying:
                players=[u.id for u in battle.units if u.team=='player' and u.alive]
                if deploy_var.get() not in players:
                    deploy_var.set(players[0] if players else '')
                ttk.Label(controls,text='Unité').pack(side='left')
                ttk.Combobox(controls,textvariable=deploy_var,values=players,
                             state='readonly',width=11).pack(side='left',padx=5)
            ttk.Label(controls,text='Action').pack(side='left')
            ttk.Combobox(controls,textvariable=command_var,values=actions,
                         state='readonly',width=20).pack(side='left',padx=8)
            ttk.Label(controls,text='Orientation').pack(side='left')
            ttk.Combobox(controls,textvariable=facing_var,
                         values=['north','south','east','west'],
                         state='readonly',width=8).pack(side='left',padx=7)
            ttk.Button(controls,text='Exécuter',command=safe(execute)).pack(side='left',padx=5)
            if not battle.deploying:
                ttk.Button(controls,text='Fin du tour',command=safe(end_turn)).pack(side='left',padx=5)
        body=ttk.Frame(view);body.pack(fill='both',expand=True,padx=12,pady=8)
        scale=45
        canvas=tk.Canvas(body,bg='#f8fafc')
        canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(scrollregion=(0,0,battle.board.width*scale,battle.board.height*scale))
        for x,y in battle.board.cells():
            tile=battle.board.tile((x,y))
            color='#475569' if tile.blocked else '#fed7aa' if tile.hazard else '#ddd6fe' if tile.height else '#e2e8f0'
            canvas.create_rectangle(x*scale,y*scale,(x+1)*scale,(y+1)*scale,
                                    fill=color,outline='#94a3b8')
        for unit in battle.units:
            x,y=unit.pos
            fill='#60a5fa' if unit.team=='player' else '#fb7185'
            if not unit.alive:
                fill='#9ca3af'
            canvas.create_oval(x*scale+4,y*scale+4,x*scale+scale-4,y*scale+scale-4,fill=fill)
            canvas.create_text((x+.5)*scale,(y+.5)*scale,text=unit.name[:3])
        x,y=selected
        canvas.create_rectangle(x*scale+2,y*scale+2,(x+1)*scale-2,(y+1)*scale-2,
                                outline='#2563eb',width=3)
        canvas.bind('<Button-1>',lambda event:choose_cell(event,canvas,scale))
        info=tk.Text(body,width=36,height=24,state='normal',wrap='word')
        info.pack(side='right',fill='y')
        rows=[f'Case sélectionnée : {tuple(selected)}','', 'Unités :']
        rows.extend(f'{u.name}: PV {u.hp}/{u.max_hp} MP {u.mp}/{u.max_mp}' for u in battle.units)
        rows.extend(['','Journal :'])
        rows.extend(str(item) for item in battle.events[-25:])
        info.insert('1.0','\n'.join(rows)); info.configure(state='disabled')
        if not session.finalized:
            ttk.Button(view,text='Abandonner et revenir à la campagne',command=confirm_abandon).pack(pady=(0,10))

    def execute():
        battle=session.battle
        kind=command_var.get()
        facing={'north':[0,-1],'south':[0,1],'east':[1,0],'west':[-1,0]}[facing_var.get()]
        if kind=='start_battle':
            command={'kind':'start_battle'}
        elif kind=='deploy':
            # Follow the existing deployment contract: selected actor first.
            if not deploy_var.get():
                raise RuleError('Choose a player to deploy')
            command={'kind':'deploy','unit':deploy_var.get(),'cell':list(selected),'facing':facing}
        elif kind=='move':
            command={'kind':'move','cell':list(selected)}
        elif kind.startswith('item:'):
            command={'kind':'item','item':kind[5:],'cell':list(selected)}
        elif kind.startswith('object:'):
            command={'kind':'interact','object':kind[7:]}
        elif kind.startswith('siege-attack:'):
            command={'kind':'siege_attack','object':kind[13:]}
        elif kind.startswith('repair-siege:'):
            command={'kind':'repair_siege','object':kind[13:]}
        else:
            command={'kind':'act','skill':kind,'cell':list(selected)}
        session.command(command)
        battle_screen()

    def end_turn():
        facing={'north':[0,-1],'south':[0,1],'east':[1,0],'west':[-1,0]}[facing_var.get()]
        session.command({'kind':'end','facing':facing})
        battle_screen()

    def ai_turn():
        session.ai_turn()
        battle_screen()

    def confirm_abandon():
        if messagebox.askyesno('Abandonner','Quitter le combat ? La bataille en cours ne sera pas sauvegardée.'):
            session.abandon_battle()
            campaign_screen()

    def return_to_campaign():
        session.return_to_campaign()
        campaign_screen()

    def close():
        if session.battle is not None and not session.finalized:
            if not messagebox.askyesno('Quitter','Abandonner le combat non sauvegardé ?'):
                return
        root.destroy()

    root.protocol('WM_DELETE_WINDOW',close)
    title_screen()
    root.mainloop()

