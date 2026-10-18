"""R6.2: the scenegraph renders and picks the *same* building surfaces."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content
from drawtemp.render.building_geometry import building_surfaces, pick_surface
from drawtemp.render.iso_scene import Camera, IsoProjection, fingerprint, render_items, scene_from_mission
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.construction import ConstructionPick, ConstructionWorkspace
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.building_visuals import exterior_wall_cells
from tests_standalone.test_drawtemp5_r6 import available_anchor


def middle(vertices):
    return (sum(x for x,y in vertices)/len(vertices),
            sum(y for x,y in vertices)/len(vertices))


class BuildingGeometryR6Tests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.workspace = ConstructionWorkspace(self.session, MISSION)
        self.anchor = available_anchor(content)
        self.workspace.apply(self.workspace.preview_place("Maison", self.anchor))
        self.id = self.workspace.inspect().structure_id
        self.camera = Camera()
        self.projection = IsoProjection()

    def scene(self):
        data = self.session.snapshot().to_dict()["content"]
        content = Content.from_dict(data)
        return scene_from_mission(content.missions[MISSION])

    def rows(self, **kw):
        return render_items(self.scene(), self.camera, self.projection, **kw)

    def choose(self, row, **kw):
        cx, cy = middle(row["vertices"])
        sx, sy = self.camera.screen(cx,cy)
        hit = pick_surface(self.rows(**kw),self.camera,sx,sy)
        return hit

    def test_shared_scene_contains_canonical_structures_and_is_detached(self):
        scene = self.scene()
        self.assertEqual(scene["structures"][0]["id"], self.id)
        self.assertEqual(scene["structures"][0]["anchor"], list(self.anchor))
        source = deepcopy(scene)
        fp = fingerprint(scene)
        scene["structures"][0]["anchor"][0] = -100
        self.assertNotEqual(fingerprint(scene),fp)
        self.assertNotEqual(scene["structures"],source["structures"])
        self.assertEqual(self.scene(), source)

    def test_real_roof_facade_door_polygons_picked_under_pan_zoom(self):
        rows = self.rows()
        roof = next(row for row in rows if row["kind"] == "building" and row["part"] == "roof")
        self.assertEqual(self.choose(roof)["part"], "roof")
        self.assertEqual(self.choose(roof)["structure_id"],self.id)
        door = next(row for row in rows if row["kind"] == "building" and row["part"] == "door")
        self.assertEqual(self.choose(door)["part"],"door")
        self.assertEqual(self.choose(door)["cell"],list(self.workspace.inspect().entry))
        for zoom, px, py in ((0.4, -110, 40), (2.5, 130, -55), (1.0, 0, 0)):
            self.camera.zoom = zoom
            self.camera.pan_x,self.camera.pan_y = px,py
            self.assertEqual(self.choose(roof)["part"],"roof")
            self.assertEqual(self.choose(door)["part"],"door")

    def test_painted_window_picks_real_wall_and_hidden_face_is_not_selectable(self):
        walls = exterior_wall_cells({"name":"Maison","turns":0,"door_slot":0})
        visible = next((dx,dy) for dx,dy in walls if dy == 2)
        window_cell = (self.anchor[0]+visible[0],self.anchor[1]+visible[1])
        self.workspace.apply(self.workspace.preview_window(window_cell))
        rows = self.rows()
        window = next(row for row in rows if row["kind"]=="building"
                      and row["part"]=="window" and row["cell"]==list(window_cell))
        pick = self.choose(window)
        self.assertEqual(pick["part"],"window")
        self.assertEqual(pick["cell"],list(window_cell))
        self.workspace.select(ConstructionPick(pick["structure_id"],
                                               tuple(pick["anchor"]),
                                               tuple(pick["cell"]),pick["part"]))
        self.assertEqual(self.workspace.inspect().selected_part,"window")
        back = {(x,y) for x,y in walls if y!=2 and x!=3}
        self.assertFalse(any(r["kind"] == "building" and r["part"] == "window" and
                             tuple(r["cell"]) in {(self.anchor[0]+x,self.anchor[1]+y) for x,y in back}
                             for r in rows))

    def test_cutaway_hides_roof_and_floor_hits_include_correct_level(self):
        self.workspace.apply(self.workspace.preview_floor_add(1))
        self.workspace.apply(self.workspace.preview_floor_add(2))
        rows_closed = self.rows()
        self.assertTrue(any(r["part"]=="roof" for r in rows_closed if r["kind"]=="building"))
        self.assertFalse(any(r["part"]=="floor" for r in rows_closed if r["kind"]=="building"))
        rows = self.rows(cutaway=True,active_level=2)
        self.assertFalse(any(r["part"]=="roof" for r in rows if r["kind"]=="building"))
        floor = next(r for r in rows if r["kind"]=="building" and r["part"]=="floor"
                     and r["level"]==2 and r["cell"]==
                     [self.anchor[0]+1,self.anchor[1]+1])
        hit = self.choose(floor,cutaway=True,active_level=2)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["part"],"floor")
        self.assertEqual(hit["level"],2)
        info = self.workspace.select(ConstructionPick(
            hit["structure_id"],tuple(hit["anchor"]),tuple(hit["cell"]),
            hit["part"],hit["level"]))
        self.assertEqual(info.active_level,2)
        with self.assertRaises(AuthoringError):
            self.workspace.select(ConstructionPick(
                self.id,self.anchor,(self.anchor[0],self.anchor[1]),"floor",3))

    def test_geometry_save_open_player_scene_parity(self):
        self.workspace.apply(self.workspace.preview_material(facade="torchis",roof="ardoise"))
        self.workspace.apply(self.workspace.preview_floor_add(1))
        scene = self.scene()
        with TemporaryDirectory() as folder:
            path = Path(folder)/"jeanne-r6.json"
            self.session.save_as(path)
            loaded = AuthoringSession.open(path)
            obj = loaded.snapshot().to_dict()["content"]
            player_scene = scene_from_mission(Content.from_dict(obj).missions[MISSION])
            self.assertEqual(fingerprint(player_scene), fingerprint(scene))
            self.assertEqual(building_surfaces(scene,self.projection),
                             building_surfaces(player_scene,self.projection))

    def test_no_phantom_hit_outside_polygons_and_no_geometry_on_empty_scene(self):
        self.assertIsNone(pick_surface(self.rows(),self.camera,-99999,-99999))
        scene = self.scene()
        scene["structures"]=[]
        scene["interior_floors"]=[]
        self.assertEqual(building_surfaces(scene,self.projection),[])
        self.assertFalse(any(r["kind"]=="building"
                             for r in render_items(scene,self.camera)))


if __name__ == "__main__":
    unittest.main()
