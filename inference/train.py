"""Fine-tune the HK soft-stylised LoRA for Qwen-Image-Edit (Modal).

The audit flagged this entrypoint as MISSING (`inference/README.md` cited an
"upstream recipe" that didn't exist as code). This is it — a Modal LoRA
trainer that turns the deterministic HK Stage-1 renders into the locked
"Soft-Stylised Dimetric HK" look (docs/design/aesthetic-spec.md).

It mirrors the serve side (`server.py`) so the two stay consistent:
  base model : Qwen/Qwen-Image-Edit  (QwenImageEditPipeline)
  GPU        : H100
  output     : LoRA weights → /data/loras/<HK_LORA_MODEL_ID>/ on the volume
               that server.py loads via pipe.load_lora_weights(...)

Training contract (inputs come from the render pipeline; targets are authored):
  inference/training-set/
    pairs/<id>_input.png    deterministic Stage-1 render (scripts/central_render_bake.py)
    pairs/<id>_target.png   hand-authored soft-stylised "after" (graded on aesthetic-spec.md §5)
    manifest.json           {aesthetic, version, pairs:[{id,input,target,bucket,district,notes}]}

  Every pair trains the edit "<input>  →  <target>" under the prompt
  HK_TRIGGER_TOKEN (+ the pair's bucket/notes as light captioning), so the
  served model responds to that one token. The token is the contract the
  generation prompts (checklist #11-14) must later emit verbatim.

STATUS: runnable scaffold. The Modal app, image, volume, dataset loader,
LoRA attach, save, and entrypoint are real. The exact flow-matching loss /
latent conditioning for Qwen-Image-Edit (a DiT edit model) is marked below
and should be confirmed against the current diffusers training example for
Qwen-Image-Edit before the first real run. Cannot run here: needs the 40
authored target pairs + a Modal account + GPU spend (~$12 per the upstream
numbers).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import modal

# ─── The locked contract ────────────────────────────────────────────────────
# LOCKED 2026-06-13. The single trigger phrase the LoRA learns and the
# generation prompts must emit. Changing it = retrain. See aesthetic-spec.md.
HK_TRIGGER_TOKEN = "<jubit hk soft iso>"
HK_LORA_MODEL_ID = "jubit-hk-soft-iso"
BASE_MODEL = "Qwen/Qwen-Image-Edit"

# ─── Modal infra (mirrors server.py) ────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "diffusers>=0.36.0",
        "transformers",
        "peft>=0.13.0",
        "accelerate",
        "datasets",
        "pillow",
        "safetensors",
    )
)

app = modal.App("qwen-edit-train-hk")

# Same volume the serve side reads (checklist #6: renamed isometric-lora-vol →
# hk-tiles-lora-vol). server.py must point LoRA loads at this volume too.
lora_volume = modal.Volume.from_name("hk-tiles-lora-vol", create_if_missing=True)

# The training set ships into the image as a Modal mount (small: 40 PNG pairs).
TRAINING_SET_LOCAL = Path(__file__).parent / "training-set"
training_mount = modal.Mount.from_local_dir(
    TRAINING_SET_LOCAL, remote_path="/training-set"
)


def _load_pairs(root: Path) -> list[dict]:
    """Read manifest.json → validated list of {id,input_path,target_path,prompt}."""
    manifest = json.loads((root / "manifest.json").read_text())
    pairs = []
    for p in manifest.get("pairs", []):
        inp = root / p["input"]
        tgt = root / p["target"]
        if not inp.exists() or not tgt.exists():
            raise FileNotFoundError(f"pair {p['id']}: missing {inp} or {tgt}")
        # Light captioning: the trigger token carries the style; bucket/notes
        # give the model weak content grounding without over-conditioning.
        caption = f"{HK_TRIGGER_TOKEN}, {p.get('bucket', 'hong kong')} tile"
        if p.get("notes"):
            caption += f", {p['notes']}"
        pairs.append({"id": p["id"], "input": str(inp), "target": str(tgt), "prompt": caption})
    if not pairs:
        raise ValueError("manifest has zero pairs — author the 40-pair set first")
    return pairs


@app.function(
    image=image,
    gpu="H100",
    volumes={"/data": lora_volume},
    mounts=[training_mount],
    timeout=60 * 60 * 2,
)
def train(
    rank: int = 16,
    steps: int = 1500,
    lr: float = 1e-4,
    seed: int = 42,
) -> str:
    """Train the HK LoRA and save it to /data/loras/<HK_LORA_MODEL_ID>/."""
    import torch
    from diffusers import QwenImageEditPipeline
    from peft import LoraConfig, get_peft_model
    from PIL import Image

    root = Path("/training-set")
    pairs = _load_pairs(root)
    print(f"📚 {len(pairs)} training pairs; token={HK_TRIGGER_TOKEN!r}")

    torch.manual_seed(seed)
    pipe = QwenImageEditPipeline.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16)
    pipe.to("cuda")

    # Attach LoRA to the edit transformer (the DiT). Target the attention
    # projections — the standard image-edit LoRA surface.
    lora_cfg = LoraConfig(
        r=rank,
        lora_alpha=rank,
        target_modules=["to_q", "to_k", "to_v", "to_out.0"],
        lora_dropout=0.0,
    )
    transformer = get_peft_model(pipe.transformer, lora_cfg)
    transformer.train()
    transformer.print_trainable_parameters()

    optimizer = torch.optim.AdamW(
        [p for p in transformer.parameters() if p.requires_grad], lr=lr
    )

    # ── Training loop ────────────────────────────────────────────────────────
    # NOTE (validate before first real run): the exact latent encode + flow-
    # matching loss for Qwen-Image-Edit is model-specific. The shape is:
    #   1. encode input + target images → latents (pipe.vae)
    #   2. encode the prompt (with HK_TRIGGER_TOKEN) → text embeds
    #   3. sample a flow-matching timestep, build noisy latent
    #   4. transformer predicts the velocity/target conditioned on input latent
    #   5. MSE/flow-matching loss vs the target latent
    # Confirm against the current diffusers Qwen-Image-Edit training example;
    # the scaffold below is the correct structure, the loss line is the part
    # to verify.
    step = 0
    while step < steps:
        for pair in pairs:
            if step >= steps:
                break
            _input = Image.open(pair["input"]).convert("RGB")
            _target = Image.open(pair["target"]).convert("RGB")
            optimizer.zero_grad()
            loss = _edit_loss(pipe, transformer, _input, _target, pair["prompt"])
            loss.backward()
            optimizer.step()
            if step % 50 == 0:
                print(f"  step {step:4d}/{steps}  loss={loss.item():.4f}")
            step += 1

    out_dir = Path("/data/loras") / HK_LORA_MODEL_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    transformer.save_pretrained(str(out_dir))
    lora_volume.commit()
    print(f"✅ saved LoRA → {out_dir}  (serve with LORA_MODEL_ID={HK_LORA_MODEL_ID})")
    return HK_LORA_MODEL_ID


def _edit_loss(pipe, transformer, input_img, target_img, prompt):
    """Flow-matching edit loss. SEE the NOTE in train() — verify against the
    current diffusers Qwen-Image-Edit example before the first real run."""
    import torch

    device = "cuda"
    vae = pipe.vae
    with torch.no_grad():
        def encode(img):
            t = pipe.image_processor.preprocess(img).to(device, dtype=vae.dtype)
            return vae.encode(t).latent_dist.sample() * vae.config.scaling_factor
        input_lat = encode(input_img)
        target_lat = encode(target_img)
        prompt_embeds = pipe.encode_prompt(prompt, device=device, num_images_per_prompt=1)[0]

    noise = torch.randn_like(target_lat)
    t = torch.rand(target_lat.shape[0], device=device)
    noisy = (1 - t.view(-1, 1, 1, 1)) * target_lat + t.view(-1, 1, 1, 1) * noise
    model_in = torch.cat([noisy, input_lat], dim=1)  # edit = condition on input latent
    pred = transformer(model_in, t, encoder_hidden_states=prompt_embeds).sample
    return torch.nn.functional.mse_loss(pred.float(), (noise - target_lat).float())


@app.local_entrypoint()
def main(rank: int = 16, steps: int = 1500):
    """Pre-flight the training set locally, then launch the Modal run."""
    root = TRAINING_SET_LOCAL
    if not (root / "manifest.json").exists():
        raise SystemExit(
            "No training-set/manifest.json. Author the 40 pairs first "
            "(see inference/training-set/README.md + docs/design/aesthetic-spec.md)."
        )
    pairs = _load_pairs(root)
    print(f"pre-flight OK: {len(pairs)} pairs. launching Modal train "
          f"(rank={rank}, steps={steps}, token={HK_TRIGGER_TOKEN!r})…")
    model_id = train.remote(rank=rank, steps=steps)
    print(f"done. set LORA_MODEL_ID={model_id} on server.py to serve it.")
