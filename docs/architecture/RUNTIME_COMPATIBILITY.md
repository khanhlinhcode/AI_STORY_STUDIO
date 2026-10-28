# Runtime compatibility and machine audit

Audit date: 2026-10-27 (Asia/Ho_Chi_Minh).

| Item | Observed |
| --- | --- |
| Hardware | Apple M1, 8 GiB unified memory |
| OS | macOS 27.0.1, arm64 |
| Free disk at audit | approximately 114 GiB |
| Node/npm | 22.23.2 / 10.9.8 |
| Python/uv | 3.12.10 / 0.12.8 |
| Docker/Compose | 29.9.2 / 5.6.1 |
| FFmpeg | 9.0.2, installed through Homebrew |
| Ollama | 0.40.11, running as a Homebrew service; `qwen3:4b` selected, smaller test models also downloaded |
| Voice | macOS `say` with Apple Linh `vi_VN` via a local launch agent |

The 8 GiB machine falls below the plan's 32 GiB local image-generation recommendation. The active local setup uses Ollama for story scripts, the source NASA photograph for Autopilot visuals, and Apple Linh for Vietnamese narration. Manual topics still use fixture images. Preview videos remain blocked by QC from publication until image rights, factual details, voice quality and child safety have been reviewed. No LoRA checkpoint has been trained or installed.

