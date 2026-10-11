"""2.8.3 — Journaled, chronological StoryBook over verified siege commands.

The siege engine owns combat outcomes; StoryBook owns narrative conditions and
effects. A narrative event records the *index* of the underlying tactical
operation so replay can prove that no conditional dialogue preceded its cause.
"""
from copy import deepcopy
from dataclasses import asdict

from .fronts import MultiFrontSession
from .game_session import digest
from .model import require
from .narrative import StoryBook


def victories(fronts):
    return {name for name, battle in fronts.battles.items()
            if battle.result == "victory"}


class SiegeStory:
    VERSION = 1

    def __init__(self, project, content, blueprint, fronts):
        project.validate(content)
        self.project = deepcopy(project)
        self.content = deepcopy(content)
        self.blueprint = deepcopy(blueprint)
        self.book = StoryBook(project.story, content, project.campaigns)
        self.progress = project.new_game(blueprint["campaign_id"], content)
        self.events = []
        self.baseline = {"at": len(fronts.history), "winners": sorted(victories(fronts))}
        self.won = set(self.baseline["winners"])
        self.pending_missions = []
        self.mapped_nodes = {
            ref.split('/', 1)[1]: scene
            for ref, scene in self.book.after_strategic_event.items()
            if ref.startswith(blueprint['id'] + '/')
        }
        # Scene-triggered cutscenes opt into v3; legacy v1/v2 remain unchanged.
        self.scene_clips = {}
        for clip in project.cinematics:
            if clip["trigger"]["kind"] == "scene":
                self.scene_clips.setdefault(clip["trigger"]["target"], []).append(
                    clip["id"])
        self.played_cinematics = set()
        self.VERSION = (3 if self.scene_clips else
                        2 if self.mapped_nodes else 1)
        self.seen_strategic = (set(fronts.fired_graph)
                               if self.baseline['at'] else set())
        self.pending_scenes = []
        # Legacy pre-2.8.3 checkpoints have no chronicle; do not retroactively
        # play an intro after combat has already begun.
        if self.baseline["at"]:
            self.progress.story_pending = ""
            for front in sorted(self.won):
                mid = fronts.missions[front]
                if mid not in self.progress.completed:
                    self.progress.completed.append(mid)

    def _queue_scene(self, scene):
        if self.progress.story_pending:
            self.pending_scenes.append(scene)
        else:
            self.progress.story_pending = scene

    def _strategic(self, node, at):
        require(node in self.mapped_nodes and node not in self.seen_strategic,
                'Unverified or duplicate strategic narrative trigger')
        self.seen_strategic.add(node)
        self._queue_scene(self.mapped_nodes[node])
        self.events.append({'kind': 'strategic', 'node': node, 'at': at})

    def next_cinematic(self):
        scene = self.active_scene()
        if self.VERSION != 3 or scene is None:
            return None
        for clip_id in self.scene_clips.get(scene["id"], ()):
            if clip_id not in self.played_cinematics:
                return deepcopy(next(c for c in self.project.cinematics
                                     if c["id"] == clip_id))
        return None

    def acknowledge_cinematic(self, clip_id, at):
        require(type(at) is int and at >= self.baseline["at"],
                "Invalid cinematic operation index")
        next_clip = self.next_cinematic()
        require(next_clip is not None and clip_id == next_clip["id"],
                "Cinematic is not pending for the active narrative scene")
        scene_id = self.progress.story_pending
        self.played_cinematics.add(clip_id)
        self.events.append({"kind": "cinematic", "clip": clip_id,
                            "scene": scene_id, "at": at})

    def _victory(self, front, at):
        require(front not in self.won, "Narrative front was already won")
        self.won.add(front)
        mission = self.blueprint["fronts"][front]
        if mission not in self.progress.completed:
            self.progress.completed.append(mission)
        if mission in self.book.after:
            if self.VERSION >= 2:
                self._queue_scene(self.book.after[mission])
            elif self.progress.story_pending:
                self.pending_missions.append(mission)
            else:
                self.book.after_victory(self.progress, mission)
        self.events.append({"kind": "victory", "front": front, "at": at})

    def sync(self, fronts):
        index = len(fronts.history)
        require(index >= self.baseline["at"], "Siege clock cannot move backwards")
        if self.VERSION >= 2:
            # Only one-shot, authenticated graph events may advance the story.
            for event in fronts.timeline.events:
                node = event.get('id')
                if (event.get('kind') == 'strategic_event_fired'
                        and node in self.mapped_nodes
                        and node not in self.seen_strategic):
                    require(node in fronts.fired_graph,
                            'Strategic narrative event lacks tactical proof')
                    self._strategic(node, index)
        for front in sorted(victories(fronts) - self.won):
            self._victory(front, index)

    def active_scene(self):
        return self.book.active_scene(self.progress)

    def choices(self):
        return self.book.choices(self.progress)

    def choose(self, choice, at):
        require(type(at) is int and at >= self.baseline["at"],
                "Invalid narrative operation index")
        require(self.next_cinematic() is None,
                "Finish or skip the pending cinematic before this choice")
        self.progress = self.book.choose(self.progress, choice)
        self.events.append({"kind": "choice", "choice": choice, "at": at})
        if not self.progress.story_pending:
            if self.VERSION == 2 and self.pending_scenes:
                self.progress.story_pending = self.pending_scenes.pop(0)
            elif self.pending_missions:
                self.book.after_victory(self.progress, self.pending_missions.pop(0))
        return self.active_scene()

    def recording(self):
        state = {'progress': asdict(self.progress),
                 'pending_missions': self.pending_missions,
                 'won': sorted(self.won)}
        if self.VERSION >= 2:
            state['seen_strategic'] = sorted(self.seen_strategic)
            state['pending_scenes'] = list(self.pending_scenes)
        if self.VERSION == 3:
            state["played_cinematics"] = sorted(self.played_cinematics)
        body = {"version": self.VERSION,
                "project_digest": digest(self.project.to_dict()),
                "baseline": deepcopy(self.baseline),
                "events": deepcopy(self.events),
                "state_digest": digest(state)}
        return {**body, "digest": digest(body)}

    @classmethod
    def replay(cls, record, project, content, blueprint, tactical, *, rules=None):
        require(isinstance(record, dict) and set(record) == {
            "version", "project_digest", "baseline", "events",
            "state_digest", "digest"} and record["version"] in (1, 2, 3),
                "Unsupported siege narrative recording")
        require(record["digest"] == digest({key: value for key, value in
                record.items() if key != "digest"}), "Narrative checksum mismatch")
        require(record["project_digest"] == digest(project.to_dict()),
                "Narrative project changed since save")
        # The caller has already verified the entire multi-front recording.
        # Prefix replay cannot be used as a substitute for full validation.
        operations = tactical["operations"]
        require(isinstance(operations, list), "Malformed tactical history")
        memo = {}
        def prefix(index):
            if index not in memo:
                memo[index] = MultiFrontSession.replay(
                    tactical, rules=rules, _until=index)
            return memo[index]

        baseline = record["baseline"]
        require(isinstance(baseline, dict) and set(baseline) == {"at", "winners"}
                and type(baseline["at"]) is int
                and 0 <= baseline["at"] <= len(operations)
                and isinstance(baseline["winners"], list)
                and all(isinstance(front, str) for front in baseline["winners"])
                and len(set(baseline["winners"])) == len(baseline["winners"]),
                "Invalid narrative baseline")
        require(sorted(victories(prefix(baseline["at"]))) == baseline["winners"],
                "Narrative initial victories mismatch")
        story = cls(project, content, blueprint, prefix(baseline["at"]))
        require(story.baseline == baseline and story.VERSION == record["version"],
                "Narrative version or baseline differs from saved campaign")
        events = record["events"]
        require(isinstance(events, list) and len(events) <= 20000,
                "Invalid narrative event journal")
        last = baseline["at"]
        for event in events:
            require(isinstance(event, dict)
                    and type(event.get("at")) is int
                    and last <= event["at"] <= len(operations),
                    "Invalid narrative event timestamp")
            index = event["at"]
            if index > last:
                require(story.active_scene() is None,
                        "Tactical actions bypassed an unresolved dialogue")
            if event.get("kind") == "victory":
                require(set(event) == {"kind", "front", "at"}
                        and event["front"] in blueprint["fronts"]
                        and index > baseline["at"]
                        and event["front"] in victories(prefix(index))
                        and event["front"] not in victories(prefix(index - 1)),
                        "Narrative victory has no newly verified battle result")
                story._victory(event["front"], index)
            elif event.get("kind") == "strategic":
                require(set(event) == {"kind", "node", "at"}
                        and story.VERSION >= 2
                        and index > baseline["at"]
                        and event["node"] in story.mapped_nodes
                        and event["node"] in prefix(index).fired_graph
                        and event["node"] not in prefix(index-1).fired_graph,
                        "Strategic scene has no authenticated graph firing")
                story._strategic(event["node"], index)
            elif event.get("kind") == "cinematic":
                require(set(event) == {"kind", "clip", "scene", "at"}
                        and story.VERSION == 3
                        and event["scene"] == story.progress.story_pending,
                        "Malformed or displaced cinematic acknowledgement")
                story.acknowledge_cinematic(event["clip"], index)
            elif event.get("kind") == "choice":
                require(set(event) == {"kind", "choice", "at"}
                        and isinstance(event["choice"], str),
                        "Malformed dialogue choice")
                story.choose(event["choice"], index)
            else:
                require(False, "Unknown narrative event")
            last = index
        require(story.active_scene() is None or last == len(operations),
                "Tactical actions occurred while a dialogue was pending")
        require(victories(prefix(len(operations))) <= story.won,
                "A real victory was omitted from narrative chronology")
        if story.VERSION == 2:
            require(set(story.mapped_nodes) & set(prefix(len(operations)).fired_graph)
                    <= story.seen_strategic,
                    "A strategic narrative event is missing from the journal")
        require(story.recording() == record, "Narrative replay state mismatch")
        return story
