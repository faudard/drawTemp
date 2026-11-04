# Character Studio — from beautiful concept art to real playable graphics

The Character Studio can now **display the real PNG artwork** the artist
provides. It no longer has to redraw a 1024px character as a handful of
programmatic geometric shapes. This workflow supports two different outputs:
a complete hi-res character (4 unique directional images), or editable
modular art (individual transparent front hair, clothes, eyes, etc.).

## 1. The high-resolution full-character path

Prepare a folder like:

\`\`\`text
my_knight_art/
  front.png       # transparent full body, facing camera
  right.png       # transparent full body, looking right
  back.png        # transparent full body, seen from back
  left.png        # transparent full body, looking left
  portrait.png    # optional: large portrait; opaque or transparent
  reference.png   # optional: concept sheet; reference only
\`\`\`

Each directional PNG must have real alpha transparency (not a solid
parchment or checkerboard rendered into the pixels). The images must share
the **same exact dimensions** (for example, 512×512 or 1024×1024, max 2048)
but must actually depict *four different facings*. A duplicated single
sprite is not accepted as four drawings. The actor should be centered over
a shared foot line; the importer defaults to horizontal centering and a
4px bottom margin. To retain the artist's original placements instead,
use \`--keep-position\` on the CLI. Original full-resolution PNG files are
preserved byte-for-byte in \`source/\`, and normalized game-ready PNGs are
written in \`idle/\` **without scaling**.

Run the editor and choose **File → Import 4-View Artwork…**, pick that
folder and provide a character display name / stable ID. This creates:

\`\`\`text
characters/my_knight.character.json
assets/character_art/my_knight/
  source/front.png, right.png, back.png, left.png
  idle/front.png, right.png, back.png, left.png
  portrait.png          # when provided
  reference.png         # when provided
  import.json           # placement decisions and QA status
\`\`\`

The character appears in the searchable Character Library immediately.
The large checkered overview and four direction previews use the **actual
imported high-res PNGs**. The Face panel shows the actual portrait, if
provided. Selecting a portrait never replaces the full-body overview.

You can also import without opening the GUI:

\`\`\`powershell
python -m drawtemp.assets.character_artwork --root . --folder "E:\Art\my_knight_art" --id my_knight --name "My Knight"
\`\`\`

The R7 recipe and atlas remain in their existing formats. No changes to
game saves or gameplay simulation.

**Do not mistake a beautiful illustration for a finished animation set.**
The four imports are four *idle stills*. Walk/attack/run/hit/death frames
must be drawn and added through the existing Animation Tools and timeline.
A high-resolution *full-body illustration* is also not automatically
separated into hair, face, shoes, armor and weapons.

## 2. Editable modular artwork

For actual RPG Maker-like variations, the artist supplies four transparent
**192×192** PNGs of one and only one part (such as Front Hair).
All pieces must share the project's head/foot anchors.

Use the Appearance category, then **Import Transparent Modular Part…**,
pick the four-file folder, and give the new variation a name. It is installed
under \`assets/hero_parts/{category}/{id}_{front|right|back|left}.png\`
and immediately appears in the Variation gallery. The original artwork is
not overwritten. The imported piece can then be tinted, positioned with
Offset X/Y and removed through the normal R7 recipe workflow.

This is the production path for creating many clean, independent versions of
the same character's hair, outfits, accessories, eyes, etc. It avoids
artificially cropping one fully painted portrait into fake layers.

## 3. Bring in the beautiful concept sheet from our earlier mockup

If you only have a *single labelled artwork sheet* (front/side/back shown
on a parchment background), do **not** load it as a sprite. Choose
**File → Attach Concept Reference…** and select the original PNG.

This saves it as
\`assets/character_art/{current-character-id}/reference.png\` and displays
it in the separately dockable **Concept Art Reference** panel with a
25–400% zoom control. Use the **View → Concept Art Reference** menu to
reopen it. It never replaces the actual Character Overview and is never
misrepresented as a playable sprite or an animation.

The artist must export isolated, background-free directional PNGs before
using the full-character importer. For modular customization, export
individual body/hair/face/clothing/accessory layers as well.

## 4. Real visual review in CI

The R7 GitHub Actions workflow now checks the import of valid transparent
four-way art on Ubuntu, Windows and macOS using synthetic test images.
Tests cover native-resolution compositing, alpha, distinct facings,
baseline alignment, portraits, original-file preservation, invalid artwork,
collision rejection and canonical atlas export.

The Qt smoke saves a **real application screenshot** named
\`character-studio-{Windows|Linux|macOS}.png\`, uploaded to GitHub Actions
as an artifact. These are actual UI captures, not generated render
mockups. Human review is still required before declaring the art
commercial-quality.

## Recommended art delivery contract

For each hero: one complete concept/turnaround PNG, four unique transparent
character views, one portrait, individually layered 192px pieces *when*
modular editing is desired, plus separate authored frames for movements
and combat. Different media are shown separately in the editor rather
than being silently swapped or fabricated.
