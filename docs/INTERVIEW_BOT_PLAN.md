# P2 — Interview Bot: Full Human-Like Vision (FREE)

Design-only planning doc. No code changes other than this file.

**Hard constraint:** 100% free. No paid LLM/STT/TTS APIs (no OpenAI / Anthropic /
ElevenLabs / Polly). Voice = browser-native (Web Speech API) **or** self-hosted
free local STT (Vosk / whisper.cpp). The conversation/scoring engine stays the
existing rule-based `interview_ai.py` (no LLM cost).

---

## STEP 1 — What EXISTS today (concrete map)

### Backend `apps/interviews/`

**Models** (`models.py`) — the data model is essentially complete:
- `InterviewPlanTier` (12) — subscription tiers (price, interviews/month, max_rounds, voice/practical/cert flags).
- `CandidateProfile` (34) — resume_file/resume_text/resume_parsed (JSON), primary/secondary tech, experience_level, years, company, target_role, **`voice_id`/`voice_locale`** (66–67).
- `InterviewCampaign` (77) — full cycle, `round_count`, status, `profile_snapshot`, `is_sample`, `overall_score`.
- `InterviewRound` (135) — `round_type` (technical/manager/hr/deep_dive/leadership), `duration_minutes`, `extension_minutes`/`max_extension_minutes` (167–168), `pass_threshold` (179), `persona_name`/`persona_voice_id` (181–182), `invite_token` (183), **`questions_asked`/`strong_answers_streak`/`difficulty_level`** (185–187), **`av_compliant`/`av_warning_started_at`** (188–189), `practical_lab_session_id` (190), `schedule_deadline` (171).
- `InterviewQuestion` (202) — bank with `category` (incl. **itil, sla, casual, tricky, practical, system_design**, 205–216), `difficulty`, `follow_ups`, `expected_keywords`, **`practical_config`** (234, holds `scenario_slug`/`setup`), `discussion_prompts`.
- `InterviewMessage` (248) — transcript (role, content, message_type, question FK, score, metadata).
- `InterviewReport` (280) — per-round feedback (technical/communication/problem_solving/practical/presence/resume_alignment scores, strengths, improvements, summary, study_plan, question_breakdown).
- `InterviewCertificate` (308) — `certificate_id`, holder, rounds_cleared, expires_at, **`linkedin_share_text`** (330).
- `InterviewEntitlement` (339) — credits, `sample_interview_used`, admin-granted-free.
- `InterviewPlatformSettings` (370) — singleton; **`av_grace_seconds=300`** (378), **`schedule_window_hours=48`** (379), `default_pass_threshold`, **`voice_engine="browser"`** (382), maintenance.
- `InterviewVoiceOption` (402) — admin-managed browser voices: India/UK/US, gender, **`browser_voice_hint`** (matches `speechSynthesis` voice name), pitch, rate, is_default.
- `InterviewAdminJoinRequest` (437) — admin observer w/ candidate approval.

**Live (FREE) services — in use:**
- `services/interview_ai.py` — **THE live engine.** Rule-based reply generation (`generate_interviewer_reply`, 310) + scoring (`compute_answer_scores`, 390). Keyword/STAR banks, topic detection, adaptive reactions (strong/weak/brief/skipped, strong_streak), per-topic follow-ups (k8s/docker/aws/terraform/…), round nudges (hr/manager/itil/sla). 100% free, no API.
- `services/engine.py` — **orchestration in use.** `start_round` (60, persona intro templates incl. ITIL/SLA + AV-required line), `ask_next_question` (151, pulls from bank via selector), `submit_answer` (188, scores → `interview_ai` reply → next question; **difficulty bumps after streak≥5**, 213), `extend_round` (272, +10m capped at max_extension), `record_av_status` (290, **warn → 300s grace → auto-end**), `end_round` (319, builds report, unlocks next, finalizes campaign + cert, emails results).
- `services/scoring.py` — wraps `interview_ai.compute_answer_scores` (free); `command_validated` adds +15 (33).
- `services/question_selector.py` — adaptive selection w/ difficulty window + streak boost (39–42), sqlite JSON-contains fallback.
- `services/campaign_builder.py` — `ROUND_PLAN` for **3/4/5 rounds** (11; Technical 45m / Manager 30m / HR 20m + deep_dive/leadership), personas + default voices, `unlock_next_round` sets **48h `schedule_deadline`** (77).
- `services/resume_parser.py` — free PDF (pypdf) + regex skill/years/company/role extraction; `build_profile_from_inputs` fallback when no file.
- `services/certificate.py` — issues `FIXIT-INT-…` cert on full-campaign pass, 365-day expiry, `linkedin_share_text`, emails it.
- `services/practical_lab.py` — bridges a `practical` question's `scenario_slug` to a real `LabSession` via `apps.labs.sessions.start_lab_session` (the hands-on path **exists**).
- `services/sample_interview.py` — one-time free 10-min sample (1 round, no cert).
- `services/voice_service.py` — **FREE voice config** (`voice_config_payload`, 9): `stt_provider="browser"`, `tts_provider="browser"`, `uses_paid_apis: False`, returns admin voices or 6 defaults (India/UK/US × M/F).
- `services/notify.py`, `services/entitlements.py`, `services/interview_settings.py`, `services/interview_types.py` (rich persona addenda + eval weights for behavioral/system_design/live_coding/devops_debug/sre_oncall — **defined but only consumed by the unused LLM path**).

**Removed paid scaffolding (Phase 0 — deleted/hard-disabled):**
- `services/llm.py` — deprecated shim → re-exports the free `interview_ai.generate_interviewer_reply`.
- ~~`services/llm_engine.py`~~ / ~~`services/engine_v2.py`~~ — **deleted.** No Anthropic path remains.
- `services/tts_service.py` / `services/stt_service.py` — always return `provider="browser"` unless `INTERVIEW_STT_ENGINE=vosk` (optional local hook, default off). No ElevenLabs/Polly/Whisper API calls.
- `services/conversation/` — **new free conversational engine** (spaCy + sklearn TF-IDF + rule policy): `normalize` → `analyze_answer` → `decide_next_move` → `generate_follow_up_question`. Wired into `question_generator` and `engine.submit_answer` campaign memory.

**Conversational engine stack (100% offline):**
- STT repair dictionary (`conversation/normalize.py`) before analysis.
- `AnswerAnalysis` via spaCy `en_core_web_sm` (optional) + TF-IDF relevance.
- `CampaignMemory` persisted in `round.metadata["conversation"]["campaign_memory"]`.
- Anti-gaming semantic scorer in `conversation/scorer.py` (capped length reward).

**Routing / API** (`urls.py`): sample, plans, entitlement, profile (+resume), voices, campaigns, rounds (schedule/start/message/av/extend/end/practical-lab/ical), join-by-token, cert verify, billing, GDPR export/delete, admin observer join-requests, tts/stt config+exec.

**Views** (`views.py`) — all endpoints defensively guard against 500s and run the **free engine** (40). `InterviewRoundStartView` (387) does maintenance gating + idempotent start; `InterviewRoundMessageView` (480) is the answer loop; `InterviewRoundAvStatusView` (525) the anti-cheat heartbeat.

### Frontend `frontend/src/`

- `pages/interviews/InterviewSetup.jsx` — 3-step wizard: **Resume upload (optional)** + **voice accent select** (174), Career fields, Rounds (3/4/5 + AV-required notice). **Saves profile + creates campaign.**
- `pages/interviews/InterviewRoom.jsx` — **the calling screen** (891 lines). Preflight w/ consent + AV self-test (mic meter 570, video preview, **virtual background picker**), proactive `getUserMedia` like Meet (78), serialized media acquisition (155). In-room: candidate video tile + mic/cam toggles, **bot tile = "Browser voice (free)"** label only (775, no bot video — matches "bot mic-only"), live transcript, type/voice answer, **extend +10m, reschedule, end, AV heartbeat every 30s** (314), practical-lab launch, download local recording.
- `hooks/useInterviewVoice.js` — `speak()` (server TTS→browser fallback) + `listen()` (Whisper→browser fallback). **Loads `/voices/`, `/tts/config/`, `/stt/config/` → resolves to browser providers** when unkeyed.
- `hooks/useVirtualBackground.js` — `VIRTUAL_BACKGROUNDS` + MediaPipe-style segmentation (blur/color/gradient). **Virtual background exists.**
- `components/interviews/InterviewVideoPreview.jsx` — video + background picker.
- `pages/interviews/InterviewCampaign.jsx` — round list, **schedule within 48h** UI (162), start/reschedule.
- `pages/interviews/InterviewReport.jsx` — per-round scorecard, strengths/improve, study plan, **LinkedIn share + print PDF + iCal**.
- `pages/interviews/InterviewHub.jsx`, `InterviewLanding.jsx`, `api/interviews.js`.

### Voice/WS infra (BIG de-risker)
- **Channels + Redis + Daphne are already in production** (`requirements.txt` 16–20; `config/settings.py` 50/151/311; `config/asgi.py`). `asgi.py` uses `ProtocolTypeRouter` with a `websocket` route guarded by `JWTAuthMiddleware` (token via `?token=<jwt>` query string).
- **A proven streaming consumer pattern exists**: `apps/terminal/consumers.py` (`AsyncWebsocketConsumer`, per-user connection caps, `database_sync_to_async`) + `apps/terminal/routing.py`. The interview voice loop can copy this pattern almost verbatim.

---

## STEP 2 — Gap analysis vs target vision

Legend: ✅ exists · 🟡 partial · ⬜ missing. "File" = where the change lands.

| # | Capability | State | Evidence / gap | File to change |
|---|---|---|---|---|
| 1 | Resume **upload** | ✅ | Setup step 0 + `CandidateProfileView.put` parses PDF/DOCX | — |
| 2 | Resume **score + tips** shown to candidate | ⬜ | `parse_resume_text` extracts skills/years but no score/tips surfaced pre-interview | `services/resume_parser.py` (add `score_resume`), `views.py` (return in profile), `InterviewSetup.jsx` (render) |
| 3 | Pre-interview instructions | ✅ | Preflight list + consent (`InterviewRoom.jsx` 531) + `SAMPLE_INSTRUCTIONS` | — |
| 4 | Calling screen: candidate video+mic **required** | ✅ | Begin gated on `micOn && cameraOn && consent` (664) | — |
| 5 | Bot is **mic-only** (no bot video) | ✅ | Bot tile is a "Browser voice (free)" badge (775) | — |
| 6 | **Selectable/changeable** TTS voice | 🟡 | Selectable at setup (`voice_id`); **not changeable inside the room** | `InterviewRoom.jsx` (voice dropdown in header), `useInterviewVoice.js` |
| 7 | Realtime voice loop: free STT + browser TTS | 🟡 | TTS works (browser). STT is **broken at the call site** — `voiceAnswer()` calls `listen(profile.locale)` but hook is `listen(mediaStream, options)` (InterviewRoom 391); push-to-talk only, no stream passed | `InterviewRoom.jsx`, `useInterviewVoice.js` |
| 8 | **Barge-in** (interrupt bot while it speaks) | ⬜ | No VAD; `speak()` not cancelled when user starts talking | `useInterviewVoice.js` (`cancelSpeech` on mic energy), `InterviewRoom.jsx` |
| 9 | Natural adaptive convo, follow-ups on candidate's OWN answer | 🟡 | `interview_ai.py` reacts to quality/topic/STAR, but follow-ups are from **fixed banks**, not the candidate's literal words | `services/interview_ai.py` |
| 10 | Gets harder after ~5 good answers | ✅ | `strong_answers_streak>=5 → difficulty+1` (engine.py 213; selector 39) | — |
| 11 | Trick questions | ✅ | `category="tricky"` in bank + rotation (`question_selector.round_category_mix`) | — (need content) |
| 12 | Start discussions, casual/fun, never robotic "good answer" | 🟡 | Banks avoid "good answer", but variety is finite → repeats in long rounds | `services/interview_ai.py` (templating with answer fragments) |
| 13 | Practical: candidate types commands/code, bot validates | 🟡 | `practical_lab.py` opens a real lab; `command_validated` flag adds score, **but nothing auto-validates** the candidate's commands against the scenario checker inline | `InterviewRoom.jsx`, `views.py` (validate endpoint), `services/practical_lab.py` |
| 14 | Configurable 3–5 rounds w/ durations | ✅ | `ROUND_PLAN` (campaign_builder 11): Tech 45 / Mgr 30 / HR 20 | — |
| 15 | +10m extend | ✅ | `extend_round` (engine 272), UI button (Room 699) | — |
| 16 | **Skip-on-silence to use the time** | ⬜ | No silence timer; `_target_question_count` is fixed; no auto-advance on no-answer | `services/engine.py`, new WS consumer, `InterviewRoom.jsx` |
| 17 | ITIL / SLA coverage | ✅ | Categories `itil`/`sla` + manager nudges (interview_ai 133) | — (need content) |
| 18 | Anti-cheat: mute/cam-off → warn → auto-exit 5 min, instructed upfront | ✅ | `record_av_status` (engine 290), 30s heartbeat (Room 314), preflight notice | — |
| 19 | Per-round feedback | ✅ | `InterviewReport` + `InterviewReport.jsx` | — |
| 20 | **Emailed** results | ✅ | `send_notification_email` in `end_round` (engine 393) | — |
| 21 | Pass → unlock next round | ✅ | `unlock_next_round` (campaign_builder 68) | — |
| 22 | Schedule next within 48h + email + join link | ✅ | `schedule_deadline` + `InterviewRoundScheduleView` emails join URL (views 367) | — |
| 23 | LinkedIn-shareable certificate after all rounds | ✅ | `issue_certificate` + share text + `InterviewReport.jsx` LinkedIn btn | — |
| 24 | **Self-training from transcripts** | ⬜ | `InterviewQuestion.times_asked/avg_score` exist but nothing learns from `InterviewMessage` transcripts | new `management/commands/train_from_transcripts.py`, `services/interview_ai.py` |

**Net:** the data model, scheduling, anti-cheat, scoring, reports, certs, practical-lab bridge, and browser TTS are **done**. The real gaps are: (7/8) a working streaming STT + barge-in loop, (16) skip-on-silence pacing, (13) inline command validation, (2) resume scoring UI, (9/12) more natural follow-ups, (24) transcript self-training, and (6) in-room voice switching.

---

## STEP 3 — Phased build plan (P2.1 … P2.9)

Each increment is independently shippable and keeps CI green. Estimates are
rough engineer-days. **No paid APIs in any phase.**

| Phase | Goal | Key files | Est |
|---|---|---|---|
| **P2.1** | **Fix the browser voice loop** (highest ROI, no infra). Correct `voiceAnswer()` → `listen(mediaStream, {locale,onInterim})`, pass the live stream, show interim transcript, auto-submit on final. Add in-room **voice switcher** dropdown (cap. #6,#7). | `frontend/src/pages/interviews/InterviewRoom.jsx`, `frontend/src/hooks/useInterviewVoice.js` | 1.5 |
| **P2.2** | **Barge-in + skip-on-silence (client-side first).** Use existing mic-energy meter (Room 110) as a VAD: if candidate speaks while bot is speaking → `cancelSpeech()`. If silence > N s on an open question → post empty answer (engine already handles `quality="skipped"`, 342) so the round keeps moving and "uses the time". (cap. #8,#16) | `InterviewRoom.jsx`, `useInterviewVoice.js`, `services/engine.py` (silence-aware target count) | 2 |
| **P2.3** | **More human follow-ups (free, no LLM).** Upgrade `interview_ai.py` to quote a noun-phrase from the candidate's own answer ("You mentioned *the cache TTL* — …"), de-dupe reactions within a round, expand casual/discussion openers. Pure-Python, unit-testable. (cap. #9,#12) | `services/interview_ai.py`, `apps/interviews/tests/test_interview_robustness.py` | 2 |
| **P2.4** | **Inline practical command validation.** In practical mode, candidate's typed commands POST to a new validate endpoint that runs the scenario's existing `check.sh`/checker against their lab session; set `command_validated` so scoring (+15) and the reply reflect real correctness. (cap. #13) | `apps/interviews/views.py`, `apps/interviews/urls.py`, `services/practical_lab.py`, `InterviewRoom.jsx` | 2.5 |
| **P2.5** | **Resume score + tips.** Add `score_resume(parsed, target_role)` (keyword coverage, length, quantified-impact heuristics) → return `resume_score`+`resume_tips` from profile PUT; render a card in Setup. (cap. #2) | `services/resume_parser.py`, `apps/interviews/views.py`, `apps/interviews/serializers.py`, `InterviewSetup.jsx` | 1.5 |
| **P2.6** | **Self-hosted free server STT (Vosk) behind a flag.** Add `vosk` + a small en model to the backend image; implement `_vosk_available()`/`transcribe_audio` in `stt_service.py` so `/stt/transcribe/` returns `provider="vosk"` when enabled, else browser. Frontend already consumes `uses_server_stt`. Batch (per-utterance) first — **no WS yet**. (cap. #7 server path) | `backend/apps/interviews/services/stt_service.py`, `backend/requirements.txt`, deploy image, `backend/config/settings.py` (`INTERVIEW_STT_ENGINE`) | 3 |
| **P2.7** | **Streaming voice over WebSocket.** New `InterviewVoiceConsumer` (copy `apps/terminal/consumers.py` pattern) at `ws/interview/<round_id>/?token=`: client streams 16 kHz PCM chunks → Vosk partial/final → engine reply text back → client speaks via browser TTS. Enables true low-latency loop + server-side barge-in signaling. (cap. #7,#8 server) | new `backend/apps/interviews/voice_consumer.py`, new `backend/apps/interviews/routing.py`, `backend/config/asgi.py`, `InterviewRoom.jsx`, `useInterviewVoice.js` | 4 |
| **P2.8** | **Transcript self-training.** Management command aggregates `InterviewMessage` per `InterviewQuestion`: update `avg_score`, flag low-discrimination/confusing questions, auto-promote frequent strong candidate phrasings into `discussion_prompts`. Optional weekly Celery beat. (cap. #24) | new `backend/apps/interviews/management/commands/train_from_transcripts.py`, `services/interview_ai.py` | 2 |
| **P2.9** | **Content + E2E hardening.** Seed more `itil`/`sla`/`tricky`/`practical` questions (wire `practical_config.scenario_slug` to real scenarios); Playwright E2E for the full voice round (mock STT); load-test WS on the 8 GB node. (cap. #11,#13,#17 content) | `management/commands/seed_interview_data.py`, `scenarios/**`, E2E specs | 3 |

**Suggested order:** P2.1 → P2.2 → P2.3 → P2.5 (all client/Python, zero infra, immediately better) then P2.4 → P2.6 → P2.7 (server STT + streaming) then P2.8 → P2.9.

---

## Recommended FREE voice architecture

**Phase 1 (P2.1–P2.5) — browser-native, zero server cost, ship now.**
- **TTS:** `window.speechSynthesis` with admin-picked `InterviewVoiceOption` (hint/pitch/rate). Already implemented in `useInterviewVoice.speak()`.
- **STT:** `window.SpeechRecognition`/`webkitSpeechRecognition` (Chrome/Edge). Already implemented as the fallback in `listen()`; just needs the call-site fix (P2.1).
- **Barge-in:** reuse the AudioContext mic-energy meter as a VAD; cancel TTS when energy crosses a threshold while `isSpeaking`.
- Pros: nothing to host, no model footprint, works today. Cons: browser STT is Chrome/Edge-only and quality varies; Safari/Firefox degrade to type-only.

**Phase 2 (P2.6–P2.7) — self-hosted free server STT for accuracy/coverage.**
- **Pick Vosk over whisper.cpp** for the self-host:
  - **Footprint on the 8 GB app node:** Vosk `vosk-model-small-en-us-0.15` is ~40 MB RAM and pure-CPU streaming; the small English model is tiny and fast. whisper.cpp `base.en` (~140 MB) / `small.en` (~460 MB) needs more RAM and is **batch** (chunked), not truly streaming, so latency is worse on shared CPU. Vosk is the lighter, streaming-native choice for this node.
  - **Streaming:** Vosk's `KaldiRecognizer.AcceptWaveform` yields partial + final results per chunk → maps cleanly onto a WebSocket loop and barge-in. whisper.cpp would force fixed windows and higher tail latency.
  - **Packaging:** `pip install vosk` + bake one small model into the image; gate with `INTERVIEW_STT_ENGINE=vosk|browser` (default `browser`).
- **Wiring the streaming STT→engine→TTS loop (reuses existing infra):**
  1. `config/asgi.py` already mounts `JWTAuthMiddleware(URLRouter(...))`. Add an interview `routing.py` alongside the terminal one (or extend the URLRouter) for `ws/interview/<round_id>/`.
  2. `InterviewVoiceConsumer(AsyncWebsocketConsumer)` modeled on `TerminalConsumer`: auth via `?token=`, per-user connection cap, `database_sync_to_async` for ORM. Hold one `KaldiRecognizer` per connection.
  3. Client (`useInterviewVoice`): capture mic via `AudioWorklet`/`ScriptProcessor` → downsample to 16 kHz PCM16 → send binary frames. Render partials as interim transcript.
  4. On final: consumer calls `engine.submit_answer(round, text)` (already free) and pushes back `{interviewer_reply, score, next_question}`; client speaks the reply with browser TTS. **Barge-in:** if the client sends audio while a reply is playing, it cancels local TTS and the consumer discards the in-flight reply.
  5. Keep the REST `/message/` endpoint as the no-WS fallback so the round always works.
- Redis channel layer (already configured, db 3) handles the observer fan-out if we later mirror the live transcript to admins.

**Net:** browser voice ships immediately with no infra; Vosk + the existing Channels stack upgrades accuracy and latency later without any paid dependency.

---

## Top risks

1. **Latency on shared 8 GB CPU node.** Server STT + many concurrent rounds competes with labs/terminal for CPU. *Mitigate:* Vosk small model (CPU-cheap, streaming); cap concurrent interview WS (reuse `MAX_WS_PER_USER` pattern); keep browser STT as the default and gate server STT behind a flag; consider a dedicated worker if usage grows.
2. **Self-host footprint / image bloat.** A model in the image + `vosk` wheel grows the container and cold-start. *Mitigate:* ship only the ~40 MB small-en model; lazy-load the recognizer; behind `INTERVIEW_STT_ENGINE`.
3. **Browser STT inconsistency.** Web Speech API is Chrome/Edge-only and accent-sensitive; Safari/Firefox can't do it. *Mitigate:* P2.1 fixes the existing fallback; type-to-answer always available; server STT (P2.6/7) closes the cross-browser gap.
4. **Barge-in false triggers.** Echo/background noise can cancel the bot mid-sentence. *Mitigate:* energy threshold + min-duration debounce; headphones recommended in preflight (already advised).
5. **WebSocket auth/stability in prod (Daphne behind LB).** Token-in-querystring + reconnect/keepalive must survive proxy timeouts. *Mitigate:* reuse the proven `JWTAuthMiddleware` + terminal consumer lifecycle; heartbeat ping; REST fallback if WS drops.
6. **"Free-but-robotic" risk.** Without an LLM, finite banks repeat in long rounds. *Mitigate:* P2.3 quote-the-candidate templating + in-round de-dup + P2.8 transcript-driven content growth. (The dormant Claude path in `engine_v2.py`/`llm_engine.py` stays off — it violates the free constraint.)
7. **Dead paid scaffolding drift.** `engine_v2.py`, `llm_engine.py`, paid branches of `tts_service.py`/`stt_service.py` are unused and could confuse future work or be accidentally enabled. *Mitigate:* clearly mark as optional/disabled (or remove `engine_v2.py`, which has zero references) in a cleanup pass.
