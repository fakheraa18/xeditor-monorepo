from __future__ import annotations

from typing import Any

from apps.code_editor.parsing import parse_to_symbols_and_chunks


async def handle_parse_request(payload: dict[str, Any]):
    """
    Parse a file in the local companion using tree-sitter (local-only).
    Payload schema mirrors frontend: { filePath, content, language }.
    """
    file_path = str(payload.get("filePath") or "")
    content = str(payload.get("content") or "")
    language = str(payload.get("language") or "plaintext")

    if not file_path:
        print("Parse error: Missing filePath")
        return {"error": "Missing filePath"}

    try:
        result = parse_to_symbols_and_chunks(file_path, content, language)
        return result
    except Exception as e:
        # Do not leak content; return minimal error
        print(f"Parse failed: {file_path} - {e.__class__.__name__}: {str(e)}")
        return {"error": f"Companion parse failed: {e.__class__.__name__}: {str(e)}"}

