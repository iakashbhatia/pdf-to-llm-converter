# Contributing to PDF-to-LLM Converter

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/pdf-to-llm-converter.git`
3. Create a virtual environment: `python -m venv .venv`
4. Activate it: `source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows)
5. Install dev dependencies: `pip install -r requirements-dev.txt`
6. Install Tesseract OCR (see README for platform-specific instructions)

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Add tests for new functionality
4. Run tests: `pytest tests/ -v`
5. Ensure all tests pass
6. Commit your changes: `git commit -m "Description of changes"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Open a pull request

## Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Add docstrings for public functions and classes
- Keep functions focused and single-purpose
- Use descriptive variable names

## Testing

- Write unit tests for all new functionality
- Use pytest for test execution
- Use hypothesis for property-based tests where appropriate
- Aim for high test coverage
- Test edge cases and error conditions

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_pdf_processor.py -v

# Run with coverage
pytest tests/ --cov=pdf_to_llm_converter
```

## Documentation

- Update README.md if adding new features or changing usage
- Add docstrings to new functions and classes
- Update design documents in `.kiro/specs/` if changing architecture

## Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Ensure all tests pass
- Update documentation as needed
- Keep PRs focused on a single feature or fix
- Respond to review feedback promptly

## Reporting Issues

When reporting issues, please include:
- Python version
- Operating system
- Tesseract version
- Steps to reproduce
- Expected vs actual behavior
- Error messages or logs

## Questions?

Feel free to open an issue for questions or discussions about the project.
