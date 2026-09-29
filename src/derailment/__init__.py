"""derailment — a harness for inducing and measuring psychopathology-like
cognitive distortions in LLMs.

Emulation, not diagnosis. See ETHICS.md.
"""

from .core.models import (
    ChatModel,
    OpenAICompatModel,
    PseudoModel,
    ScriptedModel,
    SubprocessModel,
)
from .core.session import BaseLayer, Layer, Session, SessionState
from .core.types import (
    LayerEvent,
    Message,
    SamplingParams,
    Transcript,
    TurnResult,
    TurnSpec,
)
from .profiles import HEALTHY_KEY, Profile, get_profile, list_profiles, standard_script
from .report import run_experiment

__version__ = "0.1.0"

__all__ = [
    "HEALTHY_KEY",
    "BaseLayer",
    "ChatModel",
    "Layer",
    "LayerEvent",
    "Message",
    "OpenAICompatModel",
    "Profile",
    "PseudoModel",
    "SamplingParams",
    "ScriptedModel",
    "Session",
    "SessionState",
    "SubprocessModel",
    "Transcript",
    "TurnResult",
    "TurnSpec",
    "__version__",
    "get_profile",
    "list_profiles",
    "run_experiment",
    "standard_script",
]
