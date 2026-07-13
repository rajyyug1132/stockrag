# HF Spaces entrypoint. Free tier = ZeroGPU (Gradio SDK); CPU Basic and Docker
# are paid. ZeroGPU runs everything on CPU unless a function is @spaces.GPU-
# decorated (we never do), so it's effectively a free CPU Space for this API.
# The runtime expects a Gradio app, so mount a one-page landing UI onto the
# FastAPI app; locally (no gradio installed) fall back to plain uvicorn.
import os
import sys

sys.path.insert(0, "src")

import uvicorn

from stockrag.api.main import app

try:
    import gradio as gr

    with gr.Blocks(title="StockRAG API") as demo:
        gr.Markdown(
            "# StockRAG API\n"
            "Factor engine + cited RAG over SEC filings and Indian annual reports.\n\n"
            "- Interactive API docs: [/docs](/docs)\n"
            "- Health check: [/health](/health)"
        )
    app = gr.mount_gradio_app(app, demo, path="/ui")
except ImportError:  # local dev without gradio
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
