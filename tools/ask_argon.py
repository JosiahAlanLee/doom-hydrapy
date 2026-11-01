#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""ask_argon.py — Zero-Dependency Mac/4090 Codex <-> Gemini ("Argon") Bridge CLI.

Drop this file into `tools/ask_argon.py` in `doom-hydrapy`.
Uses only the Python 3 standard library (`urllib.request`, `json`, `base64`, `pathlib`)
so Codex can call it immediately on macOS or the Linux 4090 render box without installing
any third-party packages.

Quick Start:
  1. Export your Gemini API key once in the terminal where Codex runs:
       export GEMINI_API_KEY="your-api-key"
     (Or save it to `~/.gemini_api_key` so every subshell picks it up automatically.)

  2. Codex can invoke Argon from its shell with any prompt plus local code, logs, or
     rendered 4090 screenshots (`.png`, `.jpg`, `.json`, `.py`, `.c`, `.zs`, `.fp`, `.md`):
       python3 tools/ask_argon.py \
         "Critique these UZDoom 5.0.3 tower screenshots and generate a GLDEFS + .fp green-line shader lump" \
         -f modern_tower/prove_tower.py \
         -f modern_tower/verification.json \
         -f modern_tower/crown-down.png \
         --extract-dir handoff/argon_out

Features:
  - Multimodal Inspection: Automatically base64-encodes `.png`/`.jpg`/`.webp` screenshots
    into `inline_data` parts so Argon can visually inspect 4090 renders, and embeds text/code
    files (`.py`, `.c`, `.zs`, `.fp`, `.glsl`, `.json`, `.md`, `.log`) inline with line numbers.
  - Pre-Seeded NULLRUN Context: Injects a built-in system prompt summarizing the entire
    `doom-hydrapy` / NULLRUN / `modern_tower` (UZDoom 5.0.3 UDMF) / `rogue/optics.py` /
    `openai/math` context so Argon has full continuity from the first call.
  - Rolling Multi-Turn Memory: Persists conversation turns in `handoff/argon_session.json`
    (resettable anytime with `--reset`).
  - Automatic File Extraction: Parses any fenced block header of the form
    ```lang:relative/path.ext or `# FILE: relative/path.ext` and writes the extracted files
    into `--extract-dir` (default: `handoff/argon_out/`) for Codex to inspect and copy.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_MODEL = os.environ.get("ARGON_GEMINI_MODEL", "gemini-3.1-pro-preview")
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

SYSTEM_CONTEXT = """You are Argon (Gemini), collaborating directly with Codex on Josiah Alan-Lee's `doom-hydrapy` / NULLRUN project (running across a Mac and a Linux RTX 4090 render machine).

Project Context & Architectural State:
1. Repository (`JosiahAlanLee/doom-hydrapy`):
   - Native 640x400 (`doom-ipc-2x`) 7-tier roguelike campaign (`native_nullrun.py`, `rogue/server.py`, `rogue/optics.py`).
   - 3 Seeded Worlds (`seed % 3`): Drowned Records (96 BPM), Switchyard Chapel (128 BPM), After Hours Pavilion (112 BPM).
   - 14 Book Demons from *Pseudomonarchia Escalationum* (`BOSSES.md`, `rogue_boss.c`) across 4 ritual-ring binding families (`Repetiel`, `Calmor`, `Probator`, `Jurisiel`).
   - Gloamwood horrors (`GLOAMWOOD.md`): `The Hollow` (frustum-pinned inside 90-deg FOV & LOS; crawls/flanks when unwatched) and `Stone ReDead` (0.8s mask warning -> root grapple).
   - 4 Argon encounter families (`ARGON_CAMPAIGN.md`): `Surveyor` (A: Tripod, B: Gimbal; 35-tic warning countdown), `Wire Shambler` (A: Ballast Husk, B: Cable Tower), `Threshold Mimic` (A: Lintel Door, B: False Exit), and `Vore Spindle` (A: Pendulum, B: Ceiling Lurker).
   - `rogue/optics.py` (`SURVEYOR_OPTICS.md`): Green central-difference edge filter, 35-segment Surveyor warning countdown bar (1..27 amber, 28..35 steady red), converging brackets outside the crosshair, protected HUD/title/crosshair masks, and automatic `RAW` fallback.
   - `modern_tower/` (PR #15): UZDoom 5.0.3 UDMF (`zdoom` namespace) 3D tower prototype (`build_tower.py`, `build_kit_variants.py`, `prove_tower.py`) with 480-unit vertical atrium, 3D floors (`Sector_Set3DFloor`, special 160), Z-up to Y-up OBJ `MODELDEF` adapter, and headless `xvfb-run` ZScript `NullTowerProbe` verification.

Collaboration Contract with Codex:
- Be concise, mathematically rigorous, and engineering-first.
- Never fabricate math claims; verify numerical invariants (e.g., Jacobian determinants, FFT positivity, UV bounds, UDMF/ZScript/GLDEFS syntax).
- Always protect playability invariants: preserve crosshair aiming deadzones, HUD legibility, and `RAW` fallback paths.
- When emitting complete files for Codex to extract, format the fenced code block header as:
  ```python:path/to/file.py
  or include `# FILE: path/to/file.ext` (or `// FILE: path/to/file.ext`) on the first line inside the code block.
"""


def _resolve_api_key(explicit_key: str | None) -> str:
    if explicit_key:
        return explicit_key.strip()
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_name, "").strip()
        if val:
            return val
    for key_file in (Path.home() / ".gemini_api_key", Path(".gemini_api_key")):
        if key_file.is_file():
            val = key_file.read_text(encoding="utf-8").strip()
            if val:
                return val
    raise RuntimeError(
        "No Gemini API key found. Set GEMINI_API_KEY in your environment or save it to ~/.gemini_api_key."
    )


def _checked_key(key: str) -> str:
    key = key.strip()
    if not key or key.upper() in {"YOUR_GEMINI_API_KEY", "YOUR_API_KEY", "YOUR-API-KEY"}:
        raise RuntimeError("A real Gemini API key is required; the example placeholder is not a key.")
    # Reject clipboard mistakes before urllib can include the header value in
    # an exception. Never echo credential contents in a diagnostic message.
    if not re.fullmatch(r"[A-Za-z0-9_.-]{20,512}", key):
        raise RuntimeError("Credential file must contain one API-key token, without commands or whitespace.")
    return key


def _build_file_parts(file_paths: list[str]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    total = 0
    for raw_p in file_paths:
        p = Path(raw_p)
        if not p.is_file():
            raise ValueError(f"Attachment must be an existing regular file: {raw_p}")
        size = p.stat().st_size
        total += size
        if size > 8 * 1024 * 1024 or total > 24 * 1024 * 1024:
            raise ValueError("Attachments exceed the 8 MiB per-file or 24 MiB total limit.")
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS:
            mime = mimetypes.guess_type(str(p))[0] or "image/png"
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            parts.append({"text": f"\n[Attached Image: {raw_p}]\n"})
            parts.append({"inline_data": {"mime_type": mime, "data": b64}})
        else:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                content = f"<Error reading {raw_p}: {exc}>"
            parts.append(
                {
                    "text": f"\n=== FILE: {raw_p} ===\n{content}\n=== END FILE: {raw_p} ===\n"
                }
            )
    return parts


def _extract_code_files(response_text: str, extract_dir: Path) -> list[Path]:
    """Extract fenced code blocks tagged with `lang:path/to/file` or `# FILE: path/to/file`."""
    written: list[Path] = []
    root = extract_dir.resolve()
    pattern = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
    for match in pattern.finditer(response_text):
        header = match.group(1).strip()
        body = match.group(2)
        target_rel: str | None = None

        if ":" in header:
            _, candidate = header.split(":", 1)
            candidate = candidate.strip()
            if candidate and not candidate.startswith("/"):
                target_rel = candidate

        if not target_rel:
            first_line = body.splitlines()[0].strip() if body.splitlines() else ""
            m_file = re.match(r"^(?:#|//|--|/\*)\s*FILE:\s*([A-Za-z0-9_./-]+)", first_line)
            if m_file:
                target_rel = m_file.group(1).strip()

        if target_rel:
            safe_rel = Path(target_rel)
            if safe_rel.is_absolute() or ".." in safe_rel.parts:
                continue
            out_path = (root / safe_rel).resolve()
            if not out_path.is_relative_to(root) or out_path == root:
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Generated replies cannot overwrite reviewed files or prior takes.
            with out_path.open("x", encoding="utf-8") as output:
                output.write(body)
            written.append(out_path)
    return written


def call_gemini(
    prompt: str,
    files: list[str],
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    session_file: Path | None = None,
    reset_session: bool = False,
    temperature: float = 0.2,
    dry_run: bool = False,
) -> dict[str, Any]:
    history: list[dict[str, Any]] = []
    if session_file and session_file.is_file() and not reset_session:
        try:
            history = json.loads(session_file.read_text(encoding="utf-8"))
        except Exception:
            history = []

    user_parts = _build_file_parts(files)
    user_parts.append({"text": prompt})
    history.append({"role": "user", "parts": user_parts})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_CONTEXT}]},
        "contents": history,
        "generationConfig": {
            "temperature": temperature,
        },
    }

    if dry_run:
        return {
            "status": "dry_run",
            "model": model,
            "turns_in_session": len(history),
            "parts_in_latest_turn": len(user_parts),
            "payload_preview_bytes": len(json.dumps(payload)),
        }

    key = _checked_key(_resolve_api_key(api_key))
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise ValueError("Invalid Gemini model name")
    url = f"{API_BASE}/{model}:generateContent"
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resp_json = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API HTTP {exc.code}: {err_body.replace(key, '[REDACTED]')}") from None

    candidates = resp_json.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"No candidates returned by Gemini API: {resp_json}")

    model_parts = candidates[0].get("content", {}).get("parts", [])
    reply_chunks = [p.get("text", "") for p in model_parts if "text" in p]
    reply_text = "\n".join(reply_chunks).strip()

    # Save text-only history to keep the session file compact across turns
    compact_user_parts = [
        p if "inline_data" not in p else {"text": "[Image attached in prior turn]"}
        for p in user_parts
    ]
    history[-1] = {"role": "user", "parts": compact_user_parts}
    history.append({"role": "model", "parts": [{"text": reply_text}]})

    if session_file:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(history[-16:], indent=2), encoding="utf-8")

    return {
        "status": "ok",
        "model": model,
        "reply": reply_text,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bridge CLI for Codex on Mac/4090 to consult Argon (Gemini) with local files and screenshots."
    )
    parser.add_argument("prompt", nargs="?", default="", help="Prompt or question for Argon.")
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        default=[],
        help="Attach a local file (code, JSON, log, or PNG/JPG screenshot). Repeatable.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument("--api-key", default=None, help="Explicit Gemini API key (overrides env).")
    parser.add_argument(
        "--session",
        default="handoff/argon_session.json",
        help="Path to rolling multi-turn session JSON (default: handoff/argon_session.json).",
    )
    parser.add_argument("--reset", action="store_true", help="Clear prior session history before this call.")
    parser.add_argument(
        "--extract-dir",
        default="handoff/argon_out",
        help="Directory to extract tagged code blocks into (default: handoff/argon_out).",
    )
    parser.add_argument(
        "--out",
        default="handoff/ARGON_LATEST_REPLY.md",
        help="Write the full Markdown response to this file (default: handoff/ARGON_LATEST_REPLY.md).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate file attachments and payload without network call.")
    args = parser.parse_args(argv)

    prompt_text = args.prompt.strip()
    if not prompt_text and not sys.stdin.isatty():
        prompt_text = sys.stdin.read().strip()
    if not prompt_text:
        parser.error("Please provide a prompt string or pipe prompt text via stdin.")

    res = call_gemini(
        prompt=prompt_text,
        files=args.file,
        model=args.model,
        api_key=args.api_key,
        session_file=Path(args.session) if args.session else None,
        reset_session=args.reset,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(json.dumps(res, indent=2))
        return 0

    reply = res["reply"]
    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(reply + "\n", encoding="utf-8")

    extracted = []
    if args.extract_dir:
        extracted = _extract_code_files(reply, Path(args.extract_dir))

    print(reply)
    if extracted:
        print("\n--- Extracted Files ---", file=sys.stderr)
        for ep in extracted:
            print(f"  [wrote] {ep}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
