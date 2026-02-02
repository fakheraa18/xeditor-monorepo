"""
LLM embedding request handling module.

This module provides embedding functions for text embeddings.
For LLM requests, use the providers package instead:

    from apps.code_editor.providers import get_provider, LLMRequest
    
    provider = get_provider(model_config)
    async for event in provider.stream(request):
        # Handle LLMEvent (type: thinking, content, end, error)
        ...
"""

from typing import Dict, Any

from apps.code_editor.embeddings import embed_one, embed_many

async def handle_embedding_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        model_id = str(payload.get("modelId") or "")
        text = str(payload.get("text") or "")
        token = payload.get("hfToken")

        if not model_id:
            print("Embedding error: Missing modelId")
            return {"error": "Missing modelId"}

        embedding, dim = embed_one(model_id, text, token=token if isinstance(token, str) else None)
        return {
            "embedding": embedding,
            "dim": dim
        }
    except Exception as e:
        print(f"Embedding failed: {model_id} - {str(e)}")
        return {
            "error": str(e)
        }

async def handle_embedding_batch_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        model_id = str(payload.get("modelId") or "")
        texts = payload.get("texts")
        token = payload.get("hfToken")

        if not model_id:
            print("Embedding batch error: Missing modelId")
            return {"error": "Missing modelId"}
        if not isinstance(texts, list):
            print("Embedding batch error: Missing texts")
            return {"error": "Missing texts"}

        embeddings, dim = embed_many(
            model_id,
            [str(t) for t in texts],
            token=token if isinstance(token, str) else None,
        )

        return {
            "embeddings": embeddings,
            "dim": dim
        }
    except Exception as e:
        print(f"Batch embedding failed: {model_id} - {str(e)}")
        return {
            "error": str(e)
        }


