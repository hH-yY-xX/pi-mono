"""
Session management for conversation trees with branching and persistence
"""
import json
import os
from typing import List, Optional, Dict, Set, Union
from pathlib import Path
from datetime import datetime
from .models import (
    SessionHeader, SessionEntry, SessionContext, SessionMessageEntry,
    ThinkingLevelChangeEntry, ModelChangeEntry, CompactionEntry,
    BranchSummaryEntry, CustomEntry, LabelEntry, SessionInfoEntry,
    CustomMessageEntry, AgentMessage, ThinkingLevel, MessageType,
    UserMessage, AssistantMessage, ToolResultMessage, BashExecutionMessage,
    CustomMessage, BranchSummaryMessage, CompactionSummaryMessage
)


class SessionManager:
    """Manages conversation sessions as append-only trees stored in JSONL files."""
    
    CURRENT_VERSION = 3
    
    def __init__(self, cwd: str, session_dir: str = None, session_file: str = None, persist: bool = True):
        self.cwd = cwd
        self.session_dir = session_dir or self._get_default_session_dir(cwd)
        self.persist = persist
        self.flushed = False
        self.file_entries: List[Union[SessionHeader, SessionEntry]] = []
        self.by_id: Dict[str, SessionEntry] = {}
        self.labels_by_id: Dict[str, str] = {}
        self.leaf_id: Optional[str] = None
        
        if persist and self.session_dir and not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir, exist_ok=True)
            
        if session_file:
            self.set_session_file(session_file)
        else:
            self.new_session()
    
    @staticmethod
    def _get_default_session_dir(cwd: str) -> str:
        """Compute default session directory for a working directory."""
        safe_path = f"--{cwd.lstrip('/').replace('/', '-').replace(':', '-')}"
        session_dir = os.path.join(os.path.expanduser("~/.pi/agent/sessions"), safe_path)
        os.makedirs(session_dir, exist_ok=True)
        return session_dir
    
    def set_session_file(self, session_file: str) -> None:
        """Switch to a different session file."""
        self.session_file = os.path.abspath(session_file)
        if os.path.exists(self.session_file):
            self._load_entries_from_file()
            if not self.file_entries:
                # Empty or corrupted file
                explicit_path = self.session_file
                self.new_session()
                self.session_file = explicit_path
                self._rewrite_file()
                self.flushed = True
                return
                
            # Extract session ID from header
            header = next((e for e in self.file_entries if isinstance(e, SessionHeader)), None)
            self.session_id = header.id if header else str(uuid.uuid4())
            
            # Handle migrations if needed
            if self._migrate_to_current_version():
                self._rewrite_file()
                
            self._build_index()
            self.flushed = True
        else:
            explicit_path = self.session_file
            self.new_session()
            self.session_file = explicit_path
    
    def new_session(self, parent_session: str = None) -> Optional[str]:
        """Create a new session."""
        import uuid
        self.session_id = str(uuid.uuid4())
        header = SessionHeader(
            version=self.CURRENT_VERSION,
            cwd=self.cwd,
            parent_session=parent_session
        )
        self.file_entries = [header]
        self.by_id.clear()
        self.labels_by_id.clear()
        self.leaf_id = None
        self.flushed = False
        
        if self.persist:
            timestamp = header.timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]
            self.session_file = os.path.join(self.session_dir, f"{timestamp}_{self.session_id}.jsonl")
        
        return self.session_file if self.persist else None
    
    def _build_index(self) -> None:
        """Build internal indexes from file entries."""
        self.by_id.clear()
        self.labels_by_id.clear()
        self.leaf_id = None
        
        for entry in self.file_entries:
            if isinstance(entry, SessionHeader):
                continue
            self.by_id[entry.id] = entry
            self.leaf_id = entry.id
            if isinstance(entry, LabelEntry) and entry.label:
                self.labels_by_id[entry.target_id] = entry.label
    
    def _rewrite_file(self) -> None:
        """Rewrite the entire session file."""
        if not self.persist or not self.session_file:
            return
            
        with open(self.session_file, 'w') as f:
            for entry in self.file_entries:
                f.write(json.dumps(entry.model_dump(mode='json')) + '\n')
    
    def _persist(self, entry: SessionEntry) -> None:
        """Persist an entry to file."""
        if not self.persist or not self.session_file:
            return
            
        # Delay writing until first assistant message
        has_assistant = any(
            isinstance(e, SessionMessageEntry) and 
            isinstance(e.message, AssistantMessage) 
            for e in self.file_entries
        )
        
        if not has_assistant:
            self.flushed = False
            return
            
        if not self.flushed:
            with open(self.session_file, 'w') as f:
                for e in self.file_entries:
                    f.write(json.dumps(e.model_dump(mode='json')) + '\n')
            self.flushed = True
        else:
            with open(self.session_file, 'a') as f:
                f.write(json.dumps(entry.model_dump(mode='json')) + '\n')
    
    def _append_entry(self, entry: SessionEntry) -> None:
        """Append an entry and update internal state."""
        self.file_entries.append(entry)
        self.by_id[entry.id] = entry
        self.leaf_id = entry.id
        self._persist(entry)
    
    def append_message(self, message: AgentMessage) -> str:
        """Append a message entry."""
        entry = SessionMessageEntry(
            parent_id=self.leaf_id,
            message=message
        )
        self._append_entry(entry)
        return entry.id
    
    def append_thinking_level_change(self, thinking_level: ThinkingLevel) -> str:
        """Append a thinking level change entry."""
        entry = ThinkingLevelChangeEntry(
            parent_id=self.leaf_id,
            thinking_level=thinking_level
        )
        self._append_entry(entry)
        return entry.id
    
    def append_model_change(self, provider: str, model_id: str) -> str:
        """Append a model change entry."""
        entry = ModelChangeEntry(
            parent_id=self.leaf_id,
            provider=provider,
            model_id=model_id
        )
        self._append_entry(entry)
        return entry.id
    
    def append_compaction(self, summary: str, first_kept_entry_id: str, 
                         tokens_before: int, details: dict = None, 
                         from_hook: bool = None) -> str:
        """Append a compaction entry."""
        entry = CompactionEntry(
            parent_id=self.leaf_id,
            summary=summary,
            first_kept_entry_id=first_kept_entry_id,
            tokens_before=tokens_before,
            details=details,
            from_hook=from_hook
        )
        self._append_entry(entry)
        return entry.id
    
    def append_custom_entry(self, custom_type: str, data=None) -> str:
        """Append a custom entry for extensions."""
        entry = CustomEntry(
            parent_id=self.leaf_id,
            custom_type=custom_type,
            data=data
        )
        self._append_entry(entry)
        return entry.id
    
    def append_session_info(self, name: str) -> str:
        """Append session info entry."""
        entry = SessionInfoEntry(
            parent_id=self.leaf_id,
            name=name.strip()
        )
        self._append_entry(entry)
        return entry.id
    
    def get_session_name(self) -> Optional[str]:
        """Get the current session name."""
        for entry in reversed(self.get_entries()):
            if isinstance(entry, SessionInfoEntry) and entry.name:
                return entry.name
        return None
    
    def append_label_change(self, target_id: str, label: Optional[str]) -> str:
        """Set or clear a label on an entry."""
        if target_id not in self.by_id:
            raise ValueError(f"Entry {target_id} not found")
            
        entry = LabelEntry(
            parent_id=self.leaf_id,
            target_id=target_id,
            label=label
        )
        self._append_entry(entry)
        
        if label:
            self.labels_by_id[target_id] = label
        else:
            self.labels_by_id.pop(target_id, None)
            
        return entry.id
    
    def get_leaf_id(self) -> Optional[str]:
        """Get current leaf ID."""
        return self.leaf_id
    
    def get_leaf_entry(self) -> Optional[SessionEntry]:
        """Get current leaf entry."""
        return self.by_id.get(self.leaf_id) if self.leaf_id else None
    
    def get_entry(self, entry_id: str) -> Optional[SessionEntry]:
        """Get entry by ID."""
        return self.by_id.get(entry_id)
    
    def get_children(self, parent_id: str) -> List[SessionEntry]:
        """Get all direct children of an entry."""
        return [entry for entry in self.by_id.values() if entry.parent_id == parent_id]
    
    def get_label(self, entry_id: str) -> Optional[str]:
        """Get label for an entry."""
        return self.labels_by_id.get(entry_id)
    
    def get_branch(self, from_id: str = None) -> List[SessionEntry]:
        """Walk from entry to root, returning path."""
        path = []
        start_id = from_id or self.leaf_id
        current = self.by_id.get(start_id) if start_id else None
        
        while current:
            path.insert(0, current)
            current = self.by_id.get(current.parent_id) if current.parent_id else None
            
        return path
    
    def build_session_context(self) -> SessionContext:
        """Build session context for LLM."""
        return self._build_session_context(self.get_entries(), self.leaf_id, self.by_id)
    
    def get_header(self) -> Optional[SessionHeader]:
        """Get session header."""
        return next((e for e in self.file_entries if isinstance(e, SessionHeader)), None)
    
    def get_entries(self) -> List[SessionEntry]:
        """Get all session entries (excluding header)."""
        return [e for e in self.file_entries if not isinstance(e, SessionHeader)]
    
    def branch(self, branch_from_id: str) -> None:
        """Start a new branch from an earlier entry."""
        if branch_from_id not in self.by_id:
            raise ValueError(f"Entry {branch_from_id} not found")
        self.leaf_id = branch_from_id
    
    def reset_leaf(self) -> None:
        """Reset leaf pointer to null."""
        self.leaf_id = None
    
    def branch_with_summary(self, branch_from_id: Optional[str], summary: str, 
                           details: dict = None, from_hook: bool = None) -> str:
        """Start a new branch with summary."""
        if branch_from_id and branch_from_id not in self.by_id:
            raise ValueError(f"Entry {branch_from_id} not found")
            
        self.leaf_id = branch_from_id
        entry = BranchSummaryEntry(
            parent_id=branch_from_id,
            from_id=branch_from_id or "root",
            summary=summary,
            details=details,
            from_hook=from_hook
        )
        self._append_entry(entry)
        return entry.id
    
    @classmethod
    def create(cls, cwd: str, session_dir: str = None) -> 'SessionManager':
        """Create a new session."""
        return cls(cwd, session_dir)
    
    @classmethod
    def open(cls, path: str, session_dir: str = None) -> 'SessionManager':
        """Open an existing session file."""
        # Extract cwd from session header
        entries = cls._load_entries_from_file_static(path)
        header = next((e for e in entries if isinstance(e, SessionHeader)), None)
        cwd = header.cwd if header else os.getcwd()
        dir_path = session_dir or os.path.dirname(os.path.abspath(path))
        return cls(cwd, dir_path, path)
    
    @classmethod
    def continue_recent(cls, cwd: str, session_dir: str = None) -> 'SessionManager':
        """Continue the most recent session."""
        dir_path = session_dir or cls._get_default_session_dir(cwd)
        most_recent = cls._find_most_recent_session(dir_path)
        if most_recent:
            return cls(cwd, dir_path, most_recent)
        return cls(cwd, dir_path)
    
    @classmethod
    def in_memory(cls, cwd: str = None) -> 'SessionManager':
        """Create an in-memory session."""
        return cls(cwd or os.getcwd(), persist=False)
    
    # Helper methods (would need implementation)
    def _load_entries_from_file(self) -> None:
        """Load entries from session file."""
        if not os.path.exists(self.session_file):
            self.file_entries = []
            return
            
        self.file_entries = self._load_entries_from_file_static(self.session_file)
    
    @staticmethod
    def _load_entries_from_file_static(file_path: str) -> List[Union[SessionHeader, SessionEntry]]:
        """Static method to load entries from file."""
        entries = []
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        # Would need to deserialize to proper types
                        entries.append(data)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return entries
    
    @staticmethod
    def _find_most_recent_session(session_dir: str) -> Optional[str]:
        """Find the most recent session file."""
        if not os.path.exists(session_dir):
            return None
            
        try:
            files = [f for f in os.listdir(session_dir) if f.endswith('.jsonl')]
            if not files:
                return None
                
            file_paths = [os.path.join(session_dir, f) for f in files]
            # Would need to check file validity and sort by modification time
            return max(file_paths, key=os.path.getmtime)
        except OSError:
            return None
    
    def _migrate_to_current_version(self) -> bool:
        """Migrate session to current version if needed."""
        # Simplified migration logic
        header = self.get_header()
        if not header or header.version >= self.CURRENT_VERSION:
            return False
        # Migration would happen here
        return True
    
    def _build_session_context(self, entries: List[SessionEntry], 
                              leaf_id: Optional[str], 
                              by_id: Dict[str, SessionEntry]) -> SessionContext:
        """Build session context from entries."""
        # Simplified implementation - would need full logic from original
        messages = []
        thinking_level = ThinkingLevel.OFF
        model = None
        
        # Extract path from leaf to root
        path = []
        current_id = leaf_id
        while current_id and current_id in by_id:
            entry = by_id[current_id]
            path.insert(0, entry)
            current_id = entry.parent_id
        
        # Process entries to build context
        compaction = None
        for entry in path:
            if isinstance(entry, ThinkingLevelChangeEntry):
                thinking_level = entry.thinking_level
            elif isinstance(entry, ModelChangeEntry):
                model = {"provider": entry.provider, "model_id": entry.model_id}
            elif isinstance(entry, SessionMessageEntry):
                messages.append(entry.message)
                if isinstance(entry.message, AssistantMessage):
                    model = {"provider": entry.message.provider, "model_id": entry.message.model}
            elif isinstance(entry, CompactionEntry):
                compaction = entry
        
        return SessionContext(
            messages=messages,
            thinking_level=thinking_level,
            model=model
        )