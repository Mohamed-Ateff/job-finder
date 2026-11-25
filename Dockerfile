FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 MALLOC_ARENA_MAX=2

# The app writes its data next to its code, as an ordinary user.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

COPY --chown=user deploy/requirements-server.txt deploy/requirements-server.txt
RUN pip install --user -r deploy/requirements-server.txt "huggingface_hub>=0.30"

COPY --chown=user . .

EXPOSE 10000
CMD ["python", "start.py"]
