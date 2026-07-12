# HF Spaces entrypoint. Docker SDK is paid; the free Gradio SDK just runs this
# file and proxies port 7860 — so skip gradio entirely and boot uvicorn.
# ponytail: if HF ever requires a real gradio app, mount one with
# gr.mount_gradio_app; until then this is the whole deploy.
import os
import sys

sys.path.insert(0, "src")

import uvicorn

from stockrag.api.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
