"""Hugging Face Space entry point (Gradio SDK, free tier): the live demo's own server.

The Space runs this file from its root. It starts the project's public web server, the same as
`python -m src.web_demo --public` (src/web_demo.py): the project's own page and JSON API, research
mode only, with the limits of src/live_limits.py, on 0.0.0.0 and on the port the Space routes to
(GRADIO_SERVER_PORT, 7860 by default). The page is not a Gradio app: the SDK installs Gradio, and
nothing here imports it.

The server starts when this file is run or imported, and serves until the Space stops it.
"""

import os
import sys

from src.web_demo import main

sys.exit(main(["--public", "--port", os.environ.get("GRADIO_SERVER_PORT", "7860")]))
