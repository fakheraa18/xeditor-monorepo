from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Optional, TypedDict

from tree_sitter import Parser, Node, Tree  # type: ignore[import-untyped]
from tree_sitter_languages import get_language  # type: ignore[import-untyped]


class SymbolRange(TypedDict):
    startLine: int
    startColumn: int
    endLine: int
    endColumn: int


class Symbol(TypedDict, total=False):
    symbolId: str
    name: str
    kind: str
    filePath: str
    range: SymbolRange
    signature: str
    language: str


class GraphEdge(TypedDict):
    fromSymbolId: str
    toName: str
    edgeType: str
    confidence: float


class Chunk(TypedDict):
    chunkId: str
    filePath: str
    startLine: int
    endLine: int
    content: str
    structuredContent: str
    symbolIds: list[str]


class ParseResult(TypedDict):
    symbols: list[Symbol]
    edges: list[GraphEdge]
    chunks: list[Chunk]


_BINARY_EXTS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "svg",
    "ico",
    "woff",
    "woff2",
    "ttf",
    "eot",
    "pdf",
    "zip",
    "tar",
    "gz",
    "webp",
    "eps",
}


def _is_binary_like(file_path: str, content: str) -> bool:
    ext = (file_path.rsplit(".", 1)[-1] if "." in file_path else "").lower()
    if ext in _BINARY_EXTS:
        return True
    # Heuristic: null bytes usually indicate binary
    return "\x00" in content


_PARSER_CACHE: dict[str, Parser] = {}


def _get_parser(language_name: str) -> Optional[Parser]:
    """
    Return a cached parser for a given language. Uses tree_sitter_languages to
    provide bundled grammars. Returns None if language isn't available.
    """
    if language_name in _PARSER_CACHE:
        return _PARSER_CACHE[language_name]

    try:
        lang = get_language(language_name)
    except Exception:
        # Some bundled distributions may not expose tsx separately; fall back to typescript.
        if language_name == "tsx":
            try:
                lang = get_language("typescript")
            except Exception:
                return None
        else:
            return None

    parser = Parser()
    parser.set_language(lang)
    _PARSER_CACHE[language_name] = parser
    return parser


@dataclass(frozen=True)
class _VueScriptBlock:
    content: str
    start_line_offset: int
    lang_hint: Literal["typescript", "javascript"]


_VUE_SCRIPT_RE = re.compile(
    r"<script(?P<attrs>[^>]*)>(?P<body>[\s\S]*?)</script>",
    re.IGNORECASE,
)
_VUE_LANG_RE = re.compile(r'lang\s*=\s*["\'](?P<lang>[^"\']+)["\']', re.IGNORECASE)


def _extract_vue_script(content: str) -> Optional[_VueScriptBlock]:
    """
    Extract the first <script> block. We parse only the script portion with TS/JS.
    Line/column offsets are mapped back to the original file via start_line_offset.
    """
    m = _VUE_SCRIPT_RE.search(content)
    if not m:
        return None

    attrs = m.group("attrs") or ""
    body = m.group("body") or ""

    before = content[: m.start("body")]
    start_line_offset = before.count("\n")

    lang_match = _VUE_LANG_RE.search(attrs)
    lang_raw = (lang_match.group("lang") if lang_match else "").lower()
    lang_hint: Literal["typescript", "javascript"] = "typescript" if lang_raw in {"ts", "tsx", "typescript"} else "javascript"

    return _VueScriptBlock(content=body, start_line_offset=start_line_offset, lang_hint=lang_hint)


def _node_signature(lines: list[str], line_idx: int) -> str:
    if 0 <= line_idx < len(lines):
        return lines[line_idx].strip()
    return ""


def _symbol_id(file_path: str, name: str, start_line: int) -> str:
    return f"{file_path}::{name}::{start_line}"


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _extract_symbols_js_ts(
    root: Node,
    *,
    file_path: str,
    language: str,
    line_offset: int,
    lines: list[str],
) -> tuple[list[Symbol], dict[str, Node]]:
    symbols: list[Symbol] = []
    symbol_nodes: dict[str, Node] = {}

    for node in _walk(root):
        t = node.type

        # function_declaration / function
        if t in {"function_declaration", "function"}:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = name_node.text.decode("utf-8", errors="ignore")
                start_line = node.start_point[0] + line_offset
                sid = _symbol_id(file_path, name, start_line)
                symbol_nodes[sid] = node
                symbols.append(
                    {
                        "symbolId": sid,
                        "name": name,
                        "kind": "function",
                        "filePath": file_path,
                        "range": {
                            "startLine": start_line,
                            "startColumn": node.start_point[1],
                            "endLine": node.end_point[0] + line_offset,
                            "endColumn": node.end_point[1],
                        },
                        "signature": _node_signature(lines, start_line),
                        "language": language,
                    }
                )
                continue

        # class_declaration
        if t == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = name_node.text.decode("utf-8", errors="ignore")
                start_line = node.start_point[0] + line_offset
                sid = _symbol_id(file_path, name, start_line)
                symbol_nodes[sid] = node
                symbols.append(
                    {
                        "symbolId": sid,
                        "name": name,
                        "kind": "class",
                        "filePath": file_path,
                        "range": {
                            "startLine": start_line,
                            "startColumn": node.start_point[1],
                            "endLine": node.end_point[0] + line_offset,
                            "endColumn": node.end_point[1],
                        },
                        "signature": _node_signature(lines, start_line),
                        "language": language,
                    }
                )
                continue

        # interface_declaration / type_alias_declaration (TypeScript)
        if language in {"typescript", "tsx"}:
            if t in {"interface_declaration", "type_alias_declaration"}:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    name = name_node.text.decode("utf-8", errors="ignore")
                    kind = "interface" if t == "interface_declaration" else "type"
                    start_line = node.start_point[0] + line_offset
                    sid = _symbol_id(file_path, name, start_line)
                    symbol_nodes[sid] = node
                    symbols.append(
                        {
                            "symbolId": sid,
                            "name": name,
                            "kind": kind,
                            "filePath": file_path,
                            "range": {
                                "startLine": start_line,
                                "startColumn": node.start_point[1],
                                "endLine": node.end_point[0] + line_offset,
                                "endColumn": node.end_point[1],
                            },
                            "signature": _node_signature(lines, start_line),
                            "language": language,
                        }
                    )
                    continue

        # const x = () => {} / const x = function() {}
        if t == "variable_declaration":
            declarators = [c for c in node.children if c.type == "variable_declarator"]
            for decl in declarators:
                name_node = decl.child_by_field_name("name")
                value_node = decl.child_by_field_name("value")
                if name_node is None or value_node is None:
                    continue
                if value_node.type not in {"arrow_function", "function"}:
                    continue
                name = name_node.text.decode("utf-8", errors="ignore")
                start_line = decl.start_point[0] + line_offset
                sid = _symbol_id(file_path, name, start_line)
                symbol_nodes[sid] = decl
                symbols.append(
                    {
                        "symbolId": sid,
                        "name": name,
                        "kind": "function",
                        "filePath": file_path,
                        "range": {
                            "startLine": start_line,
                            "startColumn": decl.start_point[1],
                            "endLine": decl.end_point[0] + line_offset,
                            "endColumn": decl.end_point[1],
                        },
                        "signature": _node_signature(lines, start_line),
                        "language": language,
                    }
                )

    return symbols, symbol_nodes


def _extract_symbols_python(
    root: Node,
    *,
    file_path: str,
    language: str,
    line_offset: int,
    lines: list[str],
) -> tuple[list[Symbol], dict[str, Node]]:
    symbols: list[Symbol] = []
    symbol_nodes: dict[str, Node] = {}

    for node in _walk(root):
        t = node.type
        if t in {"function_definition", "class_definition"}:
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = name_node.text.decode("utf-8", errors="ignore")
            kind = "function" if t == "function_definition" else "class"
            start_line = node.start_point[0] + line_offset
            sid = _symbol_id(file_path, name, start_line)
            symbol_nodes[sid] = node
            symbols.append(
                {
                    "symbolId": sid,
                    "name": name,
                    "kind": kind,
                    "filePath": file_path,
                    "range": {
                        "startLine": start_line,
                        "startColumn": node.start_point[1],
                        "endLine": node.end_point[0] + line_offset,
                        "endColumn": node.end_point[1],
                    },
                    "signature": _node_signature(lines, start_line),
                    "language": language,
                }
            )

    return symbols, symbol_nodes


def _build_chunks_for_symbols(
    *,
    file_path: str,
    language: str,
    full_lines: list[str],
    symbol_nodes: dict[str, Node],
    line_offset: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    context_before = 2
    context_after = 15

    for sid, node in symbol_nodes.items():
        start_line = node.start_point[0] + line_offset
        end_line = node.end_point[0] + line_offset
        chunk_start = max(0, start_line - context_before)
        chunk_end = min(len(full_lines) - 1, end_line + context_after)
        chunk_content = "\n".join(full_lines[chunk_start : chunk_end + 1])

        # Kind + name are embedded in symbol id; keep structured content stable
        # (clients treat structuredContent as a richer representation for embeddings)
        name = sid.split("::")[1] if "::" in sid else sid
        kind = "SYMBOL"
        structured = f"{kind}: {name}\n{chunk_content}"

        chunks.append(
            {
                "chunkId": f"{sid}::chunk",
                "filePath": file_path,
                "startLine": chunk_start,
                "endLine": chunk_end,
                "content": chunk_content,
                "structuredContent": structured,
                "symbolIds": [sid],
            }
        )

    return chunks


def _build_file_chunks(file_path: str, content: str, *, chunk_size: int = 50) -> list[Chunk]:
    lines = content.split("\n")
    chunks: list[Chunk] = []
    if not lines:
        return chunks
    for i in range(0, len(lines), chunk_size):
        end = min(len(lines) - 1, i + chunk_size - 1)
        chunk_content = "\n".join(lines[i : end + 1])
        chunks.append(
            {
                "chunkId": f"{file_path}::chunk::{i}",
                "filePath": file_path,
                "startLine": i,
                "endLine": end,
                "content": chunk_content,
                "structuredContent": chunk_content,
                "symbolIds": [],
            }
        )
    return chunks


def parse_to_symbols_and_chunks(file_path: str, content: str, language: str) -> ParseResult:
    """
    Parse a file into symbols and chunks using tree-sitter where possible.
    Returns empty edges for now (graph can be expanded later).
    """
    if _is_binary_like(file_path, content):
        return {"symbols": [], "edges": [], "chunks": []}

    full_lines = content.split("\n")

    # Vue SFC: parse first <script> block using TS/JS and map line offsets back.
    if language == "vue":
        block = _extract_vue_script(content)
        if block is None:
            # No script block; chunk the whole file
            return {"symbols": [], "edges": [], "chunks": _build_file_chunks(file_path, content)}

        script_lang = block.lang_hint
        parser_name = "typescript" if script_lang == "typescript" else "javascript"
        parser = _get_parser(parser_name)
        if parser is None:
            return {"symbols": [], "edges": [], "chunks": _build_file_chunks(file_path, content)}

        tree: Optional[Tree] = parser.parse(block.content.encode("utf-8", errors="ignore"))
        if tree is None:
            return {"symbols": [], "edges": [], "chunks": _build_file_chunks(file_path, content)}

        if script_lang == "typescript":
            symbols, symbol_nodes = _extract_symbols_js_ts(
                tree.root_node,
                file_path=file_path,
                language="typescript",
                line_offset=block.start_line_offset,
                lines=full_lines,
            )
        else:
            symbols, symbol_nodes = _extract_symbols_js_ts(
                tree.root_node,
                file_path=file_path,
                language="javascript",
                line_offset=block.start_line_offset,
                lines=full_lines,
            )

        chunks = _build_chunks_for_symbols(
            file_path=file_path,
            language=language,
            full_lines=full_lines,
            symbol_nodes=symbol_nodes,
            line_offset=block.start_line_offset,
        )
        if not chunks:
            chunks = _build_file_chunks(file_path, content)
        return {"symbols": symbols, "edges": [], "chunks": chunks}

    # Tree-sitter supports specific language identifiers
    parser_name_map: dict[str, str] = {
        "typescript": "typescript",
        "tsx": "tsx",
        "javascript": "javascript",
        "jsx": "javascript",
        "python": "python",
        "go": "go",
        "rust": "rust",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "html": "html",
        "css": "css",
        "scss": "scss",
        "json": "json",
    }

    parser_name = parser_name_map.get(language)
    if parser_name is None:
        return {"symbols": [], "edges": [], "chunks": _build_file_chunks(file_path, content)}

    parser = _get_parser(parser_name)
    if parser is None:
        return {"symbols": [], "edges": [], "chunks": _build_file_chunks(file_path, content)}

    tree = parser.parse(content.encode("utf-8", errors="ignore"))
    if tree is None:
        return {"symbols": [], "edges": [], "chunks": _build_file_chunks(file_path, content)}

    if language in {"typescript", "tsx", "javascript", "jsx"}:
        js_ts_lang = "typescript" if language in {"typescript", "tsx"} else "javascript"
        symbols, symbol_nodes = _extract_symbols_js_ts(
            tree.root_node,
            file_path=file_path,
            language=js_ts_lang if language in {"tsx", "jsx"} else language,
            line_offset=0,
            lines=full_lines,
        )
    elif language == "python":
        symbols, symbol_nodes = _extract_symbols_python(
            tree.root_node,
            file_path=file_path,
            language=language,
            line_offset=0,
            lines=full_lines,
        )
    else:
        # For other languages, start with chunking-only for now (still tree-sitter parsed)
        symbols = []
        symbol_nodes = {}

    chunks = _build_chunks_for_symbols(
        file_path=file_path,
        language=language,
        full_lines=full_lines,
        symbol_nodes=symbol_nodes,
        line_offset=0,
    )
    if not chunks:
        chunks = _build_file_chunks(file_path, content)

    return {"symbols": symbols, "edges": [], "chunks": chunks}


