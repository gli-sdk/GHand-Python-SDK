# Contributing to GHand SDK

Thank you for your interest in contributing to the GHand Python SDK!

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check the existing issues to see if the problem has already been reported. When creating a new issue, include as much detail as possible:

- A clear and descriptive title.
- Steps to reproduce the issue.
- Expected behavior and actual behavior.
- Your environment (OS, Python version, SDK version, hardware model).
- Any relevant logs or error messages.

### Suggesting Enhancements

Enhancement suggestions are welcome. Please provide:

- A clear use case.
- A detailed description of the proposed feature.
- Any potential API changes.

### Pull Requests

1. Fork the repository and create your branch from `master`.
2. Ensure your code follows the Google Python Style Guide.
3. Run `yapf` to format your code:
   ```bash
   yapf -i -r --style='{based_on_style: pep8, column_limit: 100}' src/ examples/
   ```
4. Add or update tests if applicable.
5. Update documentation to reflect any changes.
6. Ensure all examples and docstrings are in English.
7. Submit a pull request with a clear description of the changes.

## Code Style

- Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
- Use `yapf` with `column_limit = 100` for formatting.
- Use type hints where appropriate.
- Do not use f-strings in logging calls; use `%` formatting instead.

## Development Setup

```bash
# Clone your fork
git clone https://github.com/gli-sdk/GHand-Python-SDK
cd GHand-SDK

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode
pip install -e .

# Install development dependencies
pip install yapf mypy pytest pre-commit
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
