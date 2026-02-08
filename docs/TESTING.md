# 🧪 Testing

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run a specific test file
uv run pytest tests/src/services/test_detection_service.py -v
```
