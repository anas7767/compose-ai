from __future__ import annotations

from getpass import getpass
from pathlib import Path

TEXT_MODEL = "gemini-3.5-flash"
IMAGE_MODEL = "gemini-3.1-flash-image"
REQUIRED_VALUES = {
    "AI_PROVIDER": "gemini",
    "GEMINI_TEXT_MODEL": TEXT_MODEL,
    "GEMINI_IMAGE_MODEL": IMAGE_MODEL,
}


def main() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    api_key = _read_secret()
    values = {**REQUIRED_VALUES, "GEMINI_API_KEY": api_key}
    _upsert_env_file(env_path, values)
    print("Gemini environment updated in apps/api/.env.")
    print("Updated variables: AI_PROVIDER, GEMINI_API_KEY, GEMINI_TEXT_MODEL, GEMINI_IMAGE_MODEL.")


def _read_secret() -> str:
    api_key = getpass("Paste Gemini API key (hidden input): ").strip()
    if not api_key:
        raise SystemExit("Gemini API key missing")
    return api_key


def _upsert_env_file(env_path: Path, values: dict[str, str]) -> None:
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    remaining = dict(values)
    output: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue

        key, _separator, _value = line.partition("=")
        key = key.strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)

    if remaining and output and output[-1].strip():
        output.append("")
    for key, value in remaining.items():
        output.append(f"{key}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
