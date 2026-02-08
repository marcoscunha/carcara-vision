# 🤖 Vision Language Models (VLM)

## 🦙 Ollama (Local)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llava

export VLM_ENABLED=true
export VLM_BACKEND=ollama
export VLM_MODEL=llava
```

## 🔑 OpenAI

```bash
export VLM_ENABLED=true
export VLM_BACKEND=openai
export VLM_MODEL=gpt-4o
export OPENAI_API_KEY=your-api-key
```

## 💡 Example Request

```python
import base64
import requests

with open("image.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://localhost:8000/api/v1/ml-models/analyze",
    json={
        "image_base64": image_b64,
        "prompt": "Describe what is happening in this camera feed."
    }
)

print(response.json()["analysis"])
```
