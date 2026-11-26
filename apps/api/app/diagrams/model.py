"""Structured diagram model — LLM may emit this JSON, never raw DOT/D2."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

DiagramKind = Literal["flowchart", "architecture", "sequence"]


class DiagramNode(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    label: str = Field(min_length=1, max_length=120)
    kind: str = "box"  # box | actor | datastore | cloud
    tone: str = "accent"  # theme token key


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: str | None = None


class DiagramModel(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    kind: DiagramKind = "architecture"
    nodes: list[DiagramNode] = Field(min_length=1)
    edges: list[DiagramEdge] = Field(default_factory=list)
    direction: Literal["LR", "TB"] = "TB"


class DiagramValidationError(ValueError):
    pass


def validate_diagram_model(payload: dict[str, Any]) -> DiagramModel:
    # Reject accidental raw diagram languages
    blob = str(payload)
    for banned in ("digraph ", "graph ", "```dot", "```d2", "@startuml"):
        if banned.lower() in blob.lower():
            raise DiagramValidationError(f"Raw diagram language not allowed ({banned.strip()})")
    try:
        model = DiagramModel.model_validate(payload)
    except ValidationError as exc:
        raise DiagramValidationError(str(exc)) from exc
    node_ids = {n.id for n in model.nodes}
    if len(node_ids) != len(model.nodes):
        raise DiagramValidationError("duplicate node ids")
    for edge in model.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            raise DiagramValidationError(
                f"edge {edge.source}->{edge.target} references unknown node"
            )
    return model
