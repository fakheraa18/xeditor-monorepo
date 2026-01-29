"""
Chat truncation module for XEditor Local Companion.

This module handles truncating chat history from a specific turn onwards.
It's designed as a separate module to allow future expansion for:
- Reverting file changes made after the truncation point
- Cleaning up artifacts created after the truncation point
- Other cleanup operations

For now, it simply truncates the turns list in the chat file.
"""

from typing import Dict, Any, Optional
from chat_manager import get_chat_manager


class ChatTruncator:
    """
    Handles truncation of chat history from a specific turn onwards.
    
    Future expansion:
    - Track file changes made in each turn
    - Revert file changes when truncating
    - Clean up artifacts (plans, generated files, etc.)
    """

    def __init__(self):
        self.chat_manager = get_chat_manager()

    def truncate_from_turn(
        self,
        project_id: str,
        chat_id: str,
        turn_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Truncate a chat from a specific turn onwards.
        
        This removes the specified turn and all turns after it.
        
        Args:
            project_id: The project ID
            chat_id: The chat session ID
            turn_id: The turn ID to truncate from (this turn will be removed)
            
        Returns:
            The updated chat dict, or None if the operation failed
            
        Future:
            - Collect file changes from removed turns
            - Offer to revert those changes
            - Clean up artifacts
        """
        chat = self.chat_manager.load_chat(project_id, chat_id)
        if not chat:
            return None

        turns = chat.get("turns", [])
        
        # Find the index of the turn to truncate from
        turn_index = -1
        for i, turn in enumerate(turns):
            if turn.get("id") == turn_id:
                turn_index = i
                break

        if turn_index == -1:
            # Turn not found
            return None

        # Truncate: keep only turns before the specified turn
        chat["turns"] = turns[:turn_index]

        # Save the updated chat
        if self.chat_manager.save_chat(chat):
            return chat
        return None

    def get_turns_to_remove(
        self,
        project_id: str,
        chat_id: str,
        turn_id: str,
    ) -> list[Dict[str, Any]]:
        """
        Get the list of turns that would be removed by truncation.
        
        Useful for:
        - Showing user what will be removed
        - Collecting file changes to potentially revert
        
        Args:
            project_id: The project ID
            chat_id: The chat session ID
            turn_id: The turn ID to truncate from
            
        Returns:
            List of turns that would be removed
        """
        chat = self.chat_manager.load_chat(project_id, chat_id)
        if not chat:
            return []

        turns = chat.get("turns", [])
        
        # Find the index of the turn to truncate from
        turn_index = -1
        for i, turn in enumerate(turns):
            if turn.get("id") == turn_id:
                turn_index = i
                break

        if turn_index == -1:
            return []

        # Return turns that would be removed (from turn_index onwards)
        return turns[turn_index:]


# Singleton instance
_chat_truncator: Optional[ChatTruncator] = None


def get_chat_truncator() -> ChatTruncator:
    """Get the singleton ChatTruncator instance."""
    global _chat_truncator
    if _chat_truncator is None:
        _chat_truncator = ChatTruncator()
    return _chat_truncator


# RPC Handler

async def handle_truncate_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for truncating a chat from a specific turn."""
    truncator = get_chat_truncator()
    project_id = payload.get("projectId", "")
    chat_id = payload.get("chatId", "")
    turn_id = payload.get("turnId", "")

    if not project_id or not chat_id or not turn_id:
        return {
            "success": False,
            "error": "Project ID, Chat ID, and Turn ID are required",
        }

    try:
        updated_chat = truncator.truncate_from_turn(project_id, chat_id, turn_id)
        if updated_chat:
            return {
                "success": True,
                "chat": updated_chat,
            }
        return {
            "success": False,
            "error": f"Failed to truncate chat. Turn may not exist: {turn_id}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
