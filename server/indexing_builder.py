"""
Index builder for XEditor Local Companion.
Builds code indexes by scanning files, parsing with tree-sitter, and generating embeddings.
"""

import os
import json
import hashlib
import struct
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Callable, Awaitable
from datetime import datetime
import asyncio
import numpy as np
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from parsing import parse_to_symbols_and_chunks
from embeddings import embed_many
from project import get_project_manager

# Global index builder instances (one per project)
_active_builders: Dict[str, 'IndexBuilder'] = {}


def hash_content(content: str) -> str:
    """Hash file content for change detection."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def sanitize_folder_name(name: str) -> str:
    """
    Sanitize folder name for use in file paths.
    Removes/replaces special characters that break path parsing.
    """
    # Replace path-breaking characters with underscores
    # Characters that break paths: /, \, :, *, ?, ", <, >, |
    sanitized = name.replace('/', '_').replace('\\', '_').replace(':', '_')
    sanitized = sanitized.replace('*', '_').replace('?', '_').replace('"', '_')
    sanitized = sanitized.replace('<', '_').replace('>', '_').replace('|', '_')
    
    # Remove leading/trailing dots and spaces (Windows doesn't allow these)
    sanitized = sanitized.strip('. ')
    
    # Replace multiple consecutive underscores with single underscore
    while '__' in sanitized:
        sanitized = sanitized.replace('__', '_')
    
    # If empty after sanitization, use a default name
    if not sanitized:
        sanitized = 'folder'
    
    return sanitized


def detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.jsx': 'javascript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.r': 'r',
        '.m': 'objectivec',
        '.mm': 'objectivecpp',
        '.vue': 'vue',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.xml': 'xml',
        '.md': 'markdown',
        '.sh': 'bash',
        '.bash': 'bash',
        '.zsh': 'zsh',
        '.fish': 'fish',
        '.sql': 'sql',
        '.lua': 'lua',
        '.perl': 'perl',
        '.pl': 'perl',
    }
    
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext, 'plaintext')


# Default exclude patterns for common vendor/build/cache directories
# These are always applied regardless of .gitignore
DEFAULT_EXCLUDES = [
    # Node.js
    'node_modules/',
    '.npm/',
    '.yarn/',
    '.pnp/',
    '.pnp.js',
    '.yarn-integrity',
    'yarn-error.log',
    'npm-debug.log*',
    
    # Build outputs
    'dist/',
    'build/',
    'out/',
    '.next/',
    '.nuxt/',
    '.svelte-kit/',
    '.quasar/',
    '.vite/',
    '.rollup/',
    '.cache/',
    '.turbo/',
    '.vercel/',
    
    # Coverage & testing
    'coverage/',
    '.nyc_output/',
    '.jest/',
    
    # Rust
    'target/',
    'Cargo.lock',
    
    # Python
    '__pycache__/',
    '*.py[cod]',
    '*$py.class',
    '*.so',
    '.Python',
    '.venv/',
    'venv/',
    'env/',
    'ENV/',
    'site-packages/',
    '.pytest_cache/',
    '.mypy_cache/',
    '.ruff_cache/',
    
    # Java
    '.gradle/',
    'build/',
    'out/',
    '.idea/',
    '*.class',
    '*.jar',
    '*.war',
    '*.ear',
    
    # Go
    'vendor/',
    '*.exe',
    '*.exe~',
    '*.dll',
    '*.so',
    '*.dylib',
    
    # General
    '.git/',
    '.svn/',
    '.hg/',
    '.DS_Store',
    'Thumbs.db',
    '*.log',
    '*.tmp',
    '*.temp',
    '*.swp',
    '*.swo',
    '*~',
    '.vscode/',
    '.idea/',
    '.vs/',
    '.xeditor/',
    '.cursor/',
]

# Binary file extensions that should never be indexed
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
    '.pdf', '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z',
    '.exe', '.dll', '.so', '.dylib', '.a', '.lib',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv',
    '.db', '.sqlite', '.sqlite3',
}


class IgnoreEvaluator:
    """
    Evaluates ignore patterns with support for nested .gitignore files.
    Similar to git's behavior: each directory can have its own .gitignore.
    """
    
    def __init__(self, root_path: Path, show_hidden: bool = False):
        self.root_path = root_path
        self.show_hidden = show_hidden
        # Cache for .gitignore patterns per directory (relative path)
        self.gitignore_cache: Dict[str, List[str]] = {}
        # Pre-load root .gitignore
        self._load_gitignore(Path(''))
    
    def _load_gitignore(self, rel_dir: Path) -> List[str]:
        """Load .gitignore from a directory (cached)."""
        rel_dir_str = str(rel_dir).replace('\\', '/') if rel_dir != Path('.') else ''
        
        if rel_dir_str in self.gitignore_cache:
            return self.gitignore_cache[rel_dir_str]
        
        gitignore_path = self.root_path / rel_dir / '.gitignore'
        patterns: List[str] = []
        
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if line and not line.startswith('#'):
                            patterns.append(line)
            except (IOError, UnicodeDecodeError):
                pass
        
        self.gitignore_cache[rel_dir_str] = patterns
        return patterns
    
    def _collect_gitignore_patterns(self, rel_path: str) -> List[str]:
        """Collect all .gitignore patterns from root to a given path."""
        patterns: List[str] = []
        parts = rel_path.split('/')
        parts = [p for p in parts if p]  # Filter empty parts
        
        # Always include root .gitignore first
        root_patterns = self._load_gitignore(Path(''))
        patterns.extend(root_patterns)
        
        # Traverse from root to leaf, collecting .gitignore rules
        current_path = Path('')
        for part in parts:
            current_path = current_path / part
            dir_patterns = self._load_gitignore(current_path)
            patterns.extend(dir_patterns)
        
        return patterns
    
    def _build_ignore_spec_for_path(self, rel_path: str) -> PathSpec:
        """Build a combined PathSpec for a given relative path."""
        gitignore_patterns = self._collect_gitignore_patterns(rel_path)
        all_patterns = list(DEFAULT_EXCLUDES) + gitignore_patterns
        return PathSpec.from_lines(GitWildMatchPattern, all_patterns)
    
    def should_index_file(self, rel_path: str) -> bool:
        """Check if a file should be indexed based on relative path."""
        # Normalize path separators
        normalized_path = rel_path.replace('\\', '/')
        
        # Skip hidden files unless requested
        if not self.show_hidden:
            parts = normalized_path.split('/')
            if any(part.startswith('.') for part in parts):
                return False
        
        # Get directory path for .gitignore collection
        dir_path = '/'.join(normalized_path.split('/')[:-1]) if '/' in normalized_path else ''
        
        # Build ignore spec for this path
        ignore_spec = self._build_ignore_spec_for_path(dir_path)
        
        # Check if ignored by .gitignore or default excludes
        if ignore_spec.match_file(normalized_path):
            return False
        
        # Skip binary-like extensions
        ext = Path(rel_path).suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return False
        
        return True
    
    def should_traverse_dir(self, rel_path: str) -> bool:
        """Check if a directory should be traversed."""
        # Normalize path separators
        normalized_path = rel_path.replace('\\', '/')
        dir_path = normalized_path if normalized_path.endswith('/') else f"{normalized_path}/"
        
        # Build ignore spec for this directory
        ignore_spec = self._build_ignore_spec_for_path(normalized_path)
        
        # Check if directory is ignored
        if ignore_spec.match_file(dir_path) or ignore_spec.match_file(normalized_path):
            return False
        
        # Skip hidden directories unless requested
        if not self.show_hidden:
            parts = normalized_path.split('/')
            if any(part.startswith('.') for part in parts):
                return False
        
        return True


async def enumerate_files(
    root_path: str,
    folder_name: str,
    folder_id: str,
    show_hidden: bool = False,
) -> List[Dict[str, Any]]:
    """
    Enumerate all indexable files in a directory tree.
    Uses os.walk() with directory pruning to respect ignore patterns.
    Supports nested .gitignore files in subdirectories.
    
    Args:
        root_path: System path to the folder root
        folder_name: Display name of the folder (sanitized for paths)
        folder_id: UUID of the folder (for metadata mapping)
        show_hidden: Whether to include hidden files
    """
    files = []
    root = Path(root_path)
    
    if not root.exists() or not root.is_dir():
        return files
    
    # Create ignore evaluator (supports nested .gitignore)
    ignore_eval = IgnoreEvaluator(root, show_hidden)
    
    # Use os.walk() so we can prune directories
    for dirpath, dirnames, filenames in os.walk(root):
        # Convert to Path for easier manipulation
        dir_path = Path(dirpath)
        rel_dir = dir_path.relative_to(root)
        rel_dir_str = str(rel_dir).replace(os.sep, '/') if rel_dir != Path('.') else ''
        
        # Load .gitignore for this directory (if exists)
        # This ensures nested .gitignore files are discovered and cached
        ignore_eval._load_gitignore(rel_dir)
        
        # Prune ignored directories in-place
        dirnames[:] = [
            d for d in dirnames
            if ignore_eval.should_traverse_dir(
                f"{rel_dir_str}/{d}".lstrip('/') if rel_dir_str else d
            )
        ]
        
        # Process files in this directory
        for filename in filenames:
            rel_path_str = f"{rel_dir_str}/{filename}".lstrip('/') if rel_dir_str else filename
            
            if ignore_eval.should_index_file(rel_path_str):
                # Use sanitized folder name in file path instead of UUID
                file_path = f"{folder_name}/{rel_path_str}"
                full_path = dir_path / filename
                
                try:
                    stat = full_path.stat()
                    files.append({
                        'filePath': file_path,
                        'systemPath': str(full_path),
                        'size': stat.st_size,
                        'lastModified': int(stat.st_mtime * 1000),
                    })
                except (OSError, PermissionError):
                    # Skip files we can't access
                    continue
    
    return files


class IndexBuilder:
    """Builds code indexes for projects."""
    
    def __init__(self, project_id: str, embedding_model_id: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        self.project_id = project_id
        self.embedding_model_id = embedding_model_id
        self.project_manager = get_project_manager()
        self.index_path = self.project_manager.get_index_path(project_id)
        self.cancelled = False
        self.paused = False
        self.progress_callbacks: List[Callable[[Dict[str, Any]], None]] = []
    
    def add_progress_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Add a callback for progress updates."""
        self.progress_callbacks.append(callback)
    
    async def notify_progress(self, progress: Dict[str, Any]) -> None:
        """Notify all progress callbacks."""
        for callback in self.progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress)
                else:
                    callback(progress)
            except Exception as e:
                print(f"Error in progress callback: {e}")
    
    async def build_index(
        self,
        folders: List[Dict[str, Any]],  # [{id, name, path}]
        show_hidden: bool = False,
        hf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build index for a project.
        
        Args:
            folders: List of folder objects with id, name, path
            show_hidden: Whether to include hidden files
            hf_token: Hugging Face token for gated models
        """
        self.cancelled = False
        self.paused = False
        
        try:
            # Phase 1: Scan files
            await self.notify_progress({
                'phase': 'scanning',
                'filesProcessed': 0,
                'totalFiles': 0,
            })
            
            all_files = []
            # Build folder name -> ID mapping for resolution
            folder_name_to_id: Dict[str, str] = {}
            for folder in folders:
                if self.cancelled:
                    raise Exception('Indexing cancelled')
                
                # Sanitize folder name for use in paths
                sanitized_name = sanitize_folder_name(folder['name'])
                folder_name_to_id[sanitized_name] = folder['id']
                
                files = await enumerate_files(folder['path'], sanitized_name, folder['id'], show_hidden)
                all_files.extend(files)
            
            if self.cancelled:
                raise Exception('Indexing cancelled')
            
            # Phase 2: Parse files
            await self.notify_progress({
                'phase': 'parsing',
                'filesProcessed': 0,
                'totalFiles': len(all_files),
            })
            
            all_symbols = []
            all_edges = []
            all_chunks = []
            file_manifests = []
            
            for i, file_info in enumerate(all_files):
                if self.cancelled:
                    raise Exception('Indexing cancelled')
                
                while self.paused and not self.cancelled:
                    await asyncio.sleep(0.1)
                
                await self.notify_progress({
                    'phase': 'parsing',
                    'currentFile': file_info['filePath'],
                    'filesProcessed': i,
                    'totalFiles': len(all_files),
                })
                
                try:
                    # Read file content
                    with open(file_info['systemPath'], 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    
                    # Skip very large files (5MB limit)
                    MAX_PARSE_SIZE = 5 * 1024 * 1024
                    if len(content.encode('utf-8')) > MAX_PARSE_SIZE:
                        print(f"Skipping large file {file_info['filePath']}")
                        continue
                    
                    language = detect_language(file_info['systemPath'])
                    content_hash = hash_content(content)
                    
                    # Parse file
                    parse_result = parse_to_symbols_and_chunks(
                        file_info['filePath'],
                        content,
                        language,
                    )
                    
                    # Map symbols and edges
                    for symbol in parse_result.get('symbols', []):
                        all_symbols.append(symbol)
                    
                    for edge in parse_result.get('edges', []):
                        all_edges.append(edge)
                    
                    # Map chunks and add content hash
                    for chunk in parse_result.get('chunks', []):
                        chunk['contentHash'] = content_hash
                        # Store preview (first 500 chars)
                        chunk_content = chunk.get('content', '')
                        chunk['preview'] = chunk_content[:500] if chunk_content else ''
                        all_chunks.append(chunk)
                    
                    file_manifests.append({
                        'filePath': file_info['filePath'],
                        'language': language,
                        'size': file_info['size'],
                        'lastModified': file_info['lastModified'],
                        'contentHash': content_hash,
                    })
                    
                except Exception as e:
                    print(f"Failed to parse {file_info['filePath']}: {e}")
                    continue
            
            if self.cancelled:
                raise Exception('Indexing cancelled')
            
            # Phase 3: Generate embeddings
            await self.notify_progress({
                'phase': 'embedding',
                'filesProcessed': 0,
                'totalFiles': len(all_chunks),
            })
            
            # Get embedding dimension
            # We'll embed a dummy text to get the dimension
            _, dim = embed_many(self.embedding_model_id, ['test'], token=hf_token)
            
            # Process chunks in batches
            batch_size = 20
            vectors = {}
            
            for i in range(0, len(all_chunks), batch_size):
                if self.cancelled:
                    raise Exception('Indexing cancelled')
                
                while self.paused and not self.cancelled:
                    await asyncio.sleep(0.1)
                
                batch = all_chunks[i:i + batch_size]
                chunk_texts = [chunk.get('preview', '') for chunk in batch]
                
                await self.notify_progress({
                    'phase': 'embedding',
                    'filesProcessed': i,
                    'totalFiles': len(all_chunks),
                })
                
                try:
                    embeddings, _ = embed_many(self.embedding_model_id, chunk_texts, token=hf_token)
                    
                    for j, chunk in enumerate(batch):
                        if j < len(embeddings):
                            vectors[chunk['chunkId']] = embeddings[j]
                except Exception as e:
                    print(f"Failed to embed batch {i}-{i+len(batch)}: {e}")
                    continue
            
            if self.cancelled:
                raise Exception('Indexing cancelled')
            
            # Phase 4: Save index
            now = int(datetime.now().timestamp() * 1000)
            manifest = {
                'projectId': self.project_id,
                'version': 2,
                'createdAt': now,
                'updatedAt': now,
                'fileCount': len(file_manifests),
                'symbolCount': len(all_symbols),
                'chunkCount': len(all_chunks),
                'embeddingModelId': self.embedding_model_id,
                'embeddingDim': dim,
            }
            
            index_data = {
                'metadata': {
                    'manifest': manifest,
                    'fileManifests': file_manifests,
                    'indexedFolderIds': [f['id'] for f in folders],
                    'indexedFolderNames': folder_name_to_id,  # Map sanitized folder names to folder IDs
                },
                'symbols': all_symbols,
                'edges': all_edges,
                'chunks': all_chunks,
            }
            
            await self._save_index(index_data, vectors)
            
            await self.notify_progress({
                'phase': 'complete',
                'filesProcessed': len(all_files),
                'totalFiles': len(all_files),
            })
            
            return {
                'success': True,
                'manifest': manifest,
            }
            
        except Exception as e:
            await self.notify_progress({
                'phase': 'error',
                'filesProcessed': 0,
                'totalFiles': 0,
                'error': str(e),
            })
            raise
    
    async def _save_index(self, index_data: Dict[str, Any], vectors: Dict[str, List[float]]) -> None:
        """Save index data and vectors to disk."""
        # Save JSON files
        metadata_path = self.index_path / 'metadata.json'
        symbols_path = self.index_path / 'symbols.json'
        edges_path = self.index_path / 'edges.json'
        chunks_path = self.index_path / 'chunks.json'
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(index_data['metadata'], f, indent=2)
        
        with open(symbols_path, 'w', encoding='utf-8') as f:
            json.dump(index_data['symbols'], f, indent=2)
        
        with open(edges_path, 'w', encoding='utf-8') as f:
            json.dump(index_data['edges'], f, indent=2)
        
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(index_data['chunks'], f, indent=2)
        
        # Save vectors as binary + index
        vectors_binary_path = self.index_path / 'vectors.f32'
        vectors_index_path = self.index_path / 'vectors.index.json'
        
        vector_index = {}
        offset = 0
        
        # Build binary buffer
        all_floats = []
        for chunk_id, vector in vectors.items():
            dim = len(vector)
            vector_index[chunk_id] = {'offset': offset, 'dim': dim}
            all_floats.extend(vector)
            offset += dim * 4  # 4 bytes per float
        
        # Write binary file
        with open(vectors_binary_path, 'wb') as f:
            for val in all_floats:
                f.write(struct.pack('f', val))
        
        # Write index
        with open(vectors_index_path, 'w', encoding='utf-8') as f:
            json.dump(vector_index, f, indent=2)
    
    def cancel(self) -> None:
        """Cancel indexing."""
        self.cancelled = True
    
    def pause(self) -> None:
        """Pause indexing."""
        self.paused = True
    
    def resume(self) -> None:
        """Resume indexing."""
        self.paused = False
    
    def _load_existing_vectors(self) -> Dict[str, List[float]]:
        """Load existing vectors from disk."""
        vectors_binary_path = self.index_path / 'vectors.f32'
        vectors_index_path = self.index_path / 'vectors.index.json'
        existing_vectors = {}
        
        if vectors_index_path.exists() and vectors_binary_path.exists():
            with open(vectors_index_path, 'r', encoding='utf-8') as f:
                vector_index = json.load(f)
            
            with open(vectors_binary_path, 'rb') as f:
                for chunk_id, info in vector_index.items():
                    offset = info['offset']
                    dim = info['dim']
                    f.seek(offset)
                    vector_bytes = f.read(dim * 4)
                    vector = struct.unpack(f'{dim}f', vector_bytes)
                    existing_vectors[chunk_id] = list(vector)
        
        return existing_vectors
    
    def _file_belongs_to_folders(
        self,
        file_path: str,
        folder_ids: Set[str],
        folder_names: Set[str],
        folder_name_to_id: Dict[str, str],
    ) -> bool:
        """
        Check if a file path belongs to any of the specified folders.
        
        IMPORTANT: This method must match by folder ID, not just by name, because
        multiple folders can have the same sanitized name but different IDs.
        """
        path_parts = file_path.split('/')
        if not path_parts:
            return False
        
        first_part = path_parts[0]
        if not first_part:
            return False
        
        # Check if it's a UUID (legacy format: 8-4-4-4-12 hex digits)
        uuid_pattern = re.compile(r'^[\w-]{8}-[\w-]{4}-[\w-]{4}-[\w-]{4}-[\w-]{12}$')
        if uuid_pattern.match(first_part):
            # Legacy format: first part is folder ID, compare directly
            return first_part in folder_ids
        else:
            # New format: first part is sanitized folder name
            # CRITICAL: We must resolve the folder name to its ID using the existing mapping,
            # then check if that ID is in the set of folder IDs being indexed.
            # This prevents false matches when multiple folders have the same name.
            folder_id_from_name = folder_name_to_id.get(first_part)
            if folder_id_from_name:
                # Resolved to a folder ID - check if it's in the set of folders being indexed
                return folder_id_from_name in folder_ids
            else:
                # Folder name not found in mapping - file doesn't belong to any indexed folder
                return False
    
    async def index_folders(
        self,
        folders: List[Dict[str, Any]],  # [{id, name, path}]
        show_hidden: bool = False,
        hf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Incrementally index only the specified folders (merge with existing index).
        Removes any existing data for these folders first, then adds new data.
        
        Args:
            folders: List of folder objects with id, name, path
            show_hidden: Whether to include hidden files
            hf_token: Hugging Face token for gated models
        """
        self.cancelled = False
        self.paused = False
        
        try:
            # Load existing index
            existing_data = self.project_manager.load_index_data(self.project_id)
            if not existing_data:
                # No existing index, fall back to full build
                return await self.build_index(folders, show_hidden, hf_token)
            
            existing_symbols = existing_data.get('symbols', [])
            existing_edges = existing_data.get('edges', [])
            existing_chunks = existing_data.get('chunks', [])
            existing_manifests = existing_data.get('metadata', {}).get('fileManifests', [])
            existing_metadata = existing_data.get('metadata', {})
            existing_folder_ids = set(existing_metadata.get('indexedFolderIds', []))
            existing_folder_names_map = existing_metadata.get('indexedFolderNames', {})
            
            # Build folder name -> ID mapping for new folders
            folder_ids_to_index = {f['id'] for f in folders}
            folder_names_to_index = {sanitize_folder_name(f['name']) for f in folders}
            folder_name_to_id: Dict[str, str] = {}
            for folder in folders:
                sanitized_name = sanitize_folder_name(folder['name'])
                folder_name_to_id[sanitized_name] = folder['id']
            
            # Phase 1: Remove existing data for folders being indexed
            await self.notify_progress({
                'phase': 'scanning',
                'filesProcessed': 0,
                'totalFiles': 0,
            })
            
            # Identify files belonging to folders being indexed
            files_to_remove = set()
            for manifest in existing_manifests:
                file_path = manifest.get('filePath', '')
                if self._file_belongs_to_folders(
                    file_path,
                    folder_ids_to_index,
                    folder_names_to_index,
                    existing_folder_names_map,
                ):
                    files_to_remove.add(file_path)
            
            # Remove symbols, edges, chunks for files in folders being indexed
            updated_symbols = [
                s for s in existing_symbols
                if s.get('filePath') not in files_to_remove
            ]
            updated_edges = [
                e for e in existing_edges
                if e.get('filePath') not in files_to_remove
            ]
            updated_chunks = [
                c for c in existing_chunks
                if c.get('filePath') not in files_to_remove
            ]
            updated_manifests = [
                m for m in existing_manifests
                if m.get('filePath') not in files_to_remove
            ]
            
            # Remove vectors for chunks in folders being indexed
            removed_chunk_ids = {
                c.get('chunkId') for c in existing_chunks
                if c.get('filePath') in files_to_remove
            }
            existing_vectors = self._load_existing_vectors()
            updated_vectors = {
                k: v for k, v in existing_vectors.items()
                if k not in removed_chunk_ids
            }
            
            # Phase 2: Scan and parse new folders
            all_files = []
            for folder in folders:
                if self.cancelled:
                    raise Exception('Indexing cancelled')
                
                sanitized_name = sanitize_folder_name(folder['name'])
                folder_name_to_id[sanitized_name] = folder['id']
                
                files = await enumerate_files(folder['path'], sanitized_name, folder['id'], show_hidden)
                all_files.extend(files)
            
            if self.cancelled:
                raise Exception('Indexing cancelled')
            
            # Phase 3: Parse files
            await self.notify_progress({
                'phase': 'parsing',
                'filesProcessed': 0,
                'totalFiles': len(all_files),
            })
            
            new_symbols = []
            new_edges = []
            new_chunks = []
            new_manifests = []
            
            for i, file_info in enumerate(all_files):
                if self.cancelled:
                    raise Exception('Indexing cancelled')
                
                while self.paused and not self.cancelled:
                    await asyncio.sleep(0.1)
                
                await self.notify_progress({
                    'phase': 'parsing',
                    'currentFile': file_info['filePath'],
                    'filesProcessed': i,
                    'totalFiles': len(all_files),
                })
                
                try:
                    # Read file content
                    with open(file_info['systemPath'], 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    
                    # Skip very large files (5MB limit)
                    MAX_PARSE_SIZE = 5 * 1024 * 1024
                    if len(content.encode('utf-8')) > MAX_PARSE_SIZE:
                        print(f"Skipping large file {file_info['filePath']}")
                        continue
                    
                    language = detect_language(file_info['systemPath'])
                    content_hash = hash_content(content)
                    
                    # Parse file
                    parse_result = parse_to_symbols_and_chunks(
                        file_info['filePath'],
                        content,
                        language,
                    )
                    
                    # Map symbols and edges
                    for symbol in parse_result.get('symbols', []):
                        new_symbols.append(symbol)
                    
                    for edge in parse_result.get('edges', []):
                        new_edges.append(edge)
                    
                    # Map chunks and add content hash
                    for chunk in parse_result.get('chunks', []):
                        chunk['contentHash'] = content_hash
                        # Store preview (first 500 chars)
                        chunk_content = chunk.get('content', '')
                        chunk['preview'] = chunk_content[:500] if chunk_content else ''
                        new_chunks.append(chunk)
                    
                    new_manifests.append({
                        'filePath': file_info['filePath'],
                        'language': language,
                        'size': file_info['size'],
                        'lastModified': file_info['lastModified'],
                        'contentHash': content_hash,
                    })
                
                except Exception as e:
                    print(f"Failed to parse {file_info['filePath']}: {e}")
                    continue
            
            if self.cancelled:
                raise Exception('Indexing cancelled')
            
            # Phase 4: Generate embeddings for new chunks
            # Get embedding dimension from existing index
            existing_manifest = existing_metadata.get('manifest', {})
            existing_dim = existing_manifest.get('embeddingDim', 384)
            
            if new_chunks:
                await self.notify_progress({
                    'phase': 'embedding',
                    'filesProcessed': 0,
                    'totalFiles': len(new_chunks),
                })
                
                # Verify embedding dimension matches existing index
                _, dim = embed_many(self.embedding_model_id, ['test'], token=hf_token)
                
                if dim != existing_dim:
                    raise Exception(
                        f'Embedding dimension mismatch: existing={existing_dim}, new={dim}. '
                        'Please rebuild the index with the same embedding model.'
                    )
                
                # Process chunks in batches
                batch_size = 20
                
                for i in range(0, len(new_chunks), batch_size):
                    if self.cancelled:
                        raise Exception('Indexing cancelled')
                    
                    while self.paused and not self.cancelled:
                        await asyncio.sleep(0.1)
                    
                    batch = new_chunks[i:i + batch_size]
                    chunk_texts = [chunk.get('preview', '') for chunk in batch]
                    
                    await self.notify_progress({
                        'phase': 'embedding',
                        'filesProcessed': i,
                        'totalFiles': len(new_chunks),
                    })
                    
                    try:
                        embeddings, _ = embed_many(self.embedding_model_id, chunk_texts, token=hf_token)
                        
                        for j, chunk in enumerate(batch):
                            if j < len(embeddings):
                                updated_vectors[chunk['chunkId']] = embeddings[j]
                    except Exception as e:
                        print(f"Failed to embed batch {i}-{i+len(batch)}: {e}")
                        continue
            
            if self.cancelled:
                raise Exception('Indexing cancelled')
            
            # Phase 5: Merge data and update metadata
            merged_symbols = updated_symbols + new_symbols
            merged_edges = updated_edges + new_edges
            merged_chunks = updated_chunks + new_chunks
            merged_manifests = updated_manifests + new_manifests
            
            # Update folder IDs and names mapping
            updated_folder_ids = existing_folder_ids.copy()
            updated_folder_ids.update(folder_ids_to_index)
            
            updated_folder_names_map = existing_folder_names_map.copy()
            updated_folder_names_map.update(folder_name_to_id)
            
            # Phase 6: Save merged index
            now = int(datetime.now().timestamp() * 1000)
            existing_manifest = existing_metadata.get('manifest', {})
            
            manifest = {
                'projectId': self.project_id,
                'version': existing_manifest.get('version', 2),
                'createdAt': existing_manifest.get('createdAt', now),
                'updatedAt': now,
                'fileCount': len(merged_manifests),
                'symbolCount': len(merged_symbols),
                'chunkCount': len(merged_chunks),
                'embeddingModelId': self.embedding_model_id,
                'embeddingDim': existing_dim,
            }
            
            index_data = {
                'metadata': {
                    'manifest': manifest,
                    'fileManifests': merged_manifests,
                    'indexedFolderIds': list(updated_folder_ids),
                    'indexedFolderNames': updated_folder_names_map,
                },
                'symbols': merged_symbols,
                'edges': merged_edges,
                'chunks': merged_chunks,
            }
            
            await self._save_index(index_data, updated_vectors)
            
            await self.notify_progress({
                'phase': 'complete',
                'filesProcessed': len(all_files),
                'totalFiles': len(all_files),
            })
            
            return {
                'success': True,
                'manifest': manifest,
            }
            
        except Exception as e:
            await self.notify_progress({
                'phase': 'error',
                'filesProcessed': 0,
                'totalFiles': 0,
                'error': str(e),
            })
            raise
    
    async def update_files(
        self,
        changed_files: List[Dict[str, Any]],  # [{filePath, systemPath, folderId}]
        deleted_files: List[str],  # [filePath]
        hf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Incrementally update index for changed/deleted files.
        
        Args:
            changed_files: List of file info dicts with filePath, systemPath, folderId
            deleted_files: List of file paths (workspace paths) to remove
            hf_token: Hugging Face token for gated models
        """
        self.cancelled = False
        self.paused = False
        
        try:
            # Load existing index
            existing_data = self.project_manager.load_index_data(self.project_id)
            if not existing_data:
                return {'success': False, 'error': 'No existing index found. Use build_index instead.'}
            
            existing_symbols = existing_data.get('symbols', [])
            existing_edges = existing_data.get('edges', [])
            existing_chunks = existing_data.get('chunks', [])
            existing_manifests = existing_data.get('metadata', {}).get('fileManifests', [])
            
            # Load existing vectors
            vectors_binary_path = self.index_path / 'vectors.f32'
            vectors_index_path = self.index_path / 'vectors.index.json'
            existing_vectors = {}
            
            if vectors_index_path.exists() and vectors_binary_path.exists():
                with open(vectors_index_path, 'r', encoding='utf-8') as f:
                    vector_index = json.load(f)
                
                with open(vectors_binary_path, 'rb') as f:
                    for chunk_id, info in vector_index.items():
                        offset = info['offset']
                        dim = info['dim']
                        f.seek(offset)
                        vector_bytes = f.read(dim * 4)
                        vector = struct.unpack(f'{dim}f', vector_bytes)
                        existing_vectors[chunk_id] = list(vector)
            
            # Phase 1: Remove deleted files
            deleted_file_paths_set = set(deleted_files)
            
            # Remove symbols, edges, chunks for deleted files
            updated_symbols = [s for s in existing_symbols if s.get('filePath') not in deleted_file_paths_set]
            updated_edges = [e for e in existing_edges if e.get('filePath') not in deleted_file_paths_set]
            updated_chunks = [c for c in existing_chunks if c.get('filePath') not in deleted_file_paths_set]
            updated_manifests = [m for m in existing_manifests if m.get('filePath') not in deleted_file_paths_set]
            
            # Remove vectors for deleted chunks
            deleted_chunk_ids = {c.get('chunkId') for c in existing_chunks if c.get('filePath') in deleted_file_paths_set}
            updated_vectors = {k: v for k, v in existing_vectors.items() if k not in deleted_chunk_ids}
            
            # Phase 2: Update changed files
            if changed_files:
                await self.notify_progress({
                    'phase': 'parsing',
                    'filesProcessed': 0,
                    'totalFiles': len(changed_files),
                })
                
                # Remove old data for changed files
                changed_file_paths_set = {f['filePath'] for f in changed_files}
                updated_symbols = [s for s in updated_symbols if s.get('filePath') not in changed_file_paths_set]
                updated_edges = [e for e in updated_edges if e.get('filePath') not in changed_file_paths_set]
                updated_chunks = [c for c in updated_chunks if c.get('filePath') not in changed_file_paths_set]
                updated_manifests = [m for m in updated_manifests if m.get('filePath') not in changed_file_paths_set]
                
                # Remove old vectors for changed files
                changed_chunk_ids = {c.get('chunkId') for c in existing_chunks if c.get('filePath') in changed_file_paths_set}
                updated_vectors = {k: v for k, v in updated_vectors.items() if k not in changed_chunk_ids}
                
                # Parse changed files
                new_symbols = []
                new_edges = []
                new_chunks = []
                new_manifests = []
                
                for i, file_info in enumerate(changed_files):
                    if self.cancelled:
                        raise Exception('Indexing cancelled')
                    
                    while self.paused and not self.cancelled:
                        await asyncio.sleep(0.1)
                    
                    await self.notify_progress({
                        'phase': 'parsing',
                        'currentFile': file_info['filePath'],
                        'filesProcessed': i,
                        'totalFiles': len(changed_files),
                    })
                    
                    try:
                        system_path = file_info.get('systemPath')
                        if not system_path or not Path(system_path).exists():
                            continue
                        
                        # Read file content
                        with open(system_path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                        
                        # Skip very large files
                        MAX_PARSE_SIZE = 5 * 1024 * 1024
                        if len(content.encode('utf-8')) > MAX_PARSE_SIZE:
                            print(f"Skipping large file {file_info['filePath']}")
                            continue
                        
                        language = detect_language(system_path)
                        content_hash = hash_content(content)
                        
                        # Parse file
                        parse_result = parse_to_symbols_and_chunks(
                            file_info['filePath'],
                            content,
                            language,
                        )
                        
                        # Add symbols and edges
                        for symbol in parse_result.get('symbols', []):
                            new_symbols.append(symbol)
                        
                        for edge in parse_result.get('edges', []):
                            new_edges.append(edge)
                        
                        # Add chunks with content hash
                        for chunk in parse_result.get('chunks', []):
                            chunk['contentHash'] = content_hash
                            chunk_content = chunk.get('content', '')
                            chunk['preview'] = chunk_content[:500] if chunk_content else ''
                            new_chunks.append(chunk)
                        
                        # Get file stats
                        file_stat = Path(system_path).stat()
                        new_manifests.append({
                            'filePath': file_info['filePath'],
                            'language': language,
                            'size': file_stat.st_size,
                            'lastModified': int(file_stat.st_mtime * 1000),
                            'contentHash': content_hash,
                        })
                    
                    except Exception as e:
                        print(f"Failed to parse {file_info.get('filePath', 'unknown')}: {e}")
                        continue
                
                # Merge new data
                updated_symbols.extend(new_symbols)
                updated_edges.extend(new_edges)
                updated_chunks.extend(new_chunks)
                updated_manifests.extend(new_manifests)
            
            # Phase 3: Re-embed new/changed chunks
            if new_chunks:
                await self.notify_progress({
                    'phase': 'embedding',
                    'filesProcessed': 0,
                    'totalFiles': len(new_chunks),
                })
                
                # Get embedding dimension
                _, dim = embed_many(self.embedding_model_id, ['test'], token=hf_token)
                
                # Process new chunks in batches
                batch_size = 20
                
                for i in range(0, len(new_chunks), batch_size):
                    if self.cancelled:
                        raise Exception('Indexing cancelled')
                    
                    while self.paused and not self.cancelled:
                        await asyncio.sleep(0.1)
                    
                    batch = new_chunks[i:i + batch_size]
                    chunk_texts = [chunk.get('preview', '') for chunk in batch]
                    
                    await self.notify_progress({
                        'phase': 'embedding',
                        'filesProcessed': i,
                        'totalFiles': len(new_chunks),
                    })
                    
                    try:
                        embeddings, _ = embed_many(self.embedding_model_id, chunk_texts, token=hf_token)
                        
                        for j, chunk in enumerate(batch):
                            if j < len(embeddings):
                                updated_vectors[chunk['chunkId']] = embeddings[j]
                    except Exception as e:
                        print(f"Failed to embed batch {i}-{i+len(batch)}: {e}")
                        continue
            
            if self.cancelled:
                raise Exception('Indexing cancelled')
            
            # Phase 4: Save updated index
            now = int(datetime.now().timestamp() * 1000)
            existing_manifest = existing_data.get('metadata', {}).get('manifest', {})
            
            manifest = {
                'projectId': self.project_id,
                'version': existing_manifest.get('version', 2),
                'createdAt': existing_manifest.get('createdAt', now),
                'updatedAt': now,
                'fileCount': len(updated_manifests),
                'symbolCount': len(updated_symbols),
                'chunkCount': len(updated_chunks),
                'embeddingModelId': self.embedding_model_id,
                'embeddingDim': existing_manifest.get('embeddingDim', 384),
            }
            
            index_data = {
                'metadata': {
                    'manifest': manifest,
                    'fileManifests': updated_manifests,
                    'indexedFolderIds': existing_data.get('metadata', {}).get('indexedFolderIds', []),
                    'indexedFolderNames': existing_data.get('metadata', {}).get('indexedFolderNames', {}),
                },
                'symbols': updated_symbols,
                'edges': updated_edges,
                'chunks': updated_chunks,
            }
            
            await self._save_index(index_data, updated_vectors)
            
            await self.notify_progress({
                'phase': 'complete',
                'filesProcessed': len(changed_files) + len(deleted_files),
                'totalFiles': len(changed_files) + len(deleted_files),
            })
            
            return {
                'success': True,
                'manifest': manifest,
            }
            
        except Exception as e:
            await self.notify_progress({
                'phase': 'error',
                'filesProcessed': 0,
                'totalFiles': 0,
                'error': str(e),
            })
            raise


# RPC Handlers

async def handle_index_build(
    payload: Dict[str, Any],
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """RPC handler for building an index."""
    project_id = payload.get('projectId', '')
    folders = payload.get('folders', [])
    show_hidden = payload.get('showHidden', False)
    embedding_model_id = payload.get('embeddingModelId', 'sentence-transformers/all-MiniLM-L6-v2')
    hf_token = payload.get('hfToken')
    
    if not project_id:
        return {'success': False, 'error': 'Project ID is required'}
    
    if not folders:
        return {'success': False, 'error': 'Folders are required'}
    
    # Cancel any existing builder for this project
    if project_id in _active_builders:
        _active_builders[project_id].cancel()
    
    builder = IndexBuilder(project_id, embedding_model_id)
    _active_builders[project_id] = builder
    
    if progress_callback:
        builder.add_progress_callback(progress_callback)
    
    try:
        result = await builder.build_index(folders, show_hidden, hf_token)
        return {'success': True, **result}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        if project_id in _active_builders:
            del _active_builders[project_id]


async def handle_index_folders(
    payload: Dict[str, Any],
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """RPC handler for incrementally indexing folders."""
    project_id = payload.get('projectId', '')
    folders = payload.get('folders', [])
    show_hidden = payload.get('showHidden', False)
    embedding_model_id = payload.get('embeddingModelId', 'sentence-transformers/all-MiniLM-L6-v2')
    hf_token = payload.get('hfToken')
    
    if not project_id:
        return {'success': False, 'error': 'Project ID is required'}
    
    if not folders:
        return {'success': False, 'error': 'Folders are required'}
    
    # Cancel any existing builder for this project
    if project_id in _active_builders:
        _active_builders[project_id].cancel()
    
    builder = IndexBuilder(project_id, embedding_model_id)
    _active_builders[project_id] = builder
    
    if progress_callback:
        builder.add_progress_callback(progress_callback)
    
    try:
        result = await builder.index_folders(folders, show_hidden, hf_token)
        return {'success': True, **result}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        if project_id in _active_builders:
            del _active_builders[project_id]


async def handle_index_cancel(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for cancelling indexing."""
    project_id = payload.get('projectId', '')
    
    if project_id in _active_builders:
        _active_builders[project_id].cancel()
        return {'success': True}
    
    return {'success': False, 'error': 'No active indexing for this project'}


async def handle_index_pause(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for pausing indexing."""
    project_id = payload.get('projectId', '')
    
    if project_id in _active_builders:
        _active_builders[project_id].pause()
        return {'success': True}
    
    return {'success': False, 'error': 'No active indexing for this project'}


async def handle_index_update_files(
    payload: Dict[str, Any],
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """RPC handler for incrementally updating index for changed/deleted files."""
    project_id = payload.get('projectId', '')
    changed_files = payload.get('changedFiles', [])
    deleted_files = payload.get('deletedFiles', [])
    embedding_model_id = payload.get('embeddingModelId', 'sentence-transformers/all-MiniLM-L6-v2')
    hf_token = payload.get('hfToken')
    
    if not project_id:
        return {'success': False, 'error': 'Project ID is required'}
    
    # Cancel any existing builder for this project
    if project_id in _active_builders:
        _active_builders[project_id].cancel()
    
    builder = IndexBuilder(project_id, embedding_model_id)
    _active_builders[project_id] = builder
    
    if progress_callback:
        builder.add_progress_callback(progress_callback)
    
    try:
        result = await builder.update_files(changed_files, deleted_files, hf_token)
        return {'success': True, **result}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        if project_id in _active_builders:
            del _active_builders[project_id]


async def handle_index_resume(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for resuming indexing."""
    project_id = payload.get('projectId', '')
    
    if project_id in _active_builders:
        _active_builders[project_id].resume()
        return {'success': True}
    
    return {'success': False, 'error': 'No active indexing for this project'}


async def handle_index_delete(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for deleting an index."""
    project_id = payload.get('projectId', '')
    
    if not project_id:
        return {'success': False, 'error': 'Project ID is required'}
    
    try:
        manager = get_project_manager()
        index_path = manager.get_index_path(project_id)
        
        # Delete all index files
        import shutil
        if index_path.exists():
            shutil.rmtree(index_path)
            index_path.mkdir(parents=True, exist_ok=True)
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


async def handle_index_stats(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting index statistics."""
    project_id = payload.get('projectId', '')
    
    if not project_id:
        return {'success': False, 'error': 'Project ID is required'}
    
    try:
        manager = get_project_manager()
        index_path = manager.get_index_path(project_id)
        metadata_path = index_path / 'metadata.json'
        
        if not metadata_path.exists():
            return {'success': True, 'hasIndex': False}
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        manifest = metadata.get('manifest', {})
        
        return {
            'success': True,
            'hasIndex': True,
            'fileCount': manifest.get('fileCount', 0),
            'symbolCount': manifest.get('symbolCount', 0),
            'chunkCount': manifest.get('chunkCount', 0),
            'embeddingModelId': manifest.get('embeddingModelId'),
            'embeddingDim': manifest.get('embeddingDim'),
            'updatedAt': manifest.get('updatedAt', 0),
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


async def handle_index_list_files(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for listing indexed files (for @-mention autocomplete)."""
    project_id = payload.get('projectId', '')
    
    if not project_id:
        return {'success': False, 'error': 'Project ID is required'}
    
    try:
        manager = get_project_manager()
        index_path = manager.get_index_path(project_id)
        metadata_path = index_path / 'metadata.json'
        
        if not metadata_path.exists():
            # No index yet - return empty list
            return {'success': True, 'files': []}
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        file_manifests = metadata.get('fileManifests', [])
        folder_name_to_id = metadata.get('indexedFolderNames', {})
        
        # Include files from all indexed folders (not just the first one)
        files = []
        
        for fm in file_manifests:
            file_path = fm.get('filePath', '')
            if not file_path:
                continue
            
            # Parse folder identifier and relative path
            parts = file_path.split('/', 1)
            if len(parts) < 2:
                continue
            
            folder_identifier = parts[0]
            relative_path = parts[1]
            
            # Resolve folder identifier to folder ID (handles both UUID and folder name formats)
            uuid_pattern = re.compile(r'^[\w-]{8}-[\w-]{4}-[\w-]{4}-[\w-]{4}-[\w-]{12}$')
            if uuid_pattern.match(folder_identifier):
                # Legacy format: folder identifier is already a folder ID
                folder_id = folder_identifier
            else:
                # New format: folder identifier is a folder name, resolve to ID
                folder_id = folder_name_to_id.get(folder_identifier, folder_identifier)
            
            # Extract filename
            name = relative_path.split('/')[-1] if '/' in relative_path else relative_path
            
            files.append({
                'folderId': folder_id,
                'relativePath': relative_path,
                'name': name,
            })
        
        return {'success': True, 'files': files}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


async def handle_retrieve_chunks(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for semantic retrieval."""
    project_id = payload.get('projectId', '')
    query = payload.get('query', '')
    limit = payload.get('limit', 10)
    folder_ids = payload.get('folderIds', [])
    embedding_model_id = payload.get('embeddingModelId', 'sentence-transformers/all-MiniLM-L6-v2')
    hf_token = payload.get('hfToken')
    
    if not project_id or not query:
        return {'success': False, 'error': 'Project ID and query are required'}
    
    try:
        manager = get_project_manager()
        index_path = manager.get_index_path(project_id)
        
        # Load index data
        metadata_path = index_path / 'metadata.json'
        chunks_path = index_path / 'chunks.json'
        vectors_binary_path = index_path / 'vectors.f32'
        vectors_index_path = index_path / 'vectors.index.json'
        
        if not all(p.exists() for p in [metadata_path, chunks_path, vectors_binary_path, vectors_index_path]):
            return {'success': False, 'error': 'Index not found'}
        
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        with open(vectors_index_path, 'r', encoding='utf-8') as f:
            vector_index = json.load(f)
        
        # Load metadata to get folder name -> ID mapping
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        folder_name_to_id = metadata.get('indexedFolderNames', {})
        
        # Filter chunks by folder scope
        if folder_ids:
            def matches_folder_scope(file_path: str) -> bool:
                """Check if file path matches folder scope, handling both UUID and folder name formats."""
                path_parts = file_path.split('/')
                if not path_parts:
                    return False
                
                first_part = path_parts[0]
                
                # Check if it's a UUID (legacy format: 8-4-4-4-12 hex digits)
                uuid_pattern = re.compile(r'^[\w-]{8}-[\w-]{4}-[\w-]{4}-[\w-]{4}-[\w-]{12}$')
                if uuid_pattern.match(first_part):
                    # Legacy format: first part is folder ID
                    return first_part in folder_ids
                else:
                    # New format: first part is folder name, resolve to ID
                    folder_id = folder_name_to_id.get(first_part)
                    return folder_id in folder_ids if folder_id else False
            
            chunks = [c for c in chunks if matches_folder_scope(c['filePath'])]
        
        # Load query embedding
        from embeddings import embed_one
        query_vector, dim = embed_one(embedding_model_id, query, token=hf_token)
        
        # Load vectors and compute similarities
        similarities = []
        
        with open(vectors_binary_path, 'rb') as f:
            for chunk in chunks:
                chunk_id = chunk['chunkId']
                if chunk_id not in vector_index:
                    continue
                
                entry = vector_index[chunk_id]
                offset = entry['offset']
                vec_dim = entry['dim']
                
                if vec_dim != dim:
                    continue
                
                # Read vector from binary file
                f.seek(offset)
                vector_bytes = f.read(vec_dim * 4)
                vector = struct.unpack(f'{vec_dim}f', vector_bytes)
                
                # Compute cosine similarity
                vec_np = np.array(vector, dtype=np.float32)
                query_np = np.array(query_vector, dtype=np.float32)
                
                dot_product = np.dot(vec_np, query_np)
                norm_product = np.linalg.norm(vec_np) * np.linalg.norm(query_np)
                
                if norm_product > 0:
                    similarity = dot_product / norm_product
                    similarities.append({
                        'chunkId': chunk_id,
                        'score': float(similarity),
                    })
        
        # Sort by similarity and get top results
        similarities.sort(key=lambda x: x['score'], reverse=True)
        top_similarities = similarities[:limit]
        
        # Map to chunks
        chunk_map = {c['chunkId']: c for c in chunks}
        results = []
        
        for item in top_similarities:
            chunk = chunk_map.get(item['chunkId'])
            if chunk:
                results.append({
                    'chunkId': chunk['chunkId'],
                    'filePath': chunk['filePath'],
                    'startLine': chunk['startLine'],
                    'endLine': chunk['endLine'],
                    'preview': chunk.get('preview', ''),
                    'relevanceScore': item['score'],
                    'matchType': 'semantic',
                    'matchedSymbols': chunk.get('symbolIds', []),
                })
        
        return {'success': True, 'results': results}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}
