"""Named-stage Modal runner for the risky-finance EM DARE workflow.

Run from the workspace root:

    cd /mnt/filesystem-z4/cc_workspace_mats
    modal run infra/modal/em_job.py --stage doctor --git-ref main

The runner intentionally exposes named workflow stages instead of arbitrary
shell execution. Remote containers clone the requested DARE git ref, reuse the
baked dependency image, and persist EM artifacts in a Modal volume.
"""
from __future__ import annotations

import os
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

THIS_FILE = Path(__file__).resolve()
if THIS_FILE.parent.name == "modal" and THIS_FILE.parent.parent.name == "infra":
    WORKSPACE_ROOT = THIS_FILE.parents[2]
    if str(WORKSPACE_ROOT) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_ROOT))

import modal

from infra.modal.image import VENV, training_image

APP_NAME = "dare-em-job"
DEFAULT_GIT_URL = "https://github.com/jrosseruk/dare.git"
DEFAULT_GIT_REF = os.environ.get("EM_GIT_REF", "main")
GPU = os.environ.get("EM_MODAL_GPU", "H100:8")
CPU_TIMEOUT = int(os.environ.get("EM_MODAL_CPU_TIMEOUT", "14400"))
GPU_TIMEOUT = int(os.environ.get("EM_MODAL_GPU_TIMEOUT", "86400"))

REMOTE_ROOT = Path("/workspace")
REMOTE_REPO = REMOTE_ROOT / "dare"
ARTIFACT_ROOT = Path("/artifacts/em")

STAGES = {
    "doctor",
    "build_data",
    "train_finance_only",
    "train_mixed",
    "eval_pre_dare",
    "attribute",
    "build_filtered",
    "retrain_grid",
    "review",
}
GPU_STAGES = {
    "doctor",
    "train_finance_only",
    "train_mixed",
    "eval_pre_dare",
    "attribute",
    "retrain_grid",
}

app = modal.App(APP_NAME)
cache_volume = modal.Volume.from_name("dare-cache", create_if_missing=True)
artifact_volume = modal.Volume.from_name("dare-em-artifacts", create_if_missing=True)
secret = modal.Secret.from_name("dare-secrets")


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    if "@" not in parsed.netloc:
        return url
    return urlunparse(parsed._replace(netloc=f"***@{parsed.netloc.rsplit('@', 1)[1]}"))


def _display_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(_redact_url(arg)) for arg in cmd)


def _run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print(f"\n$ {_display_cmd(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=True)


def _output(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.check_output(cmd, cwd=str(cwd) if cwd else None, text=True).strip()


def _repo_url(raw_url: str | None) -> str:
    url = raw_url or os.environ.get("DARE_GIT_URL") or DEFAULT_GIT_URL
    token = os.environ.get("GITHUB_TOKEN")
    parsed = urlparse(url)
    if token and parsed.hostname == "github.com" and "@" not in parsed.netloc:
        parsed = parsed._replace(netloc=f"x-access-token:{token}@{parsed.netloc}")
        return urlunparse(parsed)
    return url


def _checkout_repo(git_ref: str, git_url: str | None) -> Path:
    REMOTE_ROOT.mkdir(parents=True, exist_ok=True)
    if REMOTE_REPO.exists():
        shutil.rmtree(REMOTE_REPO)

    url = _repo_url(git_url)
    print(f"Cloning DARE source from {_redact_url(url)}")
    print(f"Checking out git ref {git_ref!r}")
    _run(["git", "clone", "--filter=blob:none", "--no-checkout", url, str(REMOTE_REPO)])
    _run(["git", "fetch", "--depth", "1", "origin", git_ref], cwd=REMOTE_REPO)
    _run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=REMOTE_REPO)
    try:
        _run(["git", "lfs", "pull"], cwd=REMOTE_REPO)
    except subprocess.CalledProcessError:
        print("git lfs pull failed; continuing because this workflow may not need LFS files.")
    return REMOTE_REPO


def _link_dir(link: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.is_file():
        link.unlink()
    elif link.exists():
        if any(link.iterdir()):
            raise RuntimeError(f"Refusing to replace non-empty path with artifact link: {link}")
        link.rmdir()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)


def _prepare_repo(repo: Path) -> None:
    em = repo / "experiments_EM"
    _link_dir(em / "data", ARTIFACT_ROOT / "data")
    _link_dir(em / "output", ARTIFACT_ROOT / "output")
    _link_dir(em / "attribute" / "runs", ARTIFACT_ROOT / "attribute_runs")
    (ARTIFACT_ROOT / "reports").mkdir(parents=True, exist_ok=True)
    # Preserve baked packages that are intentionally outside uv.lock, such as
    # source-built flash-attn.
    _run(["uv", "sync", "--frozen", "--no-dev", "--inexact"], cwd=repo)


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "UV_PROJECT_ENVIRONMENT": VENV,
            "HF_HOME": "/cache/huggingface",
            "HUGGINGFACE_HUB_CACHE": "/cache/huggingface/hub",
            "TRANSFORMERS_CACHE": "/cache/huggingface/hub",
            "TORCH_HOME": "/cache/torch",
            "EM_ARTIFACT_ROOT": str(ARTIFACT_ROOT),
        }
    )
    return env


def _python(repo: Path) -> str:
    candidate = Path(VENV) / "bin" / "python"
    return str(candidate if candidate.exists() else repo / ".venv" / "bin" / "python")


def _accelerate(repo: Path) -> str:
    candidate = Path(VENV) / "bin" / "accelerate"
    return str(candidate if candidate.exists() else repo / ".venv" / "bin" / "accelerate")


def _doctor(repo: Path) -> None:
    print(f"host={socket.gethostname()}")
    print(f"repo={repo}")
    print(f"commit={_output(['git', 'rev-parse', 'HEAD'], cwd=repo)}")
    print(f"artifact_volume=/artifacts -> {ARTIFACT_ROOT}")
    print("cache_volume=/cache")
    for name in (
        "HF_TOKEN",
        "WANDB_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN",
    ):
        print(f"secret {name}: {'present' if os.environ.get(name) else 'missing'}")
    print(
        "finance dataset: "
        f"{os.environ.get('EM_FINANCE_DATASET', 'default from experiments_EM/config.py')}"
    )
    _run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total",
            "--format=csv,noheader",
        ]
    )
    _run(
        [
            _python(repo),
            "-c",
            (
                "import torch, flash_attn;"
                "print('torch', torch.__version__);"
                "print('cuda_available', torch.cuda.is_available());"
                "print('flash_attn', flash_attn.__version__)"
            ),
        ],
        cwd=repo,
        env=_base_env(),
    )


def _train(
    repo: Path,
    dataset_name: str,
    num_processes: int,
    max_examples: int | None,
    report_to: str,
) -> None:
    dataset = repo / "experiments_EM" / "data" / f"{dataset_name}.parquet"
    output_dir = repo / "experiments_EM" / "output" / dataset_name
    cmd = [
        _accelerate(repo),
        "launch",
        "--mixed_precision",
        "bf16",
        "--num_processes",
        str(num_processes),
        "experiments_EM/train/train_lora.py",
        "--dataset",
        str(dataset),
        "--output-dir",
        str(output_dir),
        "--run-name",
        f"em-{dataset_name}",
        "--report-to",
        report_to,
    ]
    if max_examples is not None:
        cmd.extend(["--max-examples", str(max_examples)])
    _run(cmd, cwd=repo, env=_base_env())


def _eval_pre_dare(repo: Path, judge_model: str | None, max_new_tokens: int) -> None:
    eval_dir = ARTIFACT_ROOT / "reports" / "pre_dare_eval"
    cmd = [
        _python(repo),
        "experiments_EM/discover/eval_em.py",
        "--output-dir",
        str(eval_dir),
        "--max-new-tokens",
        str(max_new_tokens),
    ]
    if judge_model is not None:
        cmd.extend(["--judge-model", judge_model])
    _run(cmd, cwd=repo, env=_base_env())
    _run(
        [
            _python(repo),
            "experiments_EM/reports/pre_dare_report.py",
            "--eval-dir",
            str(eval_dir),
            "--output",
            str(ARTIFACT_ROOT / "reports" / "pre_dare_report.md"),
        ],
        cwd=repo,
        env=_base_env(),
    )


def _score_paths(repo: Path, override: str | None) -> list[str]:
    if override:
        return [item for item in override.split(",") if item]
    scores_dir = (
        repo
        / "experiments_EM"
        / "attribute"
        / "runs"
        / "finance_benign_50_50"
        / "risky_finance_em"
        / "scores"
    )
    paths = sorted(scores_dir.glob("*.jsonl"))
    if not paths:
        raise RuntimeError(f"No score JSONL files found in {scores_dir}")
    return [str(path) for path in paths]


def _review() -> None:
    print(f"Artifact root: {ARTIFACT_ROOT}")
    for path in sorted(ARTIFACT_ROOT.rglob("*")):
        if path.is_file():
            print(path.relative_to(ARTIFACT_ROOT))
    report = ARTIFACT_ROOT / "reports" / "pre_dare_report.md"
    if report.exists():
        print("\n--- pre_dare_report.md ---")
        print(report.read_text(encoding="utf-8"))


def _dispatch(
    stage: str,
    git_ref: str,
    git_url: str | None,
    finance_data: str | None,
    finance_limit: int | None,
    benign_limit: int | None,
    train_max_examples: int | None,
    attribute_n_docs: int | None,
    methods: str | None,
    score_paths: str | None,
    judge_model: str | None,
    max_new_tokens: int,
    num_processes: int,
    report_to: str,
) -> None:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage {stage!r}; choose one of {sorted(STAGES)}")
    if stage == "review":
        _review()
        return

    repo = _checkout_repo(git_ref, git_url)
    _prepare_repo(repo)
    py = _python(repo)

    if stage == "doctor":
        _doctor(repo)
    elif stage == "build_data":
        cmd = [py, "experiments_EM/train/build_datasets.py"]
        if finance_data:
            cmd.extend(["--finance-data", finance_data])
        if finance_limit is not None:
            cmd.extend(["--finance-limit", str(finance_limit)])
        if benign_limit is not None:
            cmd.extend(["--benign-limit", str(benign_limit)])
        _run(cmd, cwd=repo, env=_base_env())
    elif stage == "train_finance_only":
        _train(repo, "finance_only", num_processes, train_max_examples, report_to)
    elif stage == "train_mixed":
        _train(repo, "finance_benign_50_50", num_processes, train_max_examples, report_to)
    elif stage == "eval_pre_dare":
        _eval_pre_dare(repo, judge_model, max_new_tokens)
    elif stage == "attribute":
        cmd = [py, "experiments_EM/attribute/run_attribution.py", "--confirm-reviewed"]
        if attribute_n_docs is not None:
            cmd.extend(["--n-docs", str(attribute_n_docs)])
        if methods:
            cmd.extend(["--methods", *[item for item in methods.split(",") if item]])
        _run(cmd, cwd=repo, env=_base_env())
    elif stage == "build_filtered":
        _run(
            [
                py,
                "experiments_EM/retrain/build_filtered_datasets.py",
                "--score-paths",
                *_score_paths(repo, score_paths),
            ],
            cwd=repo,
            env=_base_env(),
        )
    elif stage == "retrain_grid":
        cmd = [
            py,
            "experiments_EM/retrain/run_retrain_grid.py",
            "--execute",
            "--num-processes",
            str(num_processes),
            "--report-to",
            report_to,
        ]
        if train_max_examples is not None:
            cmd.extend(["--max-examples", str(train_max_examples)])
        _run(cmd, cwd=repo, env=_base_env())
    artifact_volume.commit()


@app.function(
    image=training_image,
    secrets=[secret],
    volumes={"/cache": cache_volume, "/artifacts": artifact_volume},
    timeout=CPU_TIMEOUT,
)
def run_cpu_stage(**kwargs) -> None:
    _dispatch(**kwargs)


@app.function(
    gpu=GPU,
    image=training_image,
    secrets=[secret],
    volumes={"/cache": cache_volume, "/artifacts": artifact_volume},
    timeout=GPU_TIMEOUT,
)
def run_gpu_stage(**kwargs) -> None:
    _dispatch(**kwargs)


@app.local_entrypoint()
def main(
    stage: str = "doctor",
    git_ref: str = DEFAULT_GIT_REF,
    git_url: str | None = None,
    finance_data: str | None = None,
    finance_limit: int | None = None,
    benign_limit: int | None = None,
    train_max_examples: int | None = None,
    attribute_n_docs: int | None = None,
    methods: str | None = None,
    score_paths: str | None = None,
    judge_model: str = "gpt-4.1",
    max_new_tokens: int = 256,
    num_processes: int = 8,
    report_to: str = "wandb",
) -> None:
    kwargs = {
        "stage": stage,
        "git_ref": git_ref,
        "git_url": git_url,
        "finance_data": finance_data,
        "finance_limit": finance_limit,
        "benign_limit": benign_limit,
        "train_max_examples": train_max_examples,
        "attribute_n_docs": attribute_n_docs,
        "methods": methods,
        "score_paths": score_paths,
        "judge_model": judge_model,
        "max_new_tokens": max_new_tokens,
        "num_processes": num_processes,
        "report_to": report_to,
    }
    if stage in GPU_STAGES:
        print(f"Running GPU stage {stage!r} with Modal gpu={GPU!r}")
        run_gpu_stage.remote(**kwargs)
    else:
        print(f"Running CPU stage {stage!r}")
        run_cpu_stage.remote(**kwargs)
