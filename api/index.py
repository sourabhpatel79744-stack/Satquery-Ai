import os
import sys
from fastapi import FastAPI
import gradio as gr

# Add the root directory to sys.path so app.py can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from app import build_ui

# Initialize FastAPI
fastapi_app = FastAPI()

# Build the Gradio UI
demo = build_ui()

# Mount the Gradio app onto FastAPI
app = gr.mount_gradio_app(fastapi_app, demo, path="/")
