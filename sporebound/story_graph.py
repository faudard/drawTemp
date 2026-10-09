"""Read-only, bounded narrative tree layout for an editor canvas.

A narrative SCENE has one definition. Every incoming CHOICE gets its own
display OCCURRENCE, even if multiple branches point at the same scene.
Occurrence paths are UI-only and must never be serialized as scene IDs.
"""
from collections import Counter

from .model import require


def condition_label(value):
    if value is None:
        return 'toujours'
    if 'all' in value:
        return ' ∧ '.join('('+condition_label(child)+')' for child in value['all'])
    if 'any' in value:
        return ' ∨ '.join('('+condition_label(child)+')' for child in value['any'])
    if 'not' in value:
        return 'NON ('+condition_label(value['not'])+')'
    if 'flag' in value:
        key = next(key for key in ('eq', 'gte', 'lte') if key in value)
        return str(value['flag']) + {'eq':' = ','gte':' ≥ ','lte':' ≤ '}[key]+str(value[key])
    if 'completed_mission' in value:
        return 'mission '+value['completed_mission']+' terminée'
    if 'gold_gte' in value:
        return 'or ≥ '+str(value['gold_gte'])
    return 'condition avancée'


def effects_label(effects):
    parts=[]
    for effect in effects:
        kind=effect['kind']
        if kind=='unlock_mission':
            parts.append('débloquer '+effect['mission'])
        elif kind=='set_flag':
            parts.append(effect['flag']+' := '+str(effect['value']))
        elif kind=='add_flag':
            parts.append(effect['flag']+' '+('%+d' % effect['amount']))
        elif kind=='gold':
            parts.append('or '+('%+d' % effect['amount']))
    return ' · '.join(parts) if parts else 'aucun effet'


def build_story_tree(story, root_scene, *, collapsed=(), max_depth=24, max_nodes=300):
    """Return a deterministic, per-edge-expanded tree for drawing.

    Each node has a unique occurrence tuple (root ID + choice IDs). Two nodes
    may have the same scene_id, but edits always target that scene's canonical
    ID. The layout is independent of Tk and bounded for large content.
    """
    require(type(max_depth) is int and 1 <= max_depth <= 64, 'Invalid maximum depth')
    require(type(max_nodes) is int and 1 <= max_nodes <= 2000, 'Invalid node budget')
    scenes={scene['id']:scene for scene in story.get('scenes',[])}
    require(root_scene in scenes, 'Choose an existing story scene')
    counts=Counter(choice.get('next_scene') for scene in scenes.values()
                   for choice in scene['choices'] if choice.get('next_scene'))
    collapsed=set(collapsed)
    nodes=[]
    edges=[]
    child_paths={}
    truncated=False
    next_y=[0]

    def visit(sid, path, depth, chain, incoming=None, terminal=False):
        nonlocal truncated
        if len(nodes)>=max_nodes:
            truncated=True
            return None
        if terminal:
            node={'path':path,'scene_id':'','kind':'end',
                  'title':'FIN DU DIALOGUE','depth':depth,'reused':False,
                  'collapsed':False,'truncated':False,'incoming':incoming}
        else:
            scene=scenes[sid]
            node={'path':path,'scene_id':sid,'kind':'scene',
                  'title':scene['title'],'depth':depth,
                  'reused':counts[sid]>1,'collapsed':path in collapsed,
                  'truncated':False,'incoming':incoming}
        nodes.append(node)
        branches=[]
        if not terminal:
            if sid in chain:
                node['kind']='cycle'
                node['truncated']=True
            elif depth>=max_depth:
                node['truncated']=True
                truncated=True
            elif path not in collapsed:
                for choice in scenes[sid]['choices']:
                    if len(nodes)>=max_nodes:
                        node['truncated']=True
                        truncated=True
                        break
                    dest=choice.get('next_scene','')
                    child_path=path+(choice['id'],)
                    child=visit(dest,child_path,depth+1,chain+(sid,),
                                incoming=choice['id'],terminal=not bool(dest))
                    if child is None:
                        node['truncated']=True
                        break
                    branches.append(child_path)
                    edges.append({
                        'source':path,'target':child_path,
                        'scene_id':sid,'choice_id':choice['id'],
                        'label':choice['label'],
                        'condition':condition_label(choice.get('when')),
                        'effects':effects_label(choice.get('effects',[])),
                    })
        child_paths[path]=branches
        return node

    root_path=(root_scene,)
    visit(root_scene,root_path,0,())
    positions={}
    # Children are already in preorder. Assign leaf rows bottom-up; each
    # parent sits halfway between its first and last visible descendants.
    for node in reversed(nodes):
        children=child_paths[node['path']]
        if not children:
            y=90+next_y[0]*125
            next_y[0]+=1
        else:
            y=(positions[children[0]][1]+positions[children[-1]][1])/2
        positions[node['path']]=(90+node['depth']*320,y)
    width=max((x for x,y in positions.values()),default=90)+270
    height=max((y for x,y in positions.values()),default=90)+130
    return {'root':root_scene,'nodes':nodes,'edges':edges,
            'positions':positions,'truncated':truncated,
            'width':width,'height':height,
            'shared_scenes':sorted(sid for sid,n in counts.items() if n>1)}
