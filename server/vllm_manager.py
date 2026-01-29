"""
Optional vLLM runtime manager for local inference.
Best-effort support - may not be available on all platforms (requires Linux + CUDA).
"""
import subprocess
import os
import platform
from typing import Optional, Dict, Any
import json

class VLLMManager:
    """Manages vLLM server process for local model inference."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.port = 8001  # Default vLLM port
        self.model_path: Optional[str] = None
        self.is_available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if vLLM is available on this system."""
        # vLLM typically requires Linux + CUDA
        if platform.system() != "Linux":
            return False
        
        # Check if vllm is installed
        try:
            import vllm
            return True
        except ImportError:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current vLLM status."""
        return {
            "available": self.is_available,
            "running": self.process is not None and self.process.poll() is None,
            "port": self.port,
            "model_path": self.model_path,
            "platform": platform.system(),
        }
    
    async def start(self, model_path: str, port: int = 8001) -> Dict[str, Any]:
        """Start vLLM server process."""
        if not self.is_available:
            return {
                "error": "vLLM is not available on this platform (requires Linux + CUDA)"
            }
        
        if self.process is not None and self.process.poll() is None:
            return {
                "error": "vLLM server is already running"
            }
        
        try:
            # Start vLLM server as subprocess
            # Note: This is a simplified example - production should handle more options
            cmd = [
                "python", "-m", "vllm.entrypoints.openai.api_server",
                "--model", model_path,
                "--port", str(port),
                "--host", "127.0.0.1",
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )
            
            self.port = port
            self.model_path = model_path
            
            # Wait a bit to see if it starts successfully
            import asyncio
            await asyncio.sleep(2)
            
            if self.process.poll() is not None:
                # Process died immediately
                stderr = self.process.stderr.read().decode() if self.process.stderr else "Unknown error"
                return {
                    "error": f"vLLM server failed to start: {stderr}"
                }
            
            return {
                "status": "started",
                "port": port,
                "model_path": model_path,
            }
        except Exception as e:
            return {
                "error": f"Failed to start vLLM: {str(e)}"
            }
    
    async def stop(self) -> Dict[str, Any]:
        """Stop vLLM server process."""
        if self.process is None:
            return {
                "error": "vLLM server is not running"
            }
        
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None
            self.model_path = None
            return {
                "status": "stopped"
            }
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            self.process = None
            self.model_path = None
            return {
                "status": "stopped",
                "note": "Server was forcefully killed"
            }
        except Exception as e:
            return {
                "error": f"Failed to stop vLLM: {str(e)}"
            }

# Global singleton instance
_vllm_manager: Optional[VLLMManager] = None

def get_vllm_manager() -> VLLMManager:
    """Get the global vLLM manager instance."""
    global _vllm_manager
    if _vllm_manager is None:
        _vllm_manager = VLLMManager()
    return _vllm_manager

