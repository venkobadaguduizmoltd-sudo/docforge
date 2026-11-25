"""Symbol extraction — tree-sitter when available, regex fallback otherwise."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("docforge.analysis.symbols")


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    path: str
    line: int


_PY_DEF = re.compile(r"^(?:async\s+)?def\s+(\w+)\s*\(", re.M)
_PY_CLASS = re.compile(r"^class\s+(\w+)\s*[:(]", re.M)
_JS_FN = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\("
    r"|^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(",
    re.M,
)
_JS_CLASS = re.compile(r"^(?:export\s+)?class\s+(\w+)\b", re.M)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def extract_symbols_regex(path: str, source: str, language: str | None) -> list[Symbol]:
    symbols: list[Symbol] = []
    lang = (language or "").lower()
    if lang == "python":
        for match in _PY_CLASS.finditer(source):
            symbols.append(Symbol(match.group(1), "class", path, _line_of(source, match.start())))
        for match in _PY_DEF.finditer(source):
            symbols.append(Symbol(match.group(1), "function", path, _line_of(source, match.start())))
    elif lang in {"javascript", "typescript"}:
        for match in _JS_CLASS.finditer(source):
            symbols.append(Symbol(match.group(1), "class", path, _line_of(source, match.start())))
        for match in _JS_FN.finditer(source):
            name = match.group(1) or match.group(2)
            if name:
                symbols.append(Symbol(name, "function", path, _line_of(source, match.start())))
    return symbols


def extract_symbols_tree_sitter(path: str, source: str, language: str | None) -> list[Symbol] | None:
    """Return symbols via tree-sitter, or None if grammar/runtime unavailable."""
    lang = (language or "").lower()
    if lang != "python":
        return None
    try:
        import tree_sitter_python as tspy
        from tree_sitter import Language, Parser
    except Exception:  # noqa: BLE001 — optional dependency path
        return None

    try:
        parser = Parser(Language(tspy.language()))
        tree = parser.parse(source.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.debug("tree-sitter parse failed for %s: %s", path, exc)
        return None

    symbols: list[Symbol] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None and name_node.text is not None:
                symbols.append(
                    Symbol(
                        name_node.text.decode("utf-8"),
                        "class",
                        path,
                        name_node.start_point[0] + 1,
                    )
                )
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None and name_node.text is not None:
                symbols.append(
                    Symbol(
                        name_node.text.decode("utf-8"),
                        "function",
                        path,
                        name_node.start_point[0] + 1,
                    )
                )
        stack.extend(node.children)
    return symbols


def extract_symbols(path: str, source: str, language: str | None) -> list[Symbol]:
    ts = extract_symbols_tree_sitter(path, source, language)
    if ts is not None:
        return ts
    return extract_symbols_regex(path, source, language)
