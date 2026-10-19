"""R41.A public headless facade: versioned authoring and RPG_TURN ordering.

Party mutations and checkpoints are performed on sporebound.game_session.GameSession.
This facade never creates an independent RPG campaign or inventory owner.
"""
from sporebound.classic_party import (EXTENSION, VERSION, rpg_turn_order,
                                       validate_classic_party)

__all__ = ["EXTENSION", "VERSION", "rpg_turn_order", "validate_classic_party"]
