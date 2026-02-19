# Deployment Guide — Sovereign AI Scientist

## Prerequisites

- **Docker** installed and running
- **EigenCloud CLI** ([install](https://tools.eigencloud.xyz))
- **EigenAI API Key** — free 1M tokens at [determinal.eigenarcade.com](https://determinal.eigenarcade.com)

---

## Step 1: Get EigenAI Credits

1. Go to [https://determinal.eigenarcade.com](https://determinal.eigenarcade.com)
2. Connect your X (Twitter) account
3. Copy your API key

---

## Step 2: Install EigenCloud CLI

```bash
curl -fsSL https://tools.eigencloud.xyz | bash
```

---

## Step 3: Build the Docker Image

```bash
git clone https://github.com/YOUR_USERNAME/sovereign-ai-scientist
cd sovereign-ai-scientist

docker build -t sovereign-scientist:v1 .
```

---

## Step 4: Deploy to EigenCompute TEE

```bash
ecloud compute app deploy \
  --image-ref sovereign-scientist:v1 \
  --env EIGENAI_API_KEY=your_key_here \
  --port 8080
```

Your agent is now running inside an EigenCompute Trusted Execution Environment. Intel TDX attestation proves the exact committed code is what's running — no tampering possible.

---

## Step 5: Open the Dashboard

Navigate to the URL provided by `ecloud compute app deploy`. The dashboard lets you:

1. **Define a research program** — enter a topic and seed
2. **Watch the agent execute** — 4 milestones: Ideation → Design → Analysis → Writing
3. **Inspect the audit trail** — every EigenAI call logged with SHA256 hashes
4. **Verify any step** — re-executes the same prompt on EigenAI, confirms output matches bit-for-bit

---

## Architecture

```
EigenCompute TEE
├── FastAPI server (server.py)
├── Sovereign Scientist agent (agent/scientist.py)
├── Dashboard UI (frontend/index.html)
│
├── All LLM calls ──→ EigenAI (deterministic, seed-pinned)
└── All outputs ──→ SHA256 hashed + audit logged
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/start` | Start research pipeline. Body: `{"topic": "...", "seed": 42}` |
| GET | `/api/status` | Poll progress, milestones, audit log |
| GET | `/api/results` | Full pipeline results after completion |
| POST | `/api/verify/{step_id}` | Re-execute a step on EigenAI, compare hashes |
| GET | `/api/audit` | Complete audit log with full prompts/outputs |
| GET | `/api/health` | Health check |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EIGENAI_API_KEY` | required | Your EigenAI API key |
| Model | `gpt-oss-120b-f16` | EigenAI model (also supports `qwen3-32b-128k-bf16`) |
| Seed | `42` | Deterministic seed (configurable via dashboard) |
| Port | `8080` | Server port |
