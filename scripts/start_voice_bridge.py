"""Install and start the local macOS Vietnamese voice bridge at login."""

from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    executable = root / "apps/api/.venv/bin/uvicorn"
    if not executable.exists():
        raise SystemExit("Run 'make bootstrap' before starting the voice bridge")
    label = "com.aistorystudio.voicebridge"
    directory = Path.home() / "Library/LaunchAgents"
    directory.mkdir(parents=True, exist_ok=True)
    plist_path = directory / f"{label}.plist"
    payload = {
        "Label": label,
        "ProgramArguments": [
            str(executable),
            "studio_api.voice_bridge:app",
            "--host",
            "127.0.0.1",
            "--port",
            "7861",
        ],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {
            "PYTHONPATH": str(root / "apps/api/src"),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": "/tmp/ai-story-voice-bridge.log",
        "StandardErrorPath": "/tmp/ai-story-voice-bridge.log",
    }
    plist_path.write_bytes(plistlib.dumps(payload))
    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(plist_path)],
        check=False,
        capture_output=True,
    )
    subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], check=True)
    subprocess.run(["launchctl", "kickstart", "-k", f"{domain}/{label}"], check=True)
    print(f"Voice bridge started at http://127.0.0.1:7861/health ({plist_path})")


if __name__ == "__main__":
    main()
