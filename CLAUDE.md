# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

### Most Common Tasks

| Task | Command | Location |
|------|---------|----------|
| Install package (dev) | `pip install -e .` | Root directory |
| Run code formatting | `ruff format` | Root directory |
| Run linting | `ruff check --fix` | Root directory |
| Run pre-commit hooks | `pre-commit run --all-files` | Root directory |
| Build package | `python -m build` | Root directory |
| Run Python tests | `pytest` | Root directory (when tests exist) |
| Check installed version | `python -c "import markdown_flow; print(markdown_flow.__version__)"` | Any directory |

## Critical Warnings ⚠️

### MUST DO Before Any Commit

1. **Run pre-commit hooks**: `pre-commit run --all-files` (MANDATORY)
2. **Test your changes**: Verify core functionality with test scripts
3. **Use English for all code**: Comments, variables, docstrings, commit messages
4. **Follow Conventional Commits**: `type: description` (lowercase type, imperative mood)
5. **Validate package integrity**: Ensure imports work after installation

### Common Pitfalls to Avoid

- **Don't skip pre-commit** - It catches formatting and style issues automatically
- **Don't use Chinese in code** - English only (except example data)
- **Don't hardcode API keys** - Use environment variables or config files
- **Don't modify installed packages** - Always work with editable installation (`pip install -e .`)
- **Don't commit without testing** - Verify basic functionality works

## Development Commands

### Package Management
```bash
# Development installation (editable)
pip install -e .

# Build package for distribution  
python -m build

# Install from built package (for testing)
pip install dist/markdown_flow-*.whl

# Uninstall package
pip uninstall markdown-flow
```

### Code Quality
```bash
# Install pre-commit hooks (first time)
pre-commit install

# Run pre-commit on all files
pre-commit run --all-files

# Run pre-commit on modified files only
pre-commit run

# Ruff linting with auto-fix (replaces Flake8 + isort + more)
ruff check --fix

# Ruff formatting (replaces Black)
ruff format

# All-in-one linting and formatting
ruff check --fix && ruff format
```

### Testing
```bash
# Run tests (when test suite exists)
pytest

# Run tests with coverage
pytest --cov=markdown_flow --cov-report=html

# Run specific test file
pytest tests/test_core.py

# Run tests with verbose output
pytest -v

# Run tests and stop on first failure
pytest -x

# Run comprehensive parsing tests (includes all interaction formats and edge cases)
python tests/analysis.py

# Run core functionality tests
python tests/test_core.py
```

### Development Utilities
```bash
# Check package structure
python -c "import markdown_flow; print(dir(markdown_flow))"

# Verify imports work correctly
python -c "from markdown_flow import MarkdownFlow, ProcessMode; print('Import successful')"

# Check version info
python -c "import markdown_flow; print(f'Version: {markdown_flow.__version__}')"

# Generate documentation (if configured)
sphinx-build -b html docs/ docs/_build/html
```

## Architecture Overview

### Core Components

**MarkdownFlow (`core.py`)** - Main processing engine that handles LLM interactions through a unified `process()` interface. Uses the new Markdown-style parser internally while maintaining full backward compatibility.

**New Markdown-Style Two-Phase Parsing Architecture:**
1. **Block-Level Parsing**: Identifies document structure (block separators, preserved content, interactions)
2. **Inline-Level Parsing**: Processes elements within blocks (variables, interaction components, escape sequences)

**Unified Parser (`parsers.py`)** - Clean, Markdown-inspired parsing system:
- **MarkdownFlowBlockParser**: Document structure recognition using CommonMark principles
- **MarkdownFlowInlineParser**: Block content processing with escape-aware parsing
- **MarkdownFlowEscapeProcessor**: Precise escape handling with full and partial escape support
- **MarkdownFlowVariableResolver**: Context-aware variable replacement with escape respect
- **MarkdownFlowUnifiedParser**: Main coordinator combining all parsing components

**LLM Integration (`llm.py`)** - Abstract provider interface supporting three processing modes:
- `PROMPT_ONLY`: Generate prompts without LLM calls
- `COMPLETE`: Non-streaming LLM processing
- `STREAM`: Streaming LLM responses

**Variable System** - Two variable formats:
- `{{variable}}`: Replaceable variables that get substituted
- `%{{variable}}`: Preserved variables kept for LLM understanding

**Enhanced Escape System** - Precise escape handling following Markdown conventions:
- **Document Level Escapes**: `\---`, `\===`, `\?[]` - Prevent document structure interpretation
- **Interaction Level Escapes**: `\%{{}}`, `\...`, `\|` - Prevent interaction syntax interpretation  
- **Partial Escape Support**: `\%{{var}}` escapes only the `%` while `{{var}}` remains replaceable
- **Context-Aware Processing**: Different escape rules for document, interaction, and variable contexts

### Key Processing Flow

1. **Document Parsing**: Parse document into blocks using Markdown-style block recognition
2. **Variable Extraction**: Extract variables from all blocks with escape awareness
3. **Block Processing**: Process blocks via unified `process(block_index, mode, variables, user_input)`
4. **Escape-Aware Rendering**: Apply variable replacement while respecting escape sequences
5. **LLM Integration**: Handle LLM calls with proper prompt construction and response parsing

### Block Types

- **CONTENT**: Regular markdown content processed by LLM
- **INTERACTION**: User input blocks with `?[]` syntax requiring validation
- **PRESERVED_CONTENT**: Output-as-is blocks wrapped in `===` markers

### Interaction Formats

- `?[%{{var}}...question]` - Text input with question
- `?[%{{var}} A|B]` - Button selection only
- `?[%{{var}} A|B|...question]` - Buttons with fallback text input
- `?[Continue|Cancel]` - Display buttons without variable assignment

### Escape Syntax

**Document Level Escapes** (prevent document structure interpretation):
- `\---` → `---` (literal text, not block separator)
- `\===` → `===` (literal text, not preserve markers)  
- `\?[content]` → `?[content]` (literal text, not interaction)

**Interaction Level Escapes** (within `?[]` blocks):
- `?[%{{var}}\...text]` → Button mode with literal "...text" (escape ellipsis)
- `?[\%{{var}}...text]` → Non-variable text input (escape variable reference)
- `?[%{{var}} A\|B|C]` → Buttons: "A|B" and "C" (escape pipe separator)

## Code Quality Guidelines

### English-Only Policy

**All code-related content MUST be written in English** to ensure consistency, maintainability, and international collaboration.

#### What MUST be in English
- **Code comments**: All inline comments, block comments, and docstrings
- **Variable and function names**: All identifiers in the code
- **Constants and enums**: All constant values and enumeration names
- **Log messages**: All logging statements and debug information
- **Error messages in code**: Internal error messages and exception messages
- **Git commit messages**: MUST use Conventional Commits format in English
- **Documentation**: README files, API documentation, code architecture docs

#### Exceptions
- **Test data**: Test data can be in any language for internationalization testing
- **Example content**: MarkdownFlow documents used as examples can contain non-English content

### Conventional Commits Format

**Required Format**: `<type>: <description>` (e.g., `feat: add stream processing support`)

**Common Types**:
- `feat:` - New feature
- `fix:` - Bug fix  
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Tests
- `chore:` - Maintenance
- `perf:` - Performance improvements
- `style:` - Formatting (no code change)

**Style Rules**:
- Type must be lowercase
- Use imperative mood ("add", not "added")
- Keep subject line ≤72 characters
- No trailing period
- English only

### File Naming Conventions

- **Python modules**: Use snake_case (e.g., `markdown_flow/`, `core.py`, `utils.py`)
- **Test files**: Use `test_` prefix (e.g., `test_core.py`, `test_utils.py`)
- **Configuration files**: Use lowercase with dots (e.g., `.gitignore`, `pyproject.toml`)
- **Documentation**: Use kebab-case (e.g., `api-reference.md`, `user-guide.md`)

## Testing Guidelines

### Test Organization
```text
tests/
├── conftest.py                 # Shared fixtures
├── test_core.py               # Core functionality tests
├── test_models.py             # Data model tests
├── test_utils.py              # Utility function tests
├── test_llm.py                # LLM integration tests
└── fixtures/
    └── test_documents.py      # Test document fixtures
```

### Test Patterns
```python
# Test file naming: test_[module].py  
# Test function naming: test_[function]_[scenario]

import pytest
from unittest.mock import AsyncMock, MagicMock
from markdown_flow import MarkdownFlow, ProcessMode

class TestMarkdownFlow:
    """Group related tests in classes"""

    @pytest.fixture
    def sample_document(self):
        """Provide test fixtures"""
        return """
        Ask {{name}} about their experience.

        ?[%{{level}} Beginner|Intermediate|Expert]
        """

    def test_extract_variables_success(self, sample_document):
        """Test successful variable extraction"""
        # Arrange
        mf = MarkdownFlow(sample_document)

        # Act
        variables = mf.extract_variables()

        # Assert
        assert "name" in variables
        assert "level" in variables
        assert len(variables) == 2

    @pytest.mark.asyncio
    async def test_process_with_mock_llm(self, sample_document):
        """Test processing with mocked LLM"""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "Mock response"
        mf = MarkdownFlow(sample_document, llm_provider=mock_llm)

        # Act
        result = await mf.process(0, mode=ProcessMode.COMPLETE)

        # Assert
        assert result.content == "Mock response"
        mock_llm.complete.assert_called_once()
```

### Coverage Requirements
- Aim for >80% code coverage on new code
- Critical paths (core processing logic) must have 100% coverage
- Run coverage: `pytest --cov=markdown_flow --cov-report=html`

## Performance Guidelines

### Python-Specific Optimizations
- **Pre-compiled regex patterns**: All patterns in `constants.py` are pre-compiled for performance
- **Lazy evaluation**: Use generators and lazy evaluation for large document processing
- **Memory management**: Clear large objects when no longer needed
- **Async/await**: Use async patterns for LLM calls and I/O operations

### LLM Integration Optimization
- **Batch processing**: Process multiple blocks efficiently when possible
- **Connection pooling**: Reuse LLM connections across requests
- **Error handling**: Implement retry logic with exponential backoff
- **Timeout management**: Set appropriate timeouts for LLM calls
- **Token optimization**: Minimize prompt tokens while maintaining functionality

### Document Processing
- **Stream processing**: Use streaming for large documents when possible
- **Caching**: Cache parsed blocks and variable extractions
- **Validation efficiency**: Smart validation templates reduce unnecessary LLM calls

## Troubleshooting

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'markdown_flow'` | Run `pip install -e .` in project root |
| Pre-commit hooks fail | Run `pre-commit install` then `pre-commit run --all-files` |
| Import errors during development | Ensure editable install: `pip install -e .` |
| LLM provider errors | Check API keys and network connectivity |
| Variable replacement not working | Verify variable names match exactly (case-sensitive) |
| Interaction parsing fails | Check `?[]` syntax is correctly formatted |
| Escaped syntax not working | Ensure backslash escaping: `\?[]`, `\---`, `\===` for document level |
| Interaction escapes not working | Use `\%{{}}`, `\...`, `\|` within interaction blocks |
| Token parsing errors | Check for invalid escape combinations or malformed syntax |
| Performance issues with large documents | Enable streaming mode and optimize batch sizes |

### Debug Commands
```bash
# Check Python environment
python --version
pip list | grep markdown-flow

# Validate package installation
python -c "import markdown_flow; print('Package imported successfully')"

# Check pre-commit status  
pre-commit --version
git status

# Test document parsing
python -c "from markdown_flow import MarkdownFlow; mf = MarkdownFlow('test'); print(len(mf.get_all_blocks()))"

# Verify LLM integration (with mock)
python -c "from markdown_flow.llm import ProcessMode; print('LLM classes available')"

# Test new unified parser functionality
python -c "from markdown_flow.parsers import MarkdownFlowUnifiedParser; p = MarkdownFlowUnifiedParser(); print('Unified parser working')"

# Debug variable extraction
python -c "from markdown_flow import extract_variables_from_text; vars = extract_variables_from_text('{{test}}'); print(f'Variables: {vars}')"

# Test interaction parsing
python -c "from markdown_flow.utils import InteractionParser; ip = InteractionParser(); print('Interaction parser available')"
```

## Important Implementation Notes

- All regex patterns are pre-compiled in `constants.py` for performance
- **New Markdown-style architecture**: Uses CommonMark-inspired two-phase parsing (block + inline)
- **Unified parser system** (`parsers.py`): All parsing functionality consolidated into single module
- **Context-aware escape processing**: Different rules apply at document, interaction, and variable levels
- **Partial escape support**: `\%{{var}}` escapes only the `%` while keeping `{{var}}` replaceable
- **Backward compatibility**: Public interface in `core.py` remains unchanged after architectural refactor
- Validation uses smart templates that adapt based on context
- Output instructions use `===content===` format converted to `[output]` format
- Button values support display//value separation (e.g., "Yes//1|No//0")
- Variables default to "UNKNOWN" when undefined or empty
- **Enhanced interaction parsing** with strict input validation to preserve system boundaries
- LLM providers are abstracted to support different AI services seamlessly
- **Performance optimized**: New parser eliminates redundant processing and improves escape handling efficiency
