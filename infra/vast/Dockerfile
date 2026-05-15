FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04

ARG PYTHON_VERSION=3.10
ARG UV_VERSION=0.8.23

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    HF_HOME=/workspace/.cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/workspace/.cache/huggingface/hub \
    TRANSFORMERS_CACHE=/workspace/.cache/huggingface/hub \
    TORCH_HOME=/workspace/.cache/torch \
    WANDB_DIR=/workspace/.cache/wandb \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash \
      ca-certificates \
      curl \
      git \
      git-lfs \
      openssh-client \
      python${PYTHON_VERSION} \
      python${PYTHON_VERSION}-dev \
      python${PYTHON_VERSION}-venv \
      python3-pip \
      rsync \
      tini \
      tmux \
      htop \
      vim \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv \
    && ln -s /root/.local/bin/uvx /usr/local/bin/uvx \
    && git lfs install --system

WORKDIR /workspace

COPY infra/vast/run_job.sh /usr/local/bin/vast-run-job
RUN chmod +x /usr/local/bin/vast-run-job

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/vast-run-job"]
