# src/core/store.py

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.core.world_model import Artifact


@dataclass
class ArtifactStore:
    """
    Simple in memory registry for Artifacts.

    Stores artifacts by id and provides basic query helpers.
    """

    _artifacts: Dict[str, Artifact]

    def __init__(self) -> None:
        self._artifacts = {}

    def add(self, artifact: Artifact) -> None:
        """
        Add or replace an artifact.
        """
        self._artifacts[artifact.id] = artifact

    def get(self, artifact_id: str) -> Artifact:
        """
        Return an artifact by id, or raise KeyError if not found.
        """
        if artifact_id not in self._artifacts:
            raise KeyError(f"Artifact with id '{artifact_id}' not found")
        return self._artifacts[artifact_id]

    def exists(self, artifact_id: str) -> bool:
        """
        Return True if the artifact id is known.
        """
        return artifact_id in self._artifacts

    def list_ids(self, kind: Optional[str] = None) -> List[str]:
        """
        List artifact ids, optionally filtered by kind.
        """
        if kind is None:
            return list(self._artifacts.keys())

        return [
            artifact_id
            for artifact_id, artifact in self._artifacts.items()
            if artifact.kind == kind
        ]

    def lineage(self, artifact_id: str) -> List[str]:
        """
        Return the full lineage chain for the given artifact id:
        artifact.lineage + [artifact.id]
        """
        artifact = self.get(artifact_id)
        return list(artifact.lineage) + [artifact.id]
