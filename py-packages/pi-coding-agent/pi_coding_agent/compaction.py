"""
Context compaction for long sessions
"""
import math
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from .models import (
    AgentMessage, SessionEntry, CompactionEntry, SessionMessageEntry,
    ThinkingLevelChangeEntry, ModelChangeEntry, CompactionSummaryMessage,
    MessageType
)


class CompactionSettings:
    """Settings for compaction behavior."""
    
    def __init__(self, enabled: bool = True, reserve_tokens: int = 16384, 
                 keep_recent_tokens: int = 20000):
        self.enabled = enabled
        self.reserve_tokens = reserve_tokens
        self.keep_recent_tokens = keep_recent_tokens


class CompactionDetails:
    """Details stored in CompactionEntry for file tracking."""
    
    def __init__(self, read_files: List[str] = None, modified_files: List[str] = None):
        self.read_files = read_files or []
        self.modified_files = modified_files or []


class FileOperations:
    """Tracks file operations during compaction."""
    
    def __init__(self):
        self.read: set = set()
        self.edited: set = set()


class CompactionPreparation:
    """Preparation data for compaction."""
    
    def __init__(self, first_kept_entry_id: str, messages_to_summarize: List[AgentMessage],
                 turn_prefix_messages: List[AgentMessage], is_split_turn: bool,
                 tokens_before: int, previous_summary: Optional[str] = None,
                 file_ops: FileOperations = None, settings: CompactionSettings = None):
        self.first_kept_entry_id = first_kept_entry_id
        self.messages_to_summarize = messages_to_summarize
        self.turn_prefix_messages = turn_prefix_messages
        self.is_split_turn = is_split_turn
        self.tokens_before = tokens_before
        self.previous_summary = previous_summary
        self.file_ops = file_ops or FileOperations()
        self.settings = settings


class CompactionManager:
    """Manages context compaction for long sessions."""
    
    DEFAULT_SETTINGS = CompactionSettings()
    
    @staticmethod
    def estimate_tokens(message: AgentMessage) -> int:
        """Estimate token count for a message using chars/4 heuristic."""
        chars = 0
        
        if isinstance(message, dict):
            # Handle dictionary representation
            role = message.get('role', '')
            content = message.get('content', '')
        else:
            # Handle Pydantic model
            role = getattr(message, 'role', '')
            content = getattr(message, 'content', '')
        
        if role == MessageType.USER:
            if isinstance(content, str):
                chars = len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        chars += len(block.get('text', ''))
                    elif hasattr(block, 'type') and block.type == 'text':
                        chars += len(getattr(block, 'text', ''))
                        
        elif role == MessageType.ASSISTANT:
            # Handle assistant message content blocks
            if hasattr(message, 'content') and isinstance(message.content, list):
                for block in message.content:
                    if hasattr(block, 'type'):
                        if block.type == 'text':
                            chars += len(getattr(block, 'text', ''))
                        elif block.type == 'thinking':
                            chars += len(getattr(block, 'thinking', ''))
                        elif block.type == 'toolCall':
                            chars += len(getattr(block, 'name', '')) + len(str(getattr(block, 'arguments', {})))
                            
        elif role in [MessageType.CUSTOM, MessageType.TOOL_RESULT]:
            if isinstance(content, str):
                chars = len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get('type') == 'text':
                            chars += len(block.get('text', ''))
                        elif block.get('type') == 'image':
                            chars += 4800  # Estimate for images
                    elif hasattr(block, 'type'):
                        if block.type == 'text':
                            chars += len(getattr(block, 'text', ''))
                        elif block.type == 'image':
                            chars += 4800
                        
        elif role == MessageType.BASH_EXECUTION:
            command = getattr(message, 'command', '') if hasattr(message, 'command') else ''
            output = getattr(message, 'output', '') if hasattr(message, 'output') else ''
            chars = len(command) + len(output)
            
        elif role in [MessageType.BRANCH_SUMMARY, MessageType.COMPACTION_SUMMARY]:
            summary = getattr(message, 'summary', '') if hasattr(message, 'summary') else ''
            chars = len(summary)
        
        return math.ceil(chars / 4)
    
    @staticmethod
    def estimate_context_tokens(messages: List[AgentMessage]) -> Dict[str, int]:
        """Estimate context tokens from messages."""
        total_tokens = 0
        for message in messages:
            total_tokens += CompactionManager.estimate_tokens(message)
        return {
            'tokens': total_tokens,
            'usage_tokens': 0,
            'trailing_tokens': total_tokens,
            'last_usage_index': None
        }
    
    @staticmethod
    def should_compact(context_tokens: int, context_window: int, 
                      settings: CompactionSettings) -> bool:
        """Check if compaction should trigger."""
        if not settings.enabled:
            return False
        return context_tokens > context_window - settings.reserve_tokens
    
    @staticmethod
    def find_cut_point(entries: List[SessionEntry], start_index: int, 
                      end_index: int, keep_recent_tokens: int) -> Dict[str, Any]:
        """Find the cut point for compaction."""
        # Find valid cut points (user, assistant, custom, bashExecution messages)
        cut_points = []
        for i in range(start_index, end_index):
            entry = entries[i]
            if isinstance(entry, SessionMessageEntry):
                role = entry.message.role if hasattr(entry.message, 'role') else ''
                if role in [MessageType.USER, MessageType.ASSISTANT, MessageType.CUSTOM, 
                           MessageType.BASH_EXECUTION]:
                    cut_points.append(i)
            elif hasattr(entry, 'type') and entry.type in ['branch_summary', 'custom_message']:
                cut_points.append(i)
        
        if not cut_points:
            return {
                'first_kept_entry_index': start_index,
                'turn_start_index': -1,
                'is_split_turn': False
            }
        
        # Walk backwards accumulating tokens
        accumulated_tokens = 0
        cut_index = cut_points[0]
        
        for i in range(end_index - 1, start_index - 1, -1):
            entry = entries[i]
            if isinstance(entry, SessionMessageEntry):
                message_tokens = CompactionManager.estimate_tokens(entry.message)
                accumulated_tokens += message_tokens
                
                if accumulated_tokens >= keep_recent_tokens:
                    # Find closest valid cut point
                    for c in cut_points:
                        if c >= i:
                            cut_index = c
                            break
                    break
        
        # Scan backwards to include non-message entries
        while cut_index > start_index:
            prev_entry = entries[cut_index - 1]
            if isinstance(prev_entry, SessionMessageEntry):
                break
            if hasattr(prev_entry, 'type') and prev_entry.type == 'compaction':
                break
            cut_index -= 1
        
        # Determine if this is a split turn
        cut_entry = entries[cut_index]
        is_user_message = (isinstance(cut_entry, SessionMessageEntry) and 
                          getattr(cut_entry.message, 'role', '') == MessageType.USER)
        turn_start_index = -1 if is_user_message else CompactionManager._find_turn_start_index(
            entries, cut_index, start_index)
        
        return {
            'first_kept_entry_index': cut_index,
            'turn_start_index': turn_start_index,
            'is_split_turn': not is_user_message and turn_start_index != -1
        }
    
    @staticmethod
    def _find_turn_start_index(entries: List[SessionEntry], entry_index: int, 
                              start_index: int) -> int:
        """Find the user message that starts the turn."""
        for i in range(entry_index, start_index - 1, -1):
            entry = entries[i]
            if isinstance(entry, SessionMessageEntry):
                role = getattr(entry.message, 'role', '')
                if role in [MessageType.USER, MessageType.BASH_EXECUTION]:
                    return i
            elif hasattr(entry, 'type') and entry.type in ['branch_summary', 'custom_message']:
                return i
        return -1
    
    @staticmethod
    def prepare_compaction(entries: List[SessionEntry], 
                          settings: CompactionSettings) -> Optional[CompactionPreparation]:
        """Prepare data for compaction."""
        # Check if last entry is already a compaction
        if entries and hasattr(entries[-1], 'type') and entries[-1].type == 'compaction':
            return None
        
        # Find previous compaction
        prev_compaction_index = -1
        for i in range(len(entries) - 1, -1, -1):
            if hasattr(entries[i], 'type') and entries[i].type == 'compaction':
                prev_compaction_index = i
                break
        
        boundary_start = prev_compaction_index + 1
        boundary_end = len(entries)
        
        # Calculate tokens before compaction
        usage_start = prev_compaction_index if prev_compaction_index >= 0 else 0
        usage_messages = []
        
        for i in range(usage_start, boundary_end):
            entry = entries[i]
            if isinstance(entry, SessionMessageEntry):
                usage_messages.append(entry.message)
        
        tokens_before = CompactionManager.estimate_context_tokens(usage_messages)['tokens']
        
        # Find cut point
        cut_point = CompactionManager.find_cut_point(
            entries, boundary_start, boundary_end, settings.keep_recent_tokens
        )
        
        # Get first kept entry ID
        first_kept_entry = entries[cut_point['first_kept_entry_index']]
        if not hasattr(first_kept_entry, 'id'):
            return None
        first_kept_entry_id = first_kept_entry.id
        
        # Determine message ranges
        history_end = (cut_point['turn_start_index'] 
                      if cut_point['is_split_turn'] 
                      else cut_point['first_kept_entry_index'])
        
        # Messages to summarize
        messages_to_summarize = []
        for i in range(boundary_start, history_end):
            entry = entries[i]
            if isinstance(entry, SessionMessageEntry):
                messages_to_summarize.append(entry.message)
        
        # Turn prefix messages (if splitting)
        turn_prefix_messages = []
        if cut_point['is_split_turn']:
            for i in range(cut_point['turn_start_index'], cut_point['first_kept_entry_index']):
                entry = entries[i]
                if isinstance(entry, SessionMessageEntry):
                    turn_prefix_messages.append(entry.message)
        
        # Get previous summary
        previous_summary = None
        if prev_compaction_index >= 0:
            prev_compaction = entries[prev_compaction_index]
            if isinstance(prev_compaction, CompactionEntry):
                previous_summary = prev_compaction.summary
        
        # Extract file operations
        file_ops = CompactionManager._extract_file_operations(
            messages_to_summarize, entries, prev_compaction_index
        )
        
        if cut_point['is_split_turn']:
            for msg in turn_prefix_messages:
                CompactionManager._extract_file_ops_from_message(msg, file_ops)
        
        return CompactionPreparation(
            first_kept_entry_id=first_kept_entry_id,
            messages_to_summarize=messages_to_summarize,
            turn_prefix_messages=turn_prefix_messages,
            is_split_turn=cut_point['is_split_turn'],
            tokens_before=tokens_before,
            previous_summary=previous_summary,
            file_ops=file_ops,
            settings=settings
        )
    
    @staticmethod
    def _extract_file_operations(messages: List[AgentMessage], entries: List[SessionEntry],
                                prev_compaction_index: int) -> FileOperations:
        """Extract file operations from messages and previous compaction."""
        file_ops = FileOperations()
        
        # Collect from previous compaction
        if prev_compaction_index >= 0:
            prev_compaction = entries[prev_compaction_index]
            if (isinstance(prev_compaction, CompactionEntry) and 
                not getattr(prev_compaction, 'from_hook', False) and 
                hasattr(prev_compaction, 'details') and prev_compaction.details):
                
                details = prev_compaction.details
                if isinstance(details, dict):
                    read_files = details.get('readFiles', [])
                    modified_files = details.get('modifiedFiles', [])
                    if isinstance(read_files, list):
                        file_ops.read.update(read_files)
                    if isinstance(modified_files, list):
                        file_ops.edited.update(modified_files)
        
        # Extract from tool calls in messages
        for msg in messages:
            CompactionManager._extract_file_ops_from_message(msg, file_ops)
        
        return file_ops
    
    @staticmethod
    def _extract_file_ops_from_message(message: AgentMessage, file_ops: FileOperations) -> None:
        """Extract file operations from a single message."""
        # This would need to be implemented based on the specific tool call formats
        # For now, this is a placeholder
        pass
    
    @staticmethod
    def compute_file_lists(file_ops: FileOperations) -> Tuple[List[str], List[str]]:
        """Compute sorted file lists from file operations."""
        read_files = sorted(list(file_ops.read))
        modified_files = sorted(list(file_ops.edited))
        return read_files, modified_files
    
    @staticmethod
    def format_file_operations(read_files: List[str], modified_files: List[str]) -> str:
        """Format file operations for summary."""
        result = ""
        if read_files:
            result += "\n\n<read-files>\n" + "\n".join(read_files) + "\n</read-files>"
        if modified_files:
            result += "\n\n<modified-files>\n" + "\n".join(modified_files) + "\n</modified-files>"
        return result