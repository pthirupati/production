# Voice stack deploy (Whisper STT)

Interview hands-free listening uses **browser Web Speech** by default.
When `FIXITLAB_FASTER_WHISPER_URL` is set, the app advertises
`uses_server_stt: true` and `listenLive` records mic audio →
`POST /api/interviews/stt/transcribe/`.

## Start Whisper (optional profile)

```bash
docker compose -f docker-compose.voice.yml --profile voice up -d
```

Typical URL from the app droplet (adjust host/network as needed):

```bash
FIXITLAB_FASTER_WHISPER_URL=http://faster-whisper:8000
FIXITLAB_FASTER_WHISPER_API=openai
FIXITLAB_FASTER_WHISPER_MODEL=small
# Optional Indic path:
# FIXITLAB_INDIC_WHISPER_URL=http://indic-whisper:8000
```

These are passed through `docker-compose.app.yml` when present in
`.env.production`. Restart backend/celery after changing them.

## Verify

```bash
curl -sS https://<edge>/api/interviews/stt/config/ | jq .uses_server_stt
# → true when Whisper URL is configured
```

If the URL is set but Whisper is down, transcribe returns **503** with
`error_code=stt_unavailable` (fail closed — no silent empty `browser_sim`
while the FE thinks server STT is on).
