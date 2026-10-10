"""Tk narrative decision tree with shared-scene occurrences.

A link is an authored choice; drawing duplicates the destination occurrence,
not the underlying scene. All mutations delegate to story_authoring.
"""
import json

from . import story_authoring as edit
from .story_graph import build_story_tree


class StoryGraphEditor:
    def __init__(self, editor, notebook):
        self.editor=editor
        self.owner=editor.owner
        self.tk,self.ttk=self.owner.tk,self.owner.ttk
        self.roots={}
        self.current_root=''
        self.selected_path=None
        self.selected_choice=''
        self.collapsed=set()
        self.layout=None
        self._fingerprint=None
        self._build(notebook)

    def _button(self,parent,label,fn):
        self.ttk.Button(parent,text=label,command=lambda:self.owner._run(fn)).pack(
            side='left',padx=3,pady=3)

    def _build(self,notebook):
        ttk=self.ttk
        page=ttk.Frame(notebook)
        notebook.add(page,text='Arbre narratif')
        header=ttk.Frame(page);header.pack(fill='x',padx=8,pady=7)
        ttk.Label(header,text='Point de départ :').pack(side='left')
        self.root_var=self.tk.StringVar()
        self.root_box=ttk.Combobox(header,textvariable=self.root_var,
                                   state='readonly',width=38)
        self.root_box.pack(side='left',padx=5)
        self.root_box.bind('<<ComboboxSelected>>',lambda event:self._new_root())
        ttk.Label(header,text='Zoom').pack(side='left',padx=(14,2))
        self.zoom_var=self.tk.StringVar(value='100%')
        self.zoom_box=ttk.Combobox(header,textvariable=self.zoom_var,
                                   values=['70%','100%','130%'],state='readonly',width=6)
        self.zoom_box.pack(side='left')
        self.zoom_box.bind('<<ComboboxSelected>>',lambda event:self.draw())
        self._button(header,'Tout déplier',self.expand_all)
        self._button(header,'Recentrer',self.recenter)

        main=ttk.Frame(page)
        main.pack(fill='both',expand=True,padx=8,pady=4)
        frame=ttk.Frame(main)
        frame.pack(side='left',fill='both',expand=True)
        self.canvas=self.tk.Canvas(frame,bg='#f8fafc',highlightthickness=0,height=430)
        horizontal=ttk.Scrollbar(frame,orient='horizontal',command=self.canvas.xview)
        vertical=ttk.Scrollbar(frame,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=horizontal.set,yscrollcommand=vertical.set)
        horizontal.pack(side='bottom',fill='x')
        vertical.pack(side='right',fill='y')
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<MouseWheel>',self._wheel)
        self.canvas.bind('<Button-4>',lambda event:self.canvas.yview_scroll(-3,'units'))
        self.canvas.bind('<Button-5>',lambda event:self.canvas.yview_scroll(3,'units'))

        details=ttk.LabelFrame(main,text='Branche sélectionnée',width=305)
        details.pack(side='right',fill='y',padx=(8,0))
        details.pack_propagate(False)
        self.info=self.tk.Text(details,wrap='word',height=13,width=35,
                               relief='flat',background='#f3f4f6')
        self.info.pack(fill='both',expand=True,padx=7,pady=7)
        self.info.configure(state='disabled')
        ttk.Label(details,text='Choix à modifier').pack(anchor='w',padx=8)
        self.choice_var=self.tk.StringVar()
        self.choice_box=ttk.Combobox(details,textvariable=self.choice_var,
                                      state='readonly',width=29)
        self.choice_box.pack(fill='x',padx=8,pady=4)
        self.choice_box.bind('<<ComboboxSelected>>',lambda event:self._choice_selected())
        line=ttk.Frame(details);line.pack(fill='x',padx=6,pady=3)
        self._button(line,'Éditer scène / choix',self.open_editor)
        line=ttk.Frame(details);line.pack(fill='x',padx=6,pady=3)
        self._button(line,'Replier / déplier',self.toggle)

        ttk.Separator(details,orient='horizontal').pack(fill='x',padx=8,pady=9)
        ttk.Label(details,text='Relier à une scène existante :').pack(anchor='w',padx=8)
        self.target_var=self.tk.StringVar()
        self.target_box=ttk.Combobox(details,textvariable=self.target_var,
                                      state='readonly',width=29)
        self.target_box.pack(fill='x',padx=8,pady=5)
        line=ttk.Frame(details);line.pack(fill='x',padx=6)
        self._button(line,'Relier',lambda:self.link(self.target_var.get()))
        self._button(line,'Délier',lambda:self.link(''))

        ttk.Separator(details,orient='horizontal').pack(fill='x',padx=8,pady=9)
        ttk.Label(details,text='Créer une nouvelle scène sur ce choix').pack(
            anchor='w',padx=8)
        form=ttk.Frame(details)
        form.pack(fill='x',padx=6,pady=3)
        self.new_id,_=self.owner._field(form,0,'ID','new_branch',width=17)
        self.new_title,_=self.owner._field(form,1,'Titre','Nouvelle scène',width=17)
        self._button(details,'Créer et relier en une fois',self.create_branch)
        self.status=self.tk.StringVar(value='Choisir une scène ou une flèche pour agir.')
        ttk.Label(page,textvariable=self.status,wraplength=1000).pack(
            fill='x',padx=10,pady=6)

    def _wheel(self,event):
        if event.delta:
            self.canvas.yview_scroll(-1 if event.delta>0 else 1,'units')

    def _sources(self):
        story=self.owner.project.story
        scenes=story.get('scenes',[])
        roots={}
        for campaign in self.owner.project.campaigns:
            scene=story.get('entry_scenes',{}).get(campaign['id'])
            if scene:
                roots['Début · '+campaign['id']]=scene
        for mission,scene in sorted(story.get('after_mission',{}).items()):
            roots['Victoire · '+mission]=scene
        for scene in scenes:
            roots['Scène · '+scene['id']]=scene['id']
        return roots

    def _new_root(self):
        self.current_root=self.roots.get(self.root_var.get(),'')
        self.selected_path=None
        self.selected_choice=''
        self.collapsed.clear()
        self.draw()

    def _model(self):
        story=self.owner.project.story
        return build_story_tree(story,self.current_root,collapsed=self.collapsed,
                                max_depth=24,max_nodes=350)

    def refresh(self):
        if self.owner.project is None:
            return
        roots=self._sources()
        current=self.root_var.get()
        self.roots=roots
        self.root_box['values']=list(roots)
        if current not in roots:
            current=next(iter(roots),'')
            self.root_var.set(current)
            self.current_root=roots.get(current,'')
            self.collapsed.clear()
            self.selected_path=None
        else:
            self.current_root=roots[current]
        self.target_box['values']=['',*[scene['id'] for scene in
                                        self.owner.project.story.get('scenes',[])]]
        fingerprint=(json.dumps(self.owner.project.story,sort_keys=True,
                                ensure_ascii=False),self.current_root)
        if fingerprint!=self._fingerprint:
            self._fingerprint=fingerprint
            self.draw()
        else:
            self._details()

    def _pos(self,path):
        x,y=self.layout['positions'][path]
        scale=int(self.zoom_var.get().rstrip('%'))/100
        return int(x*scale),int(y*scale)

    def draw(self):
        canvas=self.canvas
        canvas.delete('all')
        if not self.current_root:
            canvas.create_text(30,40,text='Aucune scène : créer une scène dans « Scénario & dialogues ».',
                               anchor='nw',fill='#334155')
            self.layout=None
            self._details()
            return
        layout=self._model()
        self.layout=layout
        occurrences={node['path']:node for node in layout['nodes']}
        if self.selected_path not in occurrences:
            self.selected_path=(self.current_root,)
            self.selected_choice=''
        scale=int(self.zoom_var.get().rstrip('%'))/100
        width=int(205*scale)
        height=int(74*scale)
        for edge_index,edge in enumerate(layout['edges']):
            x1,y1=self._pos(edge['source'])
            x2,y2=self._pos(edge['target'])
            # Curved choice paths stay separate from the repeated node cards.
            xx1=x1+width
            mid=(xx1+x2)//2
            tag='edge_'+str(edge_index)
            line=canvas.create_line(xx1,y1,mid,y1,mid,y2,x2,y2,
                                    fill='#64748b',width=2,
                                    smooth=True,arrow='last',
                                    tags=(tag,))
            cx=xx1+min(65,(x2-xx1)//2)
            label=edge['label'][:20]
            if edge['condition']!='toujours':
                label+='\n[condition]'
            if edge['effects']!='aucun effet':
                label+='\n[effet]'
            label_item=canvas.create_text(cx,(y1+y2)/2,text=label,
                                           fill='#334155',justify='center',
                                           font=('TkDefaultFont',8),
                                           tags=(tag,))
            canvas.tag_bind(tag,'<Button-1>',
                            lambda event,n=edge_index:self._edge_click(n))

        used={}
        for index,node in enumerate(layout['nodes']):
            x,y=self._pos(node['path'])
            scene=node['scene_id']
            number=used.get(scene,0)+1
            used[scene]=number
            shared=node['reused']
            selected=self.selected_path==node['path']
            fill=('#fde68a' if selected else '#dbeafe' if shared else
                  '#f1f5f9' if node['kind']=='end' else '#dcfce7'
                  if node['path']==(self.current_root,) else '#ffffff')
            tag='node_'+str(index)
            canvas.create_rectangle(x,y-height//2,x+width,y+height//2,
                                    fill=fill,outline='#2563eb' if selected else '#94a3b8',
                                    width=3 if selected else 2,tags=(tag,))
            if node['kind']=='end':
                title='FIN'
            else:
                title=node['title'][:40]
                if shared:
                    title+=' · occurrence '+str(number)
                if node['collapsed']:
                    title+='  ▶'
                if node['truncated']:
                    title+='  …'
            canvas.create_text(x+width//2,y-11*scale,text=title,
                                width=width-12,justify='center',
                                font=('TkDefaultFont',10,'bold'),
                                fill='#0f172a',tags=(tag,))
            if scene:
                canvas.create_text(x+width//2,y+16*scale,text=scene,
                                   font=('TkDefaultFont',9),fill='#475569',tags=(tag,))
            canvas.tag_bind(tag,'<Button-1>',
                            lambda event,n=index:self._node_click(n))
            canvas.tag_bind(tag,'<Double-Button-1>',
                            lambda event,n=index:self._node_double_click(n))
        canvas.configure(scrollregion=(0,0,int(layout['width']*scale),
                                       int(layout['height']*scale)))
        self.status.set(
            str(len(layout['nodes']))+' occurrences · '+
            str(len(layout['shared_scenes']))+' scènes partagées · '+
            ('arbre limité (replier des branches)' if layout['truncated']
             else 'clic = sélectionner · double-clic = éditer'))
        self._details()

    def _node_click(self,index):
        self.selected_path=self.layout['nodes'][index]['path']
        self.selected_choice=''
        self.draw()

    def _node_double_click(self,index):
        self._node_click(index)
        self.open_editor()

    def _edge_click(self,index):
        edge=self.layout['edges'][index]
        self.selected_path=edge['source']
        self.selected_choice=edge['choice_id']
        self.draw()

    def _choice_selected(self):
        self.selected_choice=self.choice_var.get()
        self._details()

    def _selected_node(self):
        if self.layout is None:
            return None
        return next((node for node in self.layout['nodes']
                     if node['path']==self.selected_path),None)

    def _details(self):
        self.info.configure(state='normal')
        self.info.delete('1.0','end')
        node=self._selected_node()
        if not node or not node['scene_id']:
            self.choice_box['values']=[]
            self.choice_var.set('')
            self.info.insert('1.0','Sélectionner une scène dans l’arbre.')
        else:
            scene=next(row for row in self.owner.project.story['scenes']
                       if row['id']==node['scene_id'])
            choices=scene['choices']
            ids=[choice['id'] for choice in choices]
            self.choice_box['values']=ids
            if self.selected_choice not in ids:
                self.selected_choice=ids[0] if ids else ''
            self.choice_var.set(self.selected_choice)
            choice=next((ch for ch in choices if ch['id']==self.selected_choice),None)
            text='SCÈNE  '+scene['id']+'\n'+scene['title']+'\n'
            if node['reused']:
                text+='\nScène partagée : toutes les occurrences réutilisent cette définition.\n'
            text+='\n'+scene['speaker']+'\n'+scene['text']+'\n'
            if choice:
                from .story_graph import condition_label,effects_label
                text+='\nBRANCHE  '+choice['id']+'\n'+choice['label']
                text+='\nCondition : '+condition_label(choice.get('when'))
                text+='\nConséquence : '+effects_label(choice.get('effects',[]))
                text+='\nVers : '+choice.get('next_scene','FIN')
                self.target_var.set(choice.get('next_scene',''))
            self.info.insert('1.0',text)
        self.info.configure(state='disabled')

    def _selection(self):
        node=self._selected_node()
        from .model import RuleError
        if node is None or not node['scene_id']:
            raise RuleError('Sélectionner une scène dans l’arbre')
        choice=self.choice_var.get()
        if not choice:
            raise RuleError('Sélectionner un choix')
        return node['scene_id'],choice

    def _apply(self,fn):
        self.editor._apply(fn)

    def open_editor(self):
        node=self._selected_node()
        from .model import RuleError
        if node is None or not node['scene_id']:
            raise RuleError('Sélectionner une scène')
        self.editor.select_graph_target(node['scene_id'],self.choice_var.get())

    def link(self,destination):
        scene,choice=self._selection()
        self._apply(lambda project,content:edit.link_choice(
            project,content,scene,choice,destination))

    def create_branch(self):
        source,choice=self._selection()
        destination=self.new_id.get()
        title=self.new_title.get()
        self._apply(lambda project,content:edit.create_linked_scene(
            project,content,source,choice,destination,title,
            'Nouvelle étape à écrire.',speaker=''))
        self.new_id.set('new_branch')
        self.new_title.set('Nouvelle scène')

    def expand_all(self):
        self.collapsed.clear()
        self.draw()

    def toggle(self):
        node=self._selected_node()
        if node is None or not node['scene_id']:
            return
        if node['path'] in self.collapsed:
            self.collapsed.remove(node['path'])
        else:
            self.collapsed.add(node['path'])
        self.draw()

    def recenter(self):
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
