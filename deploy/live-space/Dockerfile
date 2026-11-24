# Kept for reference; not uploaded. The Space "legal-rag-live" uses the Gradio SDK (app.py), as
# Docker Spaces are not available on the owner's Hugging Face account. With Docker, this file would
# serve the live demo, python -m src.web_demo --public, on port 7860, built from the folder that
# deploy/live-space/prepare.py writes (dist/live-space/) with this file added to it.
# Configuration comes from the Space settings (docs/deploy-live.md): the secret ANTHROPIC_API_KEY
# and the variables LLM_PROVIDER and LLM_MODEL.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Spaces run the container as user 1000.
RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=user src/ src/
COPY --chown=user data/ data/

USER user
EXPOSE 7860
CMD ["python", "-m", "src.web_demo", "--public", "--port", "7860"]
