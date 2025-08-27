"""
Markdown-Flow Utility Functions

Collection of utility functions for document parsing, variable extraction, and text processing.
"""

import json
import re
from enum import Enum
from typing import Any

from .constants import (
    COMPILED_BRACE_VARIABLE_REGEX,
    COMPILED_INTERACTION_REGEX,
    COMPILED_LAYER1_INTERACTION_REGEX,
    COMPILED_LAYER2_VARIABLE_REGEX,
    COMPILED_LAYER3_BUTTON_VALUE_REGEX,
    COMPILED_LAYER3_ELLIPSIS_REGEX,
    COMPILED_PERCENT_VARIABLE_REGEX,
    CONTEXT_CONVERSATION_TEMPLATE,
    CONTEXT_QUESTION_MARKER,
    CONTEXT_QUESTION_TEMPLATE,
    JSON_PARSE_ERROR,
    OUTPUT_INSTRUCTION_EXPLANATION,
    OUTPUT_INSTRUCTION_PREFIX,
    OUTPUT_INSTRUCTION_SUFFIX,
    SMART_VALIDATION_TEMPLATE,
    TRIPLE_EQUALS_DELIMITER,
    VALIDATION_ILLEGAL_DEFAULT_REASON,
    VALIDATION_RESPONSE_ILLEGAL,
    VALIDATION_RESPONSE_OK,
    VARIABLE_DEFAULT_VALUE,
)


def extract_variables_from_text(text: str) -> list[str]:
    """
    Extract all variable names from text.

    Recognizes two variable formats:
    - %{{variable_name}} format (preserved variables)
    - {{variable_name}} format (replaceable variables)

    Args:
        text: Text content to analyze

    Returns:
        Sorted list of unique variable names
    """
    variables = set()

    # Match %{{...}} format variables using pre-compiled regex
    matches = COMPILED_PERCENT_VARIABLE_REGEX.findall(text)
    for match in matches:
        variables.add(match.strip())

    # Match {{...}} format variables (excluding %) using pre-compiled regex
    matches = COMPILED_BRACE_VARIABLE_REGEX.findall(text)
    for match in matches:
        variables.add(match.strip())

    return sorted(list(variables))




def extract_interaction_question(content: str) -> str | None:
    """
    Extract question text from interaction block content.

    Args:
        content: Raw interaction block content

    Returns:
        Question text if found, None otherwise
    """
    # Match interaction format: ?[...] using pre-compiled regex
    match = COMPILED_INTERACTION_REGEX.match(content.strip())
    if not match:
        return None  # type: ignore[unreachable]

    # Extract interaction content (remove ?[ and ])
    interaction_content = match.group(1) if match.groups() else match.group(0)[2:-1]

    # Find ... separator, question text follows
    if "..." in interaction_content:
        # Split and get question part
        parts = interaction_content.split("...", 1)
        if len(parts) > 1:
            return parts[1].strip()

    return None  # type: ignore[unreachable]


class InteractionType(Enum):
    """Interaction input type enumeration."""

    TEXT_ONLY = "text_only"  # Text input only: ?[%{{var}}...question]
    BUTTONS_ONLY = "buttons_only"  # Button selection only: ?[%{{var}} A|B]
    BUTTONS_WITH_TEXT = "buttons_with_text"  # Buttons + text: ?[%{{var}} A|B|...question]
    NON_ASSIGNMENT_BUTTON = "non_assignment_button"  # Display buttons: ?[Continue|Cancel]


class InteractionParser:
    """
    Three-layer interaction parser for ?[] format validation,
    variable detection, and content parsing with escape support.
    """

    def __init__(self):
        """Initialize parser."""
        from .parsers import MarkdownFlowInlineParser
        self.inline_parser = MarkdownFlowInlineParser()

    def parse(self, content: str) -> dict[str, Any]:
        """
        Main parsing method with escape handling.

        Args:
            content: Raw interaction block content

        Returns:
            Standardized parsing result with type, variable, buttons, and question fields
        """
        try:
            # Check for obviously invalid formats before processing
            # but allow Markdown links to be handled by specific detection logic
            if self._is_obviously_invalid_format(content) and not self._is_markdown_link_format(content):
                return {"error": f"Invalid interaction format: {content}"}
            
            # Extract inner content if input has ?[] wrapper
            inner_content = self._extract_inner_content(content)
            
            # Use new inline parser for escape-aware parsing
            result = self.inline_parser.parse_interaction_block(f"?[{inner_content}]")
            
            if 'error' in result:
                # Check if this is a Markdown link format that should be rejected
                if self._is_markdown_link_format(content):
                    return {"error": "Markdown link format not supported as interaction"}
                return self._create_error_result(result['error'])
            elif 'type' in result:
                # Convert type to enum for compatibility
                type_mapping = {
                    'text_only': InteractionType.TEXT_ONLY,
                    'buttons_only': InteractionType.BUTTONS_ONLY,
                    'buttons_with_text': InteractionType.BUTTONS_WITH_TEXT,
                    'non_assignment_button': InteractionType.NON_ASSIGNMENT_BUTTON
                }
                
                interaction_type = type_mapping.get(result['type'])
                
                return {
                    "type": interaction_type,
                    "variable": result.get('variable'),
                    "buttons": result.get('buttons', []),
                    "question": result.get('question')
                }
            else:
                # Check if this is a Markdown link format that should be rejected
                if self._is_markdown_link_format(content):
                    return {"error": "Markdown link format not supported as interaction"}
                return self._create_error_result("Parse failed")

        except Exception:
            # Check if this is a Markdown link format that should be rejected
            if self._is_markdown_link_format(content):
                return {"error": "Markdown link format not supported as interaction"}
            # Fallback to old parsing method if token parser fails
            return self._parse_legacy(content)
    
    def _extract_inner_content(self, content: str) -> str:
        """Extract content from ?[...] format."""
        content = content.strip()
        
        # Check if content starts with ?[ and ends with ]
        if content.startswith('?[') and content.endswith(']') and len(content) > 2:
            return content[2:-1]  # Remove ?[ and ]
        
        return content
    
    def _is_obviously_invalid_format(self, content: str) -> bool:
        """
        Check for obviously invalid interaction formats that should be rejected early.
        
        Args:
            content: Raw input content
            
        Returns:
            True if the format is obviously invalid
        """
        stripped = content.strip()
        
        # Empty string
        if not stripped:
            return True
            
        # Just punctuation marks that can't be valid interactions
        # Note: '?[]' is valid (empty interaction), so we exclude it
        if stripped in ['?', '?[', '?]', '[', ']']:
            return True
            
        # Incomplete ?[content without closing bracket  
        if stripped.startswith('?[') and not stripped.endswith(']'):
            return True
            
        # Wrong bracket combinations
        if stripped.startswith('?]') or stripped.endswith('[?'):
            return True
        
        # Escaped interaction syntax - these should be handled at document level, not interaction level
        if stripped.startswith('\\?[') and stripped.endswith(']'):
            return True
            
        return False
    
    def _is_markdown_link_format(self, content: str) -> bool:
        """
        Check if content matches Markdown link format ?[text](url).
        
        Args:
            content: Content to check
            
        Returns:
            True if it's a Markdown link format
        """
        import re
        # Check for ?[text](url) pattern
        markdown_link_pattern = r'^\?\[[^\]]+\]\([^)]+\)$'
        return bool(re.match(markdown_link_pattern, content.strip()))
            
    def _parse_legacy(self, content: str) -> dict[str, Any]:
        """Legacy parsing method for fallback."""
        try:
            # Layer 1: Validate basic format
            inner_content = self._layer1_validate_format(content)
            if inner_content is None:
                return self._create_error_result(f"Invalid interaction format: {content}")

            # Layer 2: Variable detection and pattern classification
            has_variable, variable_name, remaining_content = self._layer2_detect_variable(inner_content)

            # Layer 3: Specific content parsing
            if has_variable:
                return self._layer3_parse_variable_interaction(variable_name, remaining_content)
            return self._layer3_parse_display_buttons(inner_content)

        except Exception as e:
            return self._create_error_result(f"Parsing error: {str(e)}")

    def _layer1_validate_format(self, content: str) -> str | None:
        """
        Layer 1: Validate ?[] format and extract content.

        Args:
            content: Raw content

        Returns:
            Extracted bracket content, None if validation fails
        """
        content = content.strip()
        match = COMPILED_LAYER1_INTERACTION_REGEX.search(content)

        if not match:
            return None  # type: ignore[unreachable]

        # Ensure matched content is complete (no other text)
        matched_text = match.group(0)
        if matched_text.strip() != content:
            return None

        return match.group(1)

    def _layer2_detect_variable(self, inner_content: str) -> tuple[bool, str | None, str]:
        """
        Layer 2: Detect variables and classify patterns.

        Args:
            inner_content: Content extracted from layer 1

        Returns:
            Tuple of (has_variable, variable_name, remaining_content)
        """
        match = COMPILED_LAYER2_VARIABLE_REGEX.match(inner_content)

        if not match:
            # No variable, use entire content for display button parsing
            return False, None, inner_content  # type: ignore[unreachable]

        variable_name = match.group(1).strip()
        remaining_content = match.group(2).strip()

        return True, variable_name, remaining_content

    def _layer3_parse_variable_interaction(self, variable_name: str, content: str) -> dict[str, Any]:
        """
        Layer 3: Parse variable interactions (variable assignment type).

        Args:
            variable_name: Variable name
            content: Content after variable

        Returns:
            Parsing result dictionary
        """
        # Detect ... separator
        ellipsis_match = COMPILED_LAYER3_ELLIPSIS_REGEX.match(content)

        if ellipsis_match:
            # Has ... separator
            before_ellipsis = ellipsis_match.group(1).strip()
            question = ellipsis_match.group(2).strip()

            if "|" in before_ellipsis and before_ellipsis:
                # Button group + text input
                buttons = self._parse_buttons(before_ellipsis)
                return {
                    "type": InteractionType.BUTTONS_WITH_TEXT,
                    "variable": variable_name,
                    "buttons": buttons,
                    "question": question,
                }
            # Pure text input or single button + text
            if before_ellipsis:
                # Has prefix buttons
                buttons = self._parse_buttons(before_ellipsis)
                return {
                    "type": InteractionType.BUTTONS_WITH_TEXT,
                    "variable": variable_name,
                    "buttons": buttons,
                    "question": question,
                }
            # Pure text input
            return {
                "type": InteractionType.TEXT_ONLY,
                "variable": variable_name,
                "question": question,
            }
        # No ... separator
        if "|" in content and content:  # type: ignore[unreachable]
            # Pure button group
            buttons = self._parse_buttons(content)
            return {
                "type": InteractionType.BUTTONS_ONLY,
                "variable": variable_name,
                "buttons": buttons,
            }
        if content:  # type: ignore[unreachable]
            # Single button
            button = self._parse_single_button(content)
            return {
                "type": InteractionType.BUTTONS_ONLY,
                "variable": variable_name,
                "buttons": [button],
            }
        # Pure text input (no hint)
        return {
            "type": InteractionType.TEXT_ONLY,
            "variable": variable_name,
            "question": "",
        }

    def _layer3_parse_display_buttons(self, content: str) -> dict[str, Any]:
        """
        Layer 3: Parse display buttons (non-variable assignment type).

        Args:
            content: Content to parse

        Returns:
            Parsing result dictionary
        """
        if not content:
            # Empty content: ?[]
            return {
                "type": InteractionType.NON_ASSIGNMENT_BUTTON,
                "buttons": [{"display": "", "value": ""}],
            }

        if "|" in content:
            # Multiple buttons
            buttons = self._parse_buttons(content)
            return {"type": InteractionType.NON_ASSIGNMENT_BUTTON, "buttons": buttons}
        # Single button
        button = self._parse_single_button(content)
        return {"type": InteractionType.NON_ASSIGNMENT_BUTTON, "buttons": [button]}

    def _parse_buttons(self, content: str) -> list[dict[str, str]]:
        """
        Parse button group.

        Args:
            content: Button content separated by |

        Returns:
            List of button dictionaries
        """
        buttons = []
        for button_text in content.split("|"):
            button_text = button_text.strip()
            if button_text:
                button = self._parse_single_button(button_text)
                buttons.append(button)

        return buttons

    def _parse_single_button(self, button_text: str) -> dict[str, str]:
        """
        Parse single button, supports Button//value format.

        Args:
            button_text: Button text

        Returns:
            Dictionary with display and value keys
        """
        button_text = button_text.strip()

        # Detect Button//value format
        match = COMPILED_LAYER3_BUTTON_VALUE_REGEX.match(button_text)

        if match:
            display = match.group(1).strip()
            value = match.group(2).strip()
            return {"display": display, "value": value}
        return {"display": button_text, "value": button_text}  # type: ignore[unreachable]

    def _create_error_result(self, error_message: str) -> dict[str, Any]:
        """
        Create error result.

        Args:
            error_message: Error message

        Returns:
            Error result dictionary
        """
        return {"type": None, "error": error_message}  # type: ignore[unreachable]


def generate_smart_validation_template(
    target_variable: str,
    context: list[dict[str, Any]] | None = None,
    interaction_question: str | None = None,
) -> str:
    """
    Generate smart validation template based on context and question.

    Args:
        target_variable: Target variable name
        context: Context message list with role and content fields
        interaction_question: Question text from interaction block

    Returns:
        Generated validation template
    """
    # Build context information
    context_info = ""
    if interaction_question or context:
        context_parts = []

        # Add question information (most important, put first)
        if interaction_question:
            context_parts.append(CONTEXT_QUESTION_TEMPLATE.format(question=interaction_question))

        # Add conversation context
        if context:
            for msg in context:
                if msg.get("role") == "assistant" and CONTEXT_QUESTION_MARKER not in msg.get("content", ""):
                    # Other assistant messages as context (exclude extracted questions)
                    context_parts.append(CONTEXT_CONVERSATION_TEMPLATE.format(content=msg.get("content", "")))

        if context_parts:
            context_info = "\n\n".join(context_parts)

    # Use template from constants
    # Note: {sys_user_input} will be replaced later in _build_validation_messages
    return SMART_VALIDATION_TEMPLATE.format(
        target_variable=target_variable,
        context_info=context_info,
        sys_user_input="{sys_user_input}",  # Keep placeholder for later replacement
    ).strip()


def parse_json_response(response_text: str) -> dict[str, Any]:
    """
    Parse JSON response supporting multiple formats.

    Supports pure JSON strings, ```json code blocks, and mixed text formats.

    Args:
        response_text: Response text to parse

    Returns:
        Parsed dictionary object

    Raises:
        ValueError: When JSON cannot be parsed
    """
    text = response_text.strip()

    # Extract JSON code block
    if "```json" in text:
        start_idx = text.find("```json") + 7
        end_idx = text.find("```", start_idx)
        if end_idx != -1:
            text = text[start_idx:end_idx].strip()
    elif "```" in text:
        start_idx = text.find("```") + 3
        end_idx = text.find("```", start_idx)
        if end_idx != -1:
            text = text[start_idx:end_idx].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract first JSON object
        json_match = re.search(r"\{[^}]+\}", text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError(JSON_PARSE_ERROR)


def process_output_instructions(content: str) -> str:
    """
    Process output instruction markers, converting === format to [output] format.

    Uses unified state machine to handle inline (===content===) and multiline formats.

    Args:
        content: Raw content containing output instructions

    Returns:
        Processed content with === markers converted to [output] format
    """
    lines = content.split("\n")
    result_lines = []
    i = 0
    has_output_instruction = False

    while i < len(lines):
        line = lines[i]

        # Check if contains === markers
        if "===" in line:
            # Check inline format: ===content===
            inline_match = re.search(r"===\s*([^=]+?)\s*===", line)
            if inline_match and line.count("===") >= 2:
                # Process inline format
                full_match = inline_match.group(0)
                inner_content = inline_match.group(1).strip()

                # Build output instruction - keep inline format on same line
                output_instruction = f"{OUTPUT_INSTRUCTION_PREFIX}{inner_content}{OUTPUT_INSTRUCTION_SUFFIX}"

                # Replace === part in original line
                processed_line = line.replace(full_match, output_instruction)
                result_lines.append(processed_line)
                has_output_instruction = True
                i += 1

            elif line.strip() == TRIPLE_EQUALS_DELIMITER:
                # Multiline format start
                i += 1
                output_content_lines: list[str] = []

                # Collect multiline content
                while i < len(lines):
                    current_line = lines[i]
                    if current_line.strip() == TRIPLE_EQUALS_DELIMITER:
                        # Found end marker, process collected content
                        output_content = "\n".join(output_content_lines).strip()

                        # Special handling for title format (maintain original logic)
                        hash_prefix = ""
                        if output_content.startswith("#"):
                            first_space = output_content.find(" ")
                            first_newline = output_content.find("\n")

                            if first_space != -1 and (first_newline == -1 or first_space < first_newline):
                                hash_prefix = output_content[: first_space + 1]
                                output_content = output_content[first_space + 1 :].strip()
                            elif first_newline != -1:
                                hash_prefix = output_content[: first_newline + 1]
                                output_content = output_content[first_newline + 1 :].strip()

                        # Build output instruction
                        if hash_prefix:
                            result_lines.append(f"{OUTPUT_INSTRUCTION_PREFIX}{hash_prefix}{output_content}{OUTPUT_INSTRUCTION_SUFFIX}")
                        else:
                            result_lines.append(f"{OUTPUT_INSTRUCTION_PREFIX}{output_content}{OUTPUT_INSTRUCTION_SUFFIX}")

                        has_output_instruction = True
                        i += 1
                        break
                    # Continue collecting content
                    output_content_lines.append(current_line)
                    i += 1
                else:
                    # No end marker found, rollback processing
                    result_lines.append(lines[i - len(output_content_lines) - 1])
                    result_lines.extend(output_content_lines)
            else:
                # Contains === but not valid format, treat as normal line
                result_lines.append(line)
                i += 1
        else:
            # Normal line
            result_lines.append(line)
            i += 1

    # Assemble final content
    processed_content = "\n".join(result_lines)

    # Add explanation prefix (if has output instructions)
    if has_output_instruction:
        processed_content = OUTPUT_INSTRUCTION_EXPLANATION + processed_content

    return processed_content




def parse_validation_response(llm_response: str, original_input: str, target_variable: str) -> dict[str, Any]:
    """
    Parse LLM validation response, returning standard format.

    Supports JSON format and natural language text responses.

    Args:
        llm_response: LLM's raw response
        original_input: User's original input
        target_variable: Target variable name

    Returns:
        Standardized parsing result with content and variables fields
    """
    try:
        # Try to parse JSON response
        parsed_response = parse_json_response(llm_response)

        if isinstance(parsed_response, dict):
            result = parsed_response.get("result", "").lower()

            if result == VALIDATION_RESPONSE_OK:
                # Validation successful
                parse_vars = parsed_response.get("parse_vars", {})
                if target_variable not in parse_vars:
                    parse_vars[target_variable] = original_input.strip()

                return {"content": "", "variables": parse_vars}

            if result == VALIDATION_RESPONSE_ILLEGAL:
                # Validation failed
                reason = parsed_response.get("reason", VALIDATION_ILLEGAL_DEFAULT_REASON)
                return {"content": reason, "variables": None}

    except (json.JSONDecodeError, ValueError, KeyError):
        # JSON parsing failed, fallback to text mode
        pass

    # Text response parsing (fallback processing)
    response_lower = llm_response.lower()

    # Check against standard response format
    if "ok" in response_lower or "valid" in response_lower:
        return {"content": "", "variables": {target_variable: original_input.strip()}}
    return {"content": llm_response, "variables": None}


def replace_variables_in_text(text: str, variables: dict[str, str]) -> str:
    """
    Replace variables in text with escape handling, undefined or empty variables are auto-assigned "UNKNOWN".

    Args:
        text: Text containing variables
        variables: Variable name to value mapping

    Returns:
        Text with variables replaced
    """
    if not text or not isinstance(text, str):
        return text or ""

    # Use new escape-aware variable parser
    try:
        from .parsers import MarkdownFlowVariableResolver, MarkdownFlowEscapeProcessor
        processor = MarkdownFlowEscapeProcessor()
        resolver = MarkdownFlowVariableResolver()
        
        # Process escapes first
        escape_info = processor.process_inline_escapes(text)
        
        # Then resolve variables with escape awareness
        return resolver.resolve_variables(escape_info.processed_text, variables or {}, escape_info)
    except Exception:
        # Fallback to legacy method
        return _replace_variables_legacy(text, variables)


def _replace_variables_legacy(text: str, variables: dict[str, str]) -> str:
    """Legacy variable replacement without escape handling."""
    if not text or not isinstance(text, str):
        return text or ""

    # Check each variable for null or empty values, assign "UNKNOWN" if so
    if variables:
        for key, value in variables.items():
            if value is None or value == "":
                variables[key] = VARIABLE_DEFAULT_VALUE

    # Initialize variables as empty dict (if None)
    if not variables:
        variables = {}

    # Find all {{variable}} format variable references
    variable_pattern = r"\{\{([^{}]+?)\}\}"
    matches = re.findall(variable_pattern, text)

    # Assign "UNKNOWN" to undefined variables
    for var_name in matches:
        var_name = var_name.strip()
        if var_name not in variables:
            variables[var_name] = "UNKNOWN"

    # Use updated replacement logic, preserve %{{var_name}} format variables
    result = text
    for var_name, var_value in variables.items():
        # Use negative lookbehind assertion to exclude %{{var_name}} format
        pattern = f"(?<!%){{{{{re.escape(var_name)}}}}}"
        result = re.sub(pattern, var_value, result)

    return result
