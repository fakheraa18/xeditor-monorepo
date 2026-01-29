import uvicorn
import argparse
from server import app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XEditor Local Companion")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to run the server on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on file changes")
    args = parser.parse_args()

    if args.reload:
        print(f"Starting XEditor Local Companion on {args.host}:{args.port} with auto-reload enabled")
        uvicorn.run(
            "server:app",
            host=args.host,
            port=args.port,
            reload=True,
            timeout_keep_alive=300,  # Keep websocket connections alive for 5 minutes
            timeout_graceful_shutdown=30,  # Graceful shutdown timeout
        )
    else:
        print(f"Starting XEditor Local Companion on {args.host}:{args.port}")
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            timeout_keep_alive=300,  # Keep websocket connections alive for 5 minutes
            timeout_graceful_shutdown=30,  # Graceful shutdown timeout
        )

