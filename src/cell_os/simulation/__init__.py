"""
Simulation Package

Advanced simulation capabilities for cell_OS:
- Spatial effects (plate edge effects, temperature gradients)
- Multi-assay support (flow, imaging, qPCR, ELISA, Western)
- Failure modes (contamination, equipment failures)
- Experimental design validation (power analysis, batch detection)
"""

from .spatial_effects import (
    SpatialEffectsSimulator,
    PlateGeometry,
    PLATE_96,
    PLATE_384,
    PLATE_6,
    PLATE_24
)

from .multi_assay import (
    MultiAssaySimulator,
    AssayType,
    FlowCytometryResult,
    ImagingResult,
    qPCRResult,
    ELISAResult,
    WesternBlotResult
)

from .failure_modes import (
    FailureModeSimulator,
    FailureType,
    ContaminationType,
    FailureEvent
)

from .design_validation import (
    ExperimentalDesignValidator,
    PowerAnalysisResult,
    BatchConfoundingResult,
    ReplicationResult
)

__all__ = [
    # Spatial effects
    'SpatialEffectsSimulator',
    'PlateGeometry',
    'PLATE_96',
    'PLATE_384',
    'PLATE_6',
    'PLATE_24',
    
    # Multi-assay
    'MultiAssaySimulator',
    'AssayType',
    'FlowCytometryResult',
    'ImagingResult',
    'qPCRResult',
    'ELISAResult',
    'WesternBlotResult',
    
    # Failure modes
    'FailureModeSimulator',
    'FailureType',
    'ContaminationType',
    'FailureEvent',
    
    # Design validation
    'ExperimentalDesignValidator',
    'PowerAnalysisResult',
    'BatchConfoundingResult',
    'ReplicationResult',
]
