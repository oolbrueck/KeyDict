from __future__ import annotations

import requests

from .config import ApiConfig


class TranscriptionError(RuntimeError):
    pass


def transcribe(wav_data: bytes, config: ApiConfig) -> str:
    fields: dict[str, str] = {"model": config.model}
    if config.language:
        fields["language"] = config.language
    if config.prompt:
        fields["prompt"] = config.prompt
    try:
        response = requests.post(
            config.url,
            headers={"Authorization": f"Bearer {config.api_key}"},
            data=fields,
            files={"file": ("recording.wav", wav_data, "audio/wav")},
            timeout=config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise TranscriptionError(f"Verbindung zum Transkriptionsdienst fehlgeschlagen: {exc}") from exc
    if not response.ok:
        if response.status_code in {401, 403}:
            raise TranscriptionError(
                "API-Authentifizierung fehlgeschlagen. Pruefe [api].api_key und ob der Key Zugriff auf das Modell hat."
            )
        detail = response.text.strip()[:500]
        raise TranscriptionError(f"API-Fehler {response.status_code}: {detail}")
    try:
        payload = response.json()
    except requests.JSONDecodeError:
        text = response.text.strip()
    else:
        text = payload.get("text", "") if isinstance(payload, dict) else ""
    if not isinstance(text, str) or not text.strip():
        raise TranscriptionError("Die API-Antwort enthaelt keinen Text")
    return text.strip()
