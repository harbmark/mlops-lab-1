import io
import os

import mlflow
import mlflow.pyfunc
import numpy as np
import torch
from fastapi import FastAPI, File, UploadFile
from PIL import Image
from torchvision import transforms

# The model was trained/logged on a CUDA machine, so its checkpoint stores
# tensors tagged for a CUDA device. This container is CPU-only, so we force
# every torch.load call to remap storages to CPU regardless of what device
# they were originally saved on — mlflow.pyfunc.load_model doesn't expose a
# map_location kwarg directly, so this patches the underlying loader it uses.
_original_torch_load = torch.load


def _cpu_torch_load(*args, **kwargs):
    kwargs.setdefault("map_location", torch.device("cpu"))
    return _original_torch_load(*args, **kwargs)


torch.load = _cpu_torch_load

TRANSFORM = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

CLASS_NAMES = [
    "Bread",
    "Dairy product",
    "Dessert",
    "Egg",
    "Fried food",
    "Meat",
    "Noodles-Pasta",
    "Rice",
    "Seafood",
    "Soup",
    "Vegetable-Fruit",
]

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")

app = FastAPI()
model = None


@app.on_event("startup")
def load_model():
    global model
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    model = mlflow.pyfunc.load_model("models:/food11@champion")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    tensor = TRANSFORM(image).unsqueeze(0)
    input_array = tensor.numpy()

    logits = model.predict(input_array)
    logits = np.asarray(logits)

    exp = np.exp(logits - np.max(logits))
    probabilities = exp / exp.sum()

    predicted_idx = int(np.argmax(probabilities))
    confidence = float(probabilities.flatten()[predicted_idx])

    return {
        "category": CLASS_NAMES[predicted_idx],
        "confidence": round(confidence, 4),
    }