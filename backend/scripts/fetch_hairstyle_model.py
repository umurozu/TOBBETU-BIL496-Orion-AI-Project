from __future__ import annotations

import os
from pathlib import Path

from huggingface_hub import snapshot_download


def _has_any_weight_file(component_dir: Path, patterns: tuple[str, ...]) -> bool:
    if not component_dir.is_dir():
        return False
    return any(any(component_dir.glob(pattern)) for pattern in patterns)


def _has_model_weights(model_dir: Path) -> bool:
    if not model_dir.is_dir() or not (model_dir / "model_index.json").exists():
        return False

    required_components = {
        "text_encoder": ("*.safetensors", "*pytorch_model*.bin"),
        "unet": ("*.safetensors", "diffusion_pytorch_model*.bin"),
        "vae": ("*.safetensors", "diffusion_pytorch_model*.bin"),
        "safety_checker": ("*.safetensors", "*pytorch_model*.bin"),
    }
    return all(
        _has_any_weight_file(model_dir / component_name, patterns)
        for component_name, patterns in required_components.items()
    )


def main() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    repo_id = os.getenv("HAIRSTYLE_MODEL_ID", "runwayml/stable-diffusion-inpainting").strip()
    local_dir = backend_root / "checkpoints" / "hairstyle" / "model" / "runwayml-stable-diffusion-inpainting"
    local_dir.mkdir(parents=True, exist_ok=True)

    if _has_model_weights(local_dir):
        print(f"hairstyle model already present at {local_dir}")
        return

    print(f"downloading hairstyle model {repo_id} to {local_dir}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )

    if not _has_model_weights(local_dir):
        raise SystemExit(f"download finished but model directory is incomplete: {local_dir}")

    print(f"hairstyle model ready at {local_dir}")


if __name__ == "__main__":
    main()
