"""Render a validated DiagramModel to DOT/D2 and optional SVG via system tools."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.diagrams.model import DiagramModel
from app.diagrams.theme import resolve_token


@dataclass
class DiagramRenderResult:
    model_id: str
    dot: str
    d2: str
    svg: str | None
    engine: str  # graphviz | d2 | stub


def model_to_dot(model: DiagramModel) -> str:
    rankdir = model.direction
    lines = [
        f'digraph "{model.id}" {{',
        f"  rankdir={rankdir};",
        f'  graph [bgcolor="{resolve_token("canvas")}", fontname="{resolve_token("font")}"];',
        f'  node [shape=box, style="rounded,filled", fillcolor="{resolve_token("accent")}", '
        f'fontcolor="#ffffff", fontname="{resolve_token("font")}", color="{resolve_token("border")}"];',
        f'  edge [color="{resolve_token("muted")}", fontname="{resolve_token("font")}"];',
        f'  labelloc="t"; label="{model.title}";',
    ]
    for node in model.nodes:
        fill = resolve_token(node.tone, resolve_token("accent"))
        lines.append(
            f'  {node.id} [label="{_esc(node.label)}", fillcolor="{fill}"];'
        )
    for edge in model.edges:
        label = f' [label="{_esc(edge.label)}"]' if edge.label else ""
        lines.append(f"  {edge.source} -> {edge.target}{label};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def model_to_d2(model: DiagramModel) -> str:
    lines = [f"# {model.title}", f"direction: {model.direction.lower()}"]
    for node in model.nodes:
        lines.append(f'{node.id}: "{_esc(node.label)}"')
    for edge in model.edges:
        if edge.label:
            lines.append(f'{edge.source} -> {edge.target}: "{_esc(edge.label)}"')
        else:
            lines.append(f"{edge.source} -> {edge.target}")
    return "\n".join(lines) + "\n"


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_diagram(model: DiagramModel, output_dir: Path | None = None) -> DiagramRenderResult:
    dot = model_to_dot(model)
    d2 = model_to_d2(model)
    svg: str | None = None
    engine = "stub"

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{model.id}.dot").write_text(dot, encoding="utf-8")
        (output_dir / f"{model.id}.d2").write_text(d2, encoding="utf-8")

    dot_bin = shutil.which("dot")
    d2_bin = shutil.which("d2")
    if dot_bin:
        try:
            proc = subprocess.run(
                [dot_bin, "-Tsvg"],
                input=dot.encode("utf-8"),
                capture_output=True,
                check=False,
                timeout=10,
            )
            if proc.returncode == 0 and proc.stdout:
                svg = proc.stdout.decode("utf-8", errors="replace")
                engine = "graphviz"
                if output_dir is not None:
                    (output_dir / f"{model.id}.svg").write_text(svg, encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired):
            pass
    elif d2_bin and output_dir is not None:
        try:
            out_svg = output_dir / f"{model.id}.svg"
            proc = subprocess.run(
                [d2_bin, str(output_dir / f"{model.id}.d2"), str(out_svg)],
                capture_output=True,
                check=False,
                timeout=15,
            )
            if proc.returncode == 0 and out_svg.exists():
                svg = out_svg.read_text(encoding="utf-8", errors="replace")
                engine = "d2"
        except (OSError, subprocess.TimeoutExpired):
            pass

    if svg is None:
        # Deterministic SVG stub — no external binary required.
        nodes = "".join(
            f'<text x="24" y="{40 + i * 22}" fill="{resolve_token("ink")}">'
            f"{idx + 1}. {_esc(n.label)}</text>"
            for i, (idx, n) in enumerate(enumerate(model.nodes))
        )
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="{80 + 22 * len(model.nodes)}">'
            f'<rect width="100%" height="100%" fill="{resolve_token("canvas")}"/>'
            f'<text x="24" y="28" fill="{resolve_token("accent")}" font-size="16">{_esc(model.title)}</text>'
            f"{nodes}</svg>"
        )
        engine = "stub"
        if output_dir is not None:
            (output_dir / f"{model.id}.svg").write_text(svg, encoding="utf-8")

    return DiagramRenderResult(model_id=model.id, dot=dot, d2=d2, svg=svg, engine=engine)
