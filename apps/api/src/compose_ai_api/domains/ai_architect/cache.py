import hashlib
import json


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_cache_key(
    *,
    run_type: str,
    provider: str,
    model: str,
    prompt_checksum: str,
    context_hash: str,
    input_hash: str,
    output_schema_version: str,
    safety_policy_version: str,
) -> str:
    return stable_hash(
        {
            "runType": run_type,
            "provider": provider,
            "model": model,
            "promptChecksum": prompt_checksum,
            "contextHash": context_hash,
            "inputHash": input_hash,
            "outputSchemaVersion": output_schema_version,
            "safetyPolicyVersion": safety_policy_version,
        }
    )
