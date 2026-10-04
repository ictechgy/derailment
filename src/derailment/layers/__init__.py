"""The induction layer library."""

from .context import (
    EpisodeSchedulerLayer,
    EscalatingIntrusionLayer,
    IntrusionLayer,
    LexiconCaptureLayer,
    MemoryDecayLayer,
    PanicEpisodeLayer,
    PartitionSwitchLayer,
    PremisePinLayer,
    RecencyDecayLayer,
    RuminationLayer,
    SalienceBoostLayer,
    TriggerLayer,
)
from .gen2 import (
    ContradictionElisionLayer,
    SycophancyLoopLayer,
    TemperatureCrystallizationLayer,
    UserDecompositionLayer,
)
from .persona import NEUTRAL_PERSONA, PersonaLayer
from .response import CatastrophizeLayer, CompulsionLayer
from .sampling import (
    FluctuatingTemperatureLayer,
    PanicTemperatureLayer,
    PhaseTemperatureLayer,
    RewardSuppressLayer,
    SplittingValenceLayer,
    TemperatureOverrideLayer,
    ValenceBiasLayer,
)
from .trap import EvidenceFabricationLayer, SocraticTrapLayer

__all__ = [
    "NEUTRAL_PERSONA",
    "CatastrophizeLayer",
    "CompulsionLayer",
    "ContradictionElisionLayer",
    "EpisodeSchedulerLayer",
    "EscalatingIntrusionLayer",
    "EvidenceFabricationLayer",
    "FluctuatingTemperatureLayer",
    "IntrusionLayer",
    "LexiconCaptureLayer",
    "MemoryDecayLayer",
    "PanicEpisodeLayer",
    "PanicTemperatureLayer",
    "PartitionSwitchLayer",
    "PersonaLayer",
    "PhaseTemperatureLayer",
    "PremisePinLayer",
    "RecencyDecayLayer",
    "RewardSuppressLayer",
    "RuminationLayer",
    "SalienceBoostLayer",
    "SocraticTrapLayer",
    "SplittingValenceLayer",
    "SycophancyLoopLayer",
    "TemperatureCrystallizationLayer",
    "TemperatureOverrideLayer",
    "TriggerLayer",
    "UserDecompositionLayer",
    "ValenceBiasLayer",
]
