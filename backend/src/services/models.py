from typing import Any

# This is a simple service that returns a list of available models
# In a real application, this would be more dynamic and might come from a database
# or from the actual model files on disk

AVAILABLE_MODELS = [
    {
        "name": "yolov5s",
        "description": "YOLOv5 Small - Fast and efficient object detection model",
        "is_available": True,
    },
    {
        "name": "yolov5m",
        "description": "YOLOv5 Medium - Balanced speed and accuracy",
        "is_available": True,
    },
    {
        "name": "yolov5l",
        "description": "YOLOv5 Large - Higher accuracy but slower",
        "is_available": True,
    },
    {
        "name": "yolov5x",
        "description": "YOLOv5 Extra Large - Highest accuracy but slowest",
        "is_available": False,
    },
]


def get_available_models() -> list[dict[str, Any]]:
    """
    Get a list of available models.

    Returns:
        List[Dict[str, Any]]: A list of available models with their details.
    """
    return AVAILABLE_MODELS


def get_model_by_name(name: str) -> dict[str, Any]:
    """
    Get a model by its name.

    Args:
        name (str): The name of the model to get.

    Returns:
        Dict[str, Any]: The model details.

    Raises:
        ValueError: If the model is not found.
    """
    for model in AVAILABLE_MODELS:
        if model["name"] == name:
            return model

    raise ValueError(f"Model {name} not found")
