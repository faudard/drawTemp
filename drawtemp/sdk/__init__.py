"""Public, UI-independent DrawTemp 5 Game SDK surface (R1.10).

The SDK contract is versioned independently of the game's Content v1,
GameProject v1 and GameSession v1 disk formats. Imports stay lazy to keep the
Core headless and avoid circular dependencies during Qt bootstrap.
"""
from importlib import import_module

SDK_API_VERSION = (1, 0)
SDK_API_STATUS = "provisional"  # Stabilization candidate, not final 5.0 certification.
SDK_FEATURES = frozenset({
    "simulation.v1", "authoring.v1", "migration.v0-envelope-to-v1",
    "replay.v1", "player-slots.v1", "workers.v1", "certification.v1",
    "sdk-negotiation.v1", "project-extensions.v1",
})

_PUBLIC = {
    "SDKCompatibilityError": "compatibility",
    "negotiate_sdk": "compatibility",
    "ProjectExtensionError": "project_extensions",
    "validate_project_extensions": "project_extensions",
    "Simulation": "simulation",
    "SimulationError": "simulation",
    "StateSnapshot": "simulation",
    "GameEvent": "simulation",
    "Transition": "simulation",
    "AuthoringSession": "authoring",
    "AuthoringError": "authoring",
    "AuthoringSnapshot": "authoring",
    "AuthoringPlan": "authoring",
    "AuthoringTransition": "authoring",
    "MigrationError": "content_migration",
    "MigrationPreview": "content_migration",
    "preview_documents": "content_migration",
    "preview_pair": "content_migration",
    "commit_pair": "content_migration",
    "ReplayCommand": "replay",
    "ReplayCheckpoint": "replay",
    "ReplayReport": "replay",
    "ReplayError": "replay",
    "verify_recording": "replay",
    "verify_sequence": "replay",
    "PlayerSlotStore": "slots",
    "SlotError": "slots",
    "SlotInspection": "slots",
    "SdkWorkQueue": "workers",
    "WorkTicket": "workers",
    "WorkResult": "workers",
    "WorkQueueError": "workers",
    "CertificationError": "certification",
    "CertificationStep": "certification",
    "CertificationReport": "certification",
    "certify_trace": "certification",
}

__all__ = ["SDK_API_VERSION", "SDK_API_STATUS", "SDK_FEATURES", "capabilities",
           *_PUBLIC]


def capabilities():
    """Return a detached machine-readable feature and compatibility contract."""
    return {"api_version": list(SDK_API_VERSION),
            "status": SDK_API_STATUS,
            "features": sorted(SDK_FEATURES),
            "content_schema": 1, "project_schema": 1,
            "game_session_schema": 1}


def __getattr__(name):
    module = _PUBLIC.get(name)
    if module is None:
        raise AttributeError(name)
    value = getattr(import_module("." + module, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
