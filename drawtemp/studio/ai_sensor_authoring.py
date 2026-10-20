"""R37.D: transactional sensor authoring over GameProject's single R1 history."""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.advanced_ai import EXTENSION as AI_EXTENSION
from sporebound.ai_perception import perceive_grid, validate_sensor
from sporebound.living_world import EXTENSION as WORLD_EXTENSION


class AISensorDesigner:
    def __init__(self, session):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected the existing R1 AuthoringSession")
        self.session = session

    def _project(self):
        return self.session.snapshot().to_dict()["project"]

    def agents(self):
        document = self._project().get("extensions", {}).get(
            AI_EXTENSION, {}).get("data", {})
        return [
            {"id": row["id"], "mode": row["mode"],
             "sensor": deepcopy(row.get("sensor"))}
            for row in document.get("agents", [])]

    def _agent(self, actor_id):
        agent = next((row for row in self.agents()
                      if row["id"] == actor_id), None)
        if agent is None:
            raise ValueError("Unknown authored R37 actor")
        return agent

    def preview(self, actor_id, sensor, *, expected_revision=None):
        """Preview an atomic replacement/removal; no authoring on invalid data."""
        self._agent(actor_id)
        if expected_revision is not None and self.session.revision != expected_revision:
            raise ValueError("R37 sensor draft is stale; reload it")
        new_sensor = validate_sensor(sensor) if sensor is not None else None

        def change(project):
            agent = next(row for row in project["extensions"][AI_EXTENSION]["data"][
                "agents"] if row["id"] == actor_id)
            if new_sensor is None:
                agent.pop("sensor", None)
            else:
                agent["sensor"] = deepcopy(new_sensor)
            return project
        return self.session.preview_project(change, kind="r37.perception.sensor")

    def apply(self, plan):
        return self.session.apply(plan)

    def simulate(self, actor_id, *, sensor=None, movement=False):
        """Clearly labeled *authored reference* preview, not a live game state.

        Position comes from the NPC's FIRST authored schedule stop and the
        exploration scene's configured hero start. No fake runtime tick/pose.
        """
        self._agent(actor_id)
        if type(movement) is not bool:
            raise ValueError("Movement preview must be boolean")
        project = self._project()
        world = project.get("extensions", {}).get(
            WORLD_EXTENSION, {}).get("data", {})
        npc = next((row for row in world.get("npcs", [])
                    if row["id"] == actor_id), None)
        if npc is None:
            raise ValueError("Sensor preview requires an authored R35 NPC")
        stop = npc["schedule"][0]
        if "pos" not in stop:
            raise ValueError("Sensor preview requires authored NPC coordinates")
        stage = project["exploration"].get(stop["scene"])
        if stage is None:
            raise ValueError("No canonical exploration geometry for this NPC")
        spec = sensor
        if spec is None:
            spec = self._agent(actor_id)["sensor"]
        if spec is None:
            raise ValueError("Sensor is not configured")
        report = perceive_grid(
            stage, stop["pos"], stage["start"],
            spec, movement=movement)
        return {"preview_only": True, "scene": stop["scene"],
                "origin": "first_authored_schedule_stop_and_stage_start",
                "sensor": validate_sensor(spec), "report": report}
