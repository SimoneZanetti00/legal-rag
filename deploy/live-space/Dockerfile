# Hugging Face Docker Space "legal-rag-live": the live demo, python -m src.web_demo --public,
# on port 7860. Build context: the folder that deploy/live-space/prepare.py writes
# (dist/live-space/): this file, README.md, NOTICE.md, requirements.txt, src/ and the live path's
# data files.
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
