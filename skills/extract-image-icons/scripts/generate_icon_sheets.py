#!/usr/bin/env python3
"""Generate source-guided icon asset sheets concurrently."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import mimetypes
import os
from pathlib import Path
import time
from typing import Any
from urllib import error, request


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1536x1024"
DEFAULT_QUALITY = "high"
DEFAULT_CODEX_URL = "https://chatgpt.com/backend-api/codex/responses"
DEFAULT_RESPONSES_MODEL = "gpt-5.5"
MAX_RESPONSE_BYTES = 64 * 1024 * 1024


def codex_auth_file() -> Path:
    return Path(os.getenv("CODEX_AUTH_FILE", "~/.codex/auth.json")).expanduser()


def codex_token() -> str | None:
    path = codex_auth_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        token = data.get("tokens", {}).get("access_token")
    except Exception:
        return None
    return token.strip() if isinstance(token, str) and token.strip() else None


def mime_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed if guessed and guessed.startswith("image/") else "image/png"


def image_data_url(path: Path) -> str:
    return f"data:{mime_for(path)};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def augment_prompt(job: dict[str, Any]) -> str:
    fields = job.get("fields") or {}
    sections = [f"Primary request: {str(job['prompt']).strip()}"]
    labels = {
        "use_case": "Use case",
        "scene": "Scene/background",
        "subject": "Subject",
        "style": "Style/medium",
        "composition": "Composition/framing",
        "lighting": "Lighting/mood",
        "palette": "Color palette",
        "materials": "Materials/textures",
        "text": "Text requirements",
        "constraints": "Constraints",
        "negative": "Avoid",
    }
    for key, label in labels.items():
        value = fields.get(key, job.get(key))
        if value:
            sections.append(f"{label}: {value}")
    return "\n".join(sections)


def load_jobs(path: Path) -> list[dict[str, Any]]:
    jobs = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_no}: {exc}") from exc
        if not isinstance(job, dict) or not str(job.get("prompt", "")).strip():
            raise ValueError(f"job {line_no} requires a non-empty prompt")
        if not isinstance(job.get("image"), str):
            raise ValueError(f"job {line_no} requires one source image path in 'image'")
        jobs.append(job)
    if not jobs:
        raise ValueError("no jobs found")
    return jobs


def resolve_output(out_dir: Path, value: str, index: int) -> Path:
    relative = Path(value or f"batch_{index:03d}.png")
    if relative.is_absolute():
        raise ValueError("job output must be relative to --out-dir")
    root = out_dir.resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"job output escapes --out-dir: {relative}")
    return target


def parse_sse_image(text: str) -> bytes:
    events = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    for event in events:
        if event.get("type") in {"response.failed", "error"}:
            raise RuntimeError(str(event.get("error") or event.get("message") or "image request failed"))
        item = event.get("item")
        if (
            event.get("type") == "response.output_item.done"
            and isinstance(item, dict)
            and item.get("type") == "image_generation_call"
            and isinstance(item.get("result"), str)
        ):
            return base64.b64decode(item["result"])
    for event in events:
        response_obj = event.get("response")
        output = response_obj.get("output") if isinstance(response_obj, dict) else None
        if not isinstance(output, list):
            continue
        for item in output:
            if isinstance(item, dict) and item.get("type") == "image_generation_call" and isinstance(item.get("result"), str):
                return base64.b64decode(item["result"])
    raise RuntimeError("no image payload found in Codex response")


def codex_generate(prompt: str, source: Path, model: str, size: str, quality: str, timeout: int) -> bytes:
    token = codex_token()
    if not token:
        raise RuntimeError("Codex OAuth token is unavailable")
    tool = {
        "type": "image_generation",
        "model": model,
        "size": size,
        "quality": quality,
        "output_format": "png",
    }
    body = {
        "model": os.getenv("EXTRACT_ICONS_RESPONSES_MODEL", DEFAULT_RESPONSES_MODEL),
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url(source), "detail": "auto"},
                ],
            }
        ],
        "instructions": "You are an image generation assistant.",
        "tools": [tool],
        "tool_choice": {"type": "image_generation"},
        "stream": True,
        "store": False,
    }
    req = request.Request(
        os.getenv("EXTRACT_ICONS_CODEX_RESPONSES_URL", DEFAULT_CODEX_URL),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": "extract-image-icons/1.0",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            chunks = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise RuntimeError("Codex image response exceeded 64 MB")
                chunks.append(chunk)
    except error.HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"Codex image request failed (HTTP {exc.code}): {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Codex image request failed: {exc.reason}") from exc
    return parse_sse_image(b"".join(chunks).decode("utf-8", errors="replace"))


def api_generate(prompt: str, source: Path, model: str, size: str, quality: str) -> bytes:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI API fallback requires the 'openai' Python package") from exc
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or None)
    with source.open("rb") as image_file:
        result = client.images.edit(
            model=model,
            image=image_file,
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
            output_format="png",
        )
    payload = result.data[0].b64_json
    if not payload:
        raise RuntimeError("OpenAI image response contained no base64 payload")
    return base64.b64decode(payload)


def generate_one(
    index: int,
    job: dict[str, Any],
    out_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    source = Path(job["image"]).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    output = resolve_output(out_dir, str(job.get("out", "")), index)
    if output.exists() and not args.force:
        raise FileExistsError(f"output exists: {output}")
    prompt = augment_prompt(job)
    model = str(job.get("model", args.model))
    size = str(job.get("size", args.size))
    quality = str(job.get("quality", args.quality))
    if args.dry_run:
        return {
            "job": index,
            "source": str(source),
            "output": str(output),
            "model": model,
            "size": size,
            "quality": quality,
            "backend": "codex-oauth" if codex_token() else "openai-api",
        }
    last_error = None
    for attempt in range(1, args.max_attempts + 1):
        try:
            started = time.time()
            if codex_token():
                raw = codex_generate(prompt, source, model, size, quality, args.timeout)
                backend = "codex-oauth"
            elif os.getenv("OPENAI_API_KEY"):
                raw = api_generate(prompt, source, model, size, quality)
                backend = "openai-api"
            else:
                raise RuntimeError("run 'codex login' or set OPENAI_API_KEY")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(raw)
            return {
                "job": index,
                "source": str(source),
                "output": str(output),
                "backend": backend,
                "seconds": round(time.time() - started, 2),
                "attempt": attempt,
            }
        except Exception as exc:
            last_error = exc
            if attempt < args.max_attempts:
                time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"job {index} failed after {args.max_attempts} attempts: {last_error}")


def doctor() -> int:
    try:
        import PIL  # noqa: F401
        pillow = True
    except ImportError:
        pillow = False
    try:
        import openai  # noqa: F401
        openai_sdk = True
    except ImportError:
        openai_sdk = False
    report = {
        "codex_oauth": bool(codex_token()),
        "codex_auth_file": str(codex_auth_file()),
        "openai_api_key": bool(os.getenv("OPENAI_API_KEY")),
        "openai_sdk": openai_sdk,
        "pillow": pillow,
        "ready": bool(codex_token()) or (bool(os.getenv("OPENAI_API_KEY")) and openai_sdk),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] and pillow else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="JSONL jobs produced by plan_icon_batches.py")
    parser.add_argument("--out-dir", help="Generated asset-sheet output directory")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--doctor", action="store_true")
    args = parser.parse_args()
    if args.doctor:
        return doctor()
    if not args.input or not args.out_dir:
        parser.error("--input and --out-dir are required unless --doctor is used")
    if not 1 <= args.concurrency <= 16:
        parser.error("--concurrency must be from 1 to 16")
    if not 1 <= args.max_attempts <= 10:
        parser.error("--max-attempts must be from 1 to 10")
    jobs = load_jobs(Path(args.input).expanduser().resolve())
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        future_map = {
            pool.submit(generate_one, index, job, out_dir, args): index
            for index, job in enumerate(jobs, 1)
        }
        for future in concurrent.futures.as_completed(future_map):
            index = future_map[future]
            try:
                result = future.result()
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except Exception as exc:
                failures.append({"job": index, "error": str(exc)})
                print(json.dumps(failures[-1], ensure_ascii=False), flush=True)
    summary = {"passed": not failures, "results": sorted(results, key=lambda x: x["job"]), "failures": failures}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
