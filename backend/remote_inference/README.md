# Remote Inference (Colab Dev/Demo)

This folder contains a small FastAPI server meant to run on **Google Colab GPU**
and be exposed via **Cloudflare Quick Tunnel**.

It provides two endpoints:

- `POST /v1/sam/predict` (prompted Segment Anything mask)
- `POST /v1/hairfastgan/swap` (HairFastGAN hairstyle transfer)

## Quick start (Colab)

### 1) Install dependencies

```bash
cd mainproject/backend
pip install -r remote_inference/requirements.txt
pip install git+https://github.com/facebookresearch/segment-anything.git
```

HairFastGAN (code + deps + weights):

```bash
git clone https://github.com/AIRI-Institute/HairFastGAN
pip install -r HairFastGAN/requirements.txt

apt-get update && apt-get install -y git-lfs
git lfs install
git clone https://huggingface.co/AIRI-Institute/HairFastGAN HairFastGAN-weights
cd HairFastGAN-weights && git lfs pull && cd ..
rm -rf HairFastGAN/pretrained_models
cp -r HairFastGAN-weights/pretrained_models HairFastGAN/pretrained_models
```

Sanity-check the BiSeNet weight exists (HairFastGAN expects relative paths under its repo root):

```bash
ls -la /content/HairFastGAN/pretrained_models/BiSeNet/face_parsing_79999_iter.pth
```

Verify CUDA is available (Colab **Runtime → Change runtime type → GPU**):

```bash
python -c "import torch; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available())"
```

If `cuda_available` is `False`, you likely installed **CPU-only** PyTorch (often happens after running
`pip install -r HairFastGAN/requirements.txt`). Reinstall CUDA-enabled PyTorch, e.g. (Colab default CUDA):

```bash
pip install --upgrade --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

Download the SAM `vit_b` checkpoint:

```bash
wget -O sam_vit_b_01ec64.pth https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth
```

### 2) Run the server

```bash
export SAM_CHECKPOINT_PATH=/content/sam_vit_b_01ec64.pth
export HAIRFASTGAN_REPO_DIR=/content/HairFastGAN
export DEVICE=cuda

uvicorn remote_inference.app:app --host 0.0.0.0 --port 8000
```

If you see `Torch not compiled with CUDA enabled`, it means your Colab environment
has CPU-only PyTorch. Either:

- switch runtime to **GPU** and reinstall CUDA-enabled torch, or
- set `DEVICE=cpu` (will be slower).

Optional API key (recommended even for demos):

```bash
export INFERENCE_API_KEY="change-me"
```

Optional (recommended): warm up the heavy models **locally** (avoids tunnel timeouts on the first request):

```bash
curl -X POST http://localhost:8000/v1/hairfastgan/warmup
curl -X POST http://localhost:8000/v1/sam/warmup
```

### 3) Expose it (Quick Tunnel)

```bash
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
chmod +x cloudflared
./cloudflared tunnel --url http://localhost:8000
```

Copy the public `https://...trycloudflare.com` URL and set it in your backend:

```bash
REMOTE_INFERENCE_URL=https://<your-tunnel>.trycloudflare.com
REMOTE_INFERENCE_API_KEY=change-me
```
