from __future__ import annotations

import re
from collections import Counter

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

_PY = Language(tspython.language())
_PARSER = Parser(_PY)


def _query_tokens(query: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query)}


def _name_query_overlap(name: str, query_tokens: set[str]) -> int:
    """Score how well an identifier overlaps with query terms (snake + camel aware)."""
    chunks: set[str] = set()
    s = name.strip()
    chunks |= {p.lower() for p in re.split(r"[_\s]+", s) if p}
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    chunks |= {p.lower() for p in spaced.split() if p}
    return len(query_tokens & chunks)


def _walk_extract_names(node, source_bytes: bytes) -> list[str]:
    names: list[str] = []
    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            names.append(source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8"))
    elif node.type == "class_definition":
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            names.append(source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8"))
    for child in node.children:
        names.extend(_walk_extract_names(child, source_bytes))
    return names


def _regex_extract_symbols(source: str) -> list[str]:
    """Fallback when tree-sitter fails or returns nothing: module-level-ish def/class names."""
    names: list[str] = []
    for m in re.finditer(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source, re.MULTILINE):
        names.append(m.group(1))
    for m in re.finditer(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b", source, re.MULTILINE):
        names.append(m.group(1))
    return names


def _symbols_for_file(path: str, source: str) -> list[str]:
    if not path.endswith(".py"):
        return []
    names: list[str] = []
    try:
        source_bytes = source.encode("utf-8")
        tree = _PARSER.parse(source_bytes)
        names = _walk_extract_names(tree.root_node, source_bytes)
    except Exception:
        names = []

    if not names:
        names = _regex_extract_symbols(source)

    return names


def find_related_symbols(file_contents: dict[str, str], query_text: str, top_k: int = 25) -> list[str]:
    """
    Deterministic symbol extraction: tree-sitter walk over Python AST, with regex
    extraction as fallback. Results are ranked by overlap with query tokens.
    """
    query_tokens = _query_tokens(query_text)
    if not query_tokens:
        return []

    scores: Counter[str] = Counter()

    for path, source in file_contents.items():
        try:
            names = _symbols_for_file(path, source)
        except Exception:
            names = _regex_extract_symbols(source)

        for name in names:
            ov = _name_query_overlap(name, query_tokens)
            if ov:
                scores[name] += ov

    if not scores:
        for path, source in file_contents.items():
            if not path.endswith(".py"):
                continue
            for name in _regex_extract_symbols(source):
                ov = _name_query_overlap(name, query_tokens)
                if ov:
                    scores[name] += ov

    return [name for name, _ in scores.most_common(top_k)]
