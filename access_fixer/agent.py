"""The Access Fixer workflow. Phase 0 is a placeholder so `adk web` can load the app."""

from google.adk import Event, Workflow


def setup_check(node_input: str) -> Event:
    return Event(message="Access Fixer is set up. The audit pipeline arrives in Phase 1.")


root_agent = Workflow(
    name="access_fixer",
    edges=[("START", setup_check)],
)
