"""
New Markdown-style parsers for MarkdownFlow.

Follows CommonMark parsing principles:
1. Block-level parsing (document structure)
2. Inline-level parsing (within blocks)

This replaces the complex token-based architecture with a simpler,
more maintainable approach that aligns with Markdown parsing conventions.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from .enums import BlockType
from .models import Block


class EscapeType(Enum):
    """Types of escape sequences."""
    NONE = "none"                    # No escaping
    FULL = "full"                    # Complete escape (literal text)
    PARTIAL = "partial"              # Partial escape (e.g., \%{{var}} -> %{{var}}, but var can be replaced)


@dataclass
class EscapeInfo:
    """Information about escape sequences in text."""
    escape_type: EscapeType
    original_text: str
    processed_text: str
    variable_positions: List[Tuple[int, int]] = None  # For partial escapes, positions where variables can still be replaced
    
    def __post_init__(self):
        if self.variable_positions is None:
            self.variable_positions = []


class MarkdownFlowEscapeProcessor:
    """
    Escape processor following Markdown conventions.
    
    Handles both full and partial escapes:
    - \--- -> --- (full escape)
    - \%{{var}} -> %{{var}} but var can still be replaced (partial escape)
    """
    
    # Escape patterns for different contexts
    DOCUMENT_ESCAPES = {
        r'\\---': ('---', EscapeType.FULL),
        r'\\===': ('===', EscapeType.FULL),
        r'\\\?\[': ('?[', EscapeType.FULL),
    }
    
    INLINE_ESCAPES = {
        r'\\\.\.\.': ('...', EscapeType.FULL),
        r'\\\|': ('|', EscapeType.FULL),
        r'\\//': ('//', EscapeType.FULL),
        r'\\{{([^}]+)}}': (r'{{\1}}', EscapeType.FULL),  # Full variable escape
    }
    
    # Partial escape patterns (special handling)
    PARTIAL_ESCAPES = {
        r'\\%{{([^}]+)}}': r'%{{\1}}',  # Partial escape: only escape the %
    }
    
    def process_document_escapes(self, text: str) -> EscapeInfo:
        """Process document-level escapes."""
        return self._process_escapes(text, self.DOCUMENT_ESCAPES, {})
    
    def process_inline_escapes(self, text: str) -> EscapeInfo:
        """Process inline-level escapes."""
        return self._process_escapes(text, self.INLINE_ESCAPES, self.PARTIAL_ESCAPES)
    
    def _process_escapes(self, text: str, full_escapes: Dict[str, Tuple[str, EscapeType]], 
                        partial_escapes: Dict[str, str]) -> EscapeInfo:
        """Process escape sequences in text."""
        processed_text = text
        has_escapes = False
        escape_type = EscapeType.NONE
        variable_positions = []
        
        # Process partial escapes first (higher priority)
        for pattern, replacement in partial_escapes.items():
            matches = list(re.finditer(pattern, processed_text))
            if matches:
                has_escapes = True
                escape_type = EscapeType.PARTIAL
                
                # Process matches in reverse order to maintain positions
                for match in reversed(matches):
                    # For partial escapes, track where variables can still be replaced
                    var_name = match.group(1) if match.groups() else None
                    replacement_text = re.sub(pattern, replacement, match.group(0))
                    
                    # Find variable position in replacement text
                    if var_name:
                        var_pattern = r'\{\{' + re.escape(var_name) + r'\}\}'
                        var_match = re.search(var_pattern, replacement_text)
                        if var_match:
                            # Calculate absolute position in the final processed text
                            abs_start = match.start() + var_match.start()
                            abs_end = match.start() + var_match.end()
                            variable_positions.append((abs_start, abs_end))
                    
                    # Replace in text
                    processed_text = processed_text[:match.start()] + replacement_text + processed_text[match.end():]
        
        # Process full escapes
        for pattern, (replacement, esc_type) in full_escapes.items():
            if re.search(pattern, processed_text):
                has_escapes = True
                if escape_type == EscapeType.NONE:
                    escape_type = esc_type
                processed_text = re.sub(pattern, replacement, processed_text)
        
        return EscapeInfo(
            escape_type=escape_type,
            original_text=text,
            processed_text=processed_text,
            variable_positions=variable_positions
        )


class MarkdownFlowBlockParser:
    """
    Block-level parser following Markdown conventions.
    
    Identifies document structure:
    - Block separators (---)
    - Preserved content (===)
    - Interaction blocks (?[...])
    - Regular content blocks
    """
    
    def __init__(self):
        self.escape_processor = MarkdownFlowEscapeProcessor()
    
    def parse_document(self, document: str) -> List[Block]:
        """
        Parse document into blocks using Markdown-style block parsing.
        
        Args:
            document: Raw document text
            
        Returns:
            List of Block objects
        """
        # First, process document-level escapes
        escape_info = self.escape_processor.process_document_escapes(document)
        processed_document = escape_info.processed_text
        
        # Split by block separators (similar to Markdown's approach)
        # Use negative lookbehind to avoid matching escaped separators
        block_separator_pattern = r'\n\s*---\s*\n'
        raw_blocks = re.split(block_separator_pattern, processed_document)
        
        blocks = []
        for i, raw_block in enumerate(raw_blocks):
            raw_block = raw_block.strip()
            if not raw_block:
                continue
                
            block = self._parse_single_block(raw_block, i)
            if block:
                blocks.append(block)
        
        # Update block indices
        for i, block in enumerate(blocks):
            block.index = i
            
        return blocks
    
    def _parse_single_block(self, content: str, tentative_index: int) -> Optional[Block]:
        """Parse a single block and determine its type."""
        content = content.strip()
        if not content:
            return None
        
        # Check for interaction blocks
        # Pattern: starts with ?[ and ends with ] (allowing for multiline)
        if self._is_interaction_block(content):
            return Block(
                content=content,
                block_type=BlockType.INTERACTION,
                index=tentative_index
            )
        
        # Check for preserved content blocks
        if self._is_preserved_content_block(content):
            return Block(
                content=content,
                block_type=BlockType.PRESERVED_CONTENT,
                index=tentative_index
            )
        
        # Default to regular content
        return Block(
            content=content,
            block_type=BlockType.CONTENT,
            index=tentative_index
        )
    
    def _is_interaction_block(self, content: str) -> bool:
        """Check if content is an interaction block."""
        # Remove leading/trailing whitespace
        stripped = content.strip()
        
        # Must start with ?[ and end with ]
        if not (stripped.startswith('?[') and stripped.endswith(']')):
            return False
        
        # Check for basic balance of brackets
        bracket_count = 0
        for char in stripped:
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                
        return bracket_count == 0
    
    def _is_preserved_content_block(self, content: str) -> bool:
        """
        Check if content is preserved content block.
        
        Two formats:
        1. Inline: ===content===
        2. Multiline: ===\ncontent\n===
        """
        lines = content.split('\n')
        
        # Check inline format first
        if len(lines) == 1:
            line = lines[0].strip()
            match = re.match(r'^===(.+)===$', line)
            if match and '=' not in match.group(1):
                return True
        
        # Check multiline format
        if len(lines) >= 3:
            first_line = lines[0].strip()
            last_line = lines[-1].strip()
            if first_line == '===' and last_line == '===':
                return True
        
        return False


class MarkdownFlowInlineParser:
    """
    Inline-level parser following Markdown conventions.
    
    Processes elements within blocks:
    - Variables ({{var}}, %{{var}})
    - Interaction elements (buttons, ellipsis, pipes)
    - Escape sequences
    """
    
    def __init__(self):
        self.escape_processor = MarkdownFlowEscapeProcessor()
    
    def parse_content_block(self, content: str) -> Dict[str, Any]:
        """Parse regular content block."""
        escape_info = self.escape_processor.process_inline_escapes(content)
        variables = self._extract_variables(escape_info.processed_text, escape_info)
        
        return {
            'processed_content': escape_info.processed_text,
            'variables': variables,
            'escape_info': escape_info
        }
    
    def parse_interaction_block(self, content: str) -> Dict[str, Any]:
        """Parse interaction block content."""
        # Extract content from ?[...] format
        if content.startswith('?[') and content.endswith(']'):
            inner_content = content[2:-1].strip()
        else:
            inner_content = content
        
        # Process escapes
        escape_info = self.escape_processor.process_inline_escapes(inner_content)
        processed_content = escape_info.processed_text
        
        # Parse interaction elements
        result = self._parse_interaction_content(processed_content)
        result['escape_info'] = escape_info
        result['original_content'] = content
        
        return result
    
    def parse_preserved_content_block(self, content: str) -> Dict[str, Any]:
        """Parse preserved content block."""
        # Extract actual content from === markers
        extracted_content = self._extract_preserved_content(content)
        
        # Process escapes in extracted content
        escape_info = self.escape_processor.process_inline_escapes(extracted_content)
        variables = self._extract_variables(escape_info.processed_text, escape_info)
        
        return {
            'processed_content': escape_info.processed_text,
            'extracted_content': extracted_content,
            'variables': variables,
            'escape_info': escape_info
        }
    
    def _extract_variables(self, text: str, escape_info: EscapeInfo) -> List[str]:
        """Extract variable names from text, considering escape information."""
        variables = set()
        
        # Extract %{{var}} format (preserved variables)
        percent_vars = re.findall(r'%\{\{([^}]+)\}\}', text)
        variables.update(var.strip() for var in percent_vars)
        
        # Extract {{var}} format (replaceable variables)
        # Skip positions that are fully escaped
        brace_pattern = r'(?<!%)\{\{([^}]+)\}\}'
        for match in re.finditer(brace_pattern, text):
            # Check if this position is in a fully escaped region
            if escape_info is None or escape_info.escape_type != EscapeType.FULL:
                variables.add(match.group(1).strip())
        
        return sorted(list(variables))
    
    def _parse_interaction_content(self, content: str) -> Dict[str, Any]:
        """Parse interaction content and determine type."""
        # Check for Markdown link format: text](url) and reject it
        if re.match(r'^[^]]+\]\([^)]+\)$', content.strip()):
            return {'error': 'Markdown link format not supported as interaction'}
        
        # Check for variable assignment pattern
        var_match = re.match(r'^%\{\{([^}]+)\}\}(.*)$', content.strip())
        
        if var_match:
            var_name = var_match.group(1).strip()
            remaining = var_match.group(2).strip()
            
            # Check for ellipsis (text input)
            if '...' in remaining:
                parts = remaining.split('...', 1)
                buttons_part = parts[0].strip()
                question = parts[1].strip() if len(parts) > 1 else ''
                
                if '|' in buttons_part and buttons_part:
                    return {
                        'type': 'buttons_with_text',
                        'variable': var_name,
                        'buttons': self._parse_buttons(buttons_part),
                        'question': question
                    }
                else:
                    return {
                        'type': 'text_only',
                        'variable': var_name,
                        'question': question
                    }
            else:
                # No ellipsis - button mode
                if '|' in remaining or remaining:
                    return {
                        'type': 'buttons_only',
                        'variable': var_name,
                        'buttons': self._parse_buttons(remaining) if remaining else []
                    }
                else:
                    return {
                        'type': 'text_only',
                        'variable': var_name,
                        'question': ''
                    }
        else:
            # No variable - display buttons
            return {
                'type': 'non_assignment_button',
                'buttons': self._parse_buttons(content) if content else [{'display': '', 'value': ''}]
            }
    
    def _parse_buttons(self, content: str) -> List[Dict[str, str]]:
        """Parse button content separated by |."""
        if not content:
            return []
        
        buttons = []
        for button_text in content.split('|'):
            button_text = button_text.strip()
            if button_text:
                # Handle display//value format
                if '//' in button_text:
                    parts = button_text.split('//', 1)
                    buttons.append({
                        'display': parts[0].strip(),
                        'value': parts[1].strip()
                    })
                else:
                    buttons.append({
                        'display': button_text,
                        'value': button_text
                    })
        
        return buttons
    
    def _extract_preserved_content(self, content: str) -> str:
        """Extract actual content from preserved content markers."""
        lines = content.split('\n')
        
        # Handle inline format: ===content===
        if len(lines) == 1:
            match = re.match(r'^===(.+)===$', lines[0].strip())
            if match:
                return match.group(1).strip()
        
        # Handle multiline format
        if len(lines) >= 3 and lines[0].strip() == '===' and lines[-1].strip() == '===':
            return '\n'.join(lines[1:-1])
        
        # If no markers found, return as-is
        return content


class MarkdownFlowVariableResolver:
    """
    Variable resolver with escape-aware replacement.
    
    Handles:
    - {{var}} -> replacement
    - %{{var}} -> preserved (no replacement)
    - Escaped variables -> respect escape rules
    """
    
    def resolve_variables(self, text: str, variables: Dict[str, str], 
                         escape_info: Optional[EscapeInfo] = None) -> str:
        """
        Resolve variables in text with escape awareness.
        
        Args:
            text: Text containing variables
            variables: Variable name to value mapping
            escape_info: Escape information from parsing
            
        Returns:
            Text with variables resolved
        """
        if not variables:
            variables = {}
        
        # Handle null/empty values
        safe_variables = {}
        for key, value in variables.items():
            safe_variables[key] = value if value is not None and value != "" else "UNKNOWN"
        
        result = text
        
        # Find all {{variable}} patterns (excluding %{{var}} format)
        pattern = r'(?<!%)\{\{([^}]+)\}\}'
        matches = list(re.finditer(pattern, result))
        
        # Process matches in reverse order to maintain positions
        for match in reversed(matches):
            var_name = match.group(1).strip()
            
            # Get replacement value
            if var_name not in safe_variables:
                safe_variables[var_name] = "UNKNOWN"
            
            replacement = safe_variables[var_name]
            
            # Check if this position should be replaced based on escape info
            should_replace = True
            
            if escape_info:
                if escape_info.escape_type == EscapeType.FULL:
                    # Full escape - no replacements
                    should_replace = False
                elif escape_info.escape_type == EscapeType.PARTIAL:
                    # For partial escapes, only replace if position is in variable_positions
                    should_replace = any(
                        start <= match.start() < end 
                        for start, end in escape_info.variable_positions
                    )
            
            if should_replace:
                # Replace the variable
                result = result[:match.start()] + replacement + result[match.end():]
        
        return result


class MarkdownFlowUnifiedParser:
    """
    Unified parser that combines block-level and inline-level parsing.
    
    This is the main entry point for the new parsing architecture.
    """
    
    def __init__(self):
        self.block_parser = MarkdownFlowBlockParser()
        self.inline_parser = MarkdownFlowInlineParser()
        self.variable_resolver = MarkdownFlowVariableResolver()
    
    def parse_document(self, document: str) -> Tuple[List[Block], List[str]]:
        """
        Parse complete document and return blocks and variables.
        
        Args:
            document: Raw document content
            
        Returns:
            Tuple of (blocks, variable_names)
        """
        # Parse blocks
        blocks = self.block_parser.parse_document(document)
        
        # Extract variables from all blocks
        all_variables = set()
        
        for block in blocks:
            if block.block_type == BlockType.CONTENT:
                inline_result = self.inline_parser.parse_content_block(block.content)
                all_variables.update(inline_result['variables'])
                
            elif block.block_type == BlockType.INTERACTION:
                inline_result = self.inline_parser.parse_interaction_block(block.content)
                if 'variable' in inline_result:
                    all_variables.add(inline_result['variable'])
                # Also check for variables in buttons/questions
                if 'question' in inline_result:
                    question_vars = self.inline_parser._extract_variables(
                        inline_result['question'], None
                    )
                    all_variables.update(question_vars)
                    
            elif block.block_type == BlockType.PRESERVED_CONTENT:
                inline_result = self.inline_parser.parse_preserved_content_block(block.content)
                all_variables.update(inline_result['variables'])
        
        return blocks, sorted(list(all_variables))
    
    def process_block_content(self, block: Block, variables: Dict[str, str] = None) -> str:
        """
        Process block content with variable resolution.
        
        Args:
            block: Block to process
            variables: Variables to resolve
            
        Returns:
            Processed content
        """
        if variables is None:
            variables = {}
            
        if block.block_type == BlockType.CONTENT:
            inline_result = self.inline_parser.parse_content_block(block.content)
            return self.variable_resolver.resolve_variables(
                inline_result['processed_content'],
                variables,
                inline_result['escape_info']
            )
            
        elif block.block_type == BlockType.PRESERVED_CONTENT:
            inline_result = self.inline_parser.parse_preserved_content_block(block.content)
            return self.variable_resolver.resolve_variables(
                inline_result['processed_content'],
                variables,
                inline_result['escape_info']
            )
            
        elif block.block_type == BlockType.INTERACTION:
            # For interaction blocks, we typically don't do variable resolution
            # at this level - it's handled in the interaction processing
            return block.content
        
        return block.content