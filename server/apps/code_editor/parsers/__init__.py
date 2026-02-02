"""
Parser loading from prompt sets.
"""

from .base import ResponseParser, ParsedResponse, get_parser_for_model, extract_thinking_from_content, strip_thinking_tags
from apps.code_editor.sets.manager import get_set_manager
import importlib.util
from typing import Optional


def get_parser_for_mode(
    mode: str,
    family: str,
    version: Optional[str] = None,
    set_id: str = "default",
) -> ResponseParser:
    """
    Get parser for a specific mode/family/version from a set.
    
    Note: Parsers are now shared at the family level (not per mode).
    This function maintains API compatibility but uses family-level lookup.
    """
    from .base import get_parser_for_request
    # Use the main parser lookup function which handles family-level parsers
    return get_parser_for_request(set_id, family, version, mode)


__all__ = ['ResponseParser', 'ParsedResponse', 'get_parser_for_model', 'get_parser_for_mode', 'extract_thinking_from_content', 'strip_thinking_tags']
