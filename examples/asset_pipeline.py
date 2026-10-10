"""Build a relocatable sample game manifest using retained repository artwork.

Run from the checkout: python examples/asset_pipeline.py --output /tmp/asset-demo
The output uses bundled tactical content and can be validated from any cwd.
"""
import argparse
from pathlib import Path
import shutil
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content


def build(output):
    output = Path(output)
    # A fresh destination avoids overwriting an authored project.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'art').mkdir()
    (output / 'audio').mkdir()
    for source, target in (
        ('momo_custom.png', 'momo.png'),
        ('momo_custom_portrait.png', 'momo_portrait.png'),
    ):
        shutil.copyfile(ROOT / 'assets/generated/heroes' / source, output / 'art' / target)
    with wave.open(str(output / 'audio/placeholder.wav'), 'wb') as sound:
        sound.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        sound.writeframes(b'\0\0' * 800)  # Silent placeholder, not final game audio.
    content = Content.load(DEFAULT_CONTENT)
    project = GameProject.default(content)
    project.assets = {'version': 1, 'entries': [
        {'id': 'momo', 'kind': 'sprite', 'path': 'art/momo.png'},
        {'id': 'momo_face', 'kind': 'portrait', 'path': 'art/momo_portrait.png'},
        {'id': 'placeholder', 'kind': 'sound', 'path': 'audio/placeholder.wav'},
        {'id': 'momo_idle', 'kind': 'animation', 'loop': True,
         'frames': [{'sprite': 'momo', 'duration_ms': 500}]},
    ], 'bindings': {'sprite': {'momo': 'momo'}, 'portrait': {'momo': 'momo_face'},
                    'animation': {'momo_idle': 'momo_idle'},
                    'sound': {'title': 'placeholder'}}}
    project.save(output / 'game.json', content)
    issues = project.asset_registry().diagnostics(output)
    if issues:
        raise ValueError(issues)
    return output / 'game.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(build(parser.parse_args().output))
