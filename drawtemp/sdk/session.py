"""R0 adapter contract. This API is experimental until the R1 gate."""
from copy import deepcopy
from drawtemp.core import GameSession


class SessionAdapter:
    def __init__(self, session):
        self._session = session

    @classmethod
    def new(cls, content, project, campaign_id, *, seed=17):
        return cls(GameSession.new(content, project, campaign_id, seed=seed))

    @classmethod
    def load(cls, path, content, project):
        return cls(GameSession.load(path, content, project))

    def snapshot(self):
        # Detached canonical recording, not an alternate serialization schema.
        return deepcopy(self._session.recording())

    def choose_story_option(self, choice):
        return self._session.choose_story_option(choice)

    def start_mission(self, mission):
        self._session.start_mission(mission)

    def execute(self, command):
        return self._session.execute(deepcopy(command))

    def save(self, path):
        return self._session.save(path)
