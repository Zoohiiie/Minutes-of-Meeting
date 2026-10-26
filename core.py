import json, os, re, shutil, subprocess, tempfile, time
from google import genai
from google.genai import types, errors

MODEL = "gemma-4-26b-a4b-it"          # analysis: open-weight Gemma
AUDIO_MODEL = "gemini-3.5-flash-lite" # transcription: Google's fastest stable model (change if Google renames it)
AUDIO_FALLBACK = "gemini-3.8-flash"   # transcription backup if the fast model fails
FALLBACK_MODEL = "gemini-3.8-flash"   # used if the main model keeps failing on Google's side
MAX_CHARS = 60000                     # transcript length sent to the model

PROMPT = """You are a meeting assistant. Read the transcript and return ONLY valid JSON, no extra text, in exactly this shape:
{{
  "title": "short meeting title",
  "attendees": ["names that appear in the transcript"],
  "summary": "3-4 sentence summary",
  "topics": ["main topics discussed"],
  "decisions": ["..."],
  "action_items": [
    {{"task": "...", "owner": "name or null", "due_date": "or null", "evidence": "short quote from the transcript"}}
  ],
  "open_questions": ["unresolved issues or risks"]
}}
Rules:
- Be concise. Only include what was actually said.
- owner: only if a person is explicitly assigned. Otherwise null.
- due_date: copy the wording used in the transcript (e.g. "Friday"). If none was mentioned, null. Never guess.
- evidence: copy a short phrase exactly as it appears in the transcript.

TRANSCRIPT:
{transcript}"""


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _mentioned(value, transcript: str):
    """Keep a value only if it literally appears in the transcript."""
    if value and _norm(value) in _norm(transcript):
        return str(value).strip()
    return None


def _strs(items):
    return [str(i).strip() for i in (items or []) if i and str(i).strip()]


def _json_from(text: str) -> dict:
    """Pull the first JSON object out of the model reply, even with fences or chatter around it."""
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start:end + 1])


def parse_response(text: str, transcript: str) -> dict:
    data = _json_from(text)
    items = []
    for it in data.get("action_items") or []:
        if not isinstance(it, dict) or not str(it.get("task") or "").strip():
            continue
        items.append({
            "task": str(it["task"]).strip(),
            "owner": _mentioned(it.get("owner"), transcript),
            "due_date": _mentioned(it.get("due_date"), transcript),
            # the quote is kept only if it really appears in the transcript
            "evidence": _mentioned(it.get("evidence"), transcript) or "",
        })
    return {
        "title": data.get("title") or "Meeting minutes",
        "attendees": _strs(data.get("attendees")),
        "summary": data.get("summary") or "",
        "topics": _strs(data.get("topics")),
        "decisions": _strs(data.get("decisions")),
        "action_items": items,
        "open_questions": _strs(data.get("open_questions")),
    }


def _client(api_key: str):
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError(
            "No API key found. Add GEMINI_API_KEY to .streamlit/secrets.toml "
            "or set it as an environment variable."
        )
    # timeout is in milliseconds: a stuck request fails after 2 minutes instead of hanging forever
    return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=120_000))


def _fast_config():
    """Ask the model to think as little as it can: plain transcription does not need deep reasoning.
    Falls back to the default settings if the installed google-genai is too old to know thinking levels."""
    try:
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
        )
    except Exception:
        return None


def _ffmpeg_exe():
    """Find ffmpeg on the system, or use the copy bundled with the imageio-ffmpeg package."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def compress_audio(audio_bytes: bytes, mime: str):
    """Shrink a recording to 16 kHz mono MP3 at 32 kbps, which is plenty for speech.
    Returns the original audio untouched if ffmpeg is missing, fails, or the result is not smaller."""
    exe = _ffmpeg_exe()
    if not exe:
        return audio_bytes, mime
    try:
        with tempfile.TemporaryDirectory() as folder:
            src, dst = os.path.join(folder, "in"), os.path.join(folder, "out.mp3")
            with open(src, "wb") as f:
                f.write(audio_bytes)
            subprocess.run(
                [exe, "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                 "-c:a", "libmp3lame", "-b:a", "32k", dst],
                check=True, timeout=120,
            )
            with open(dst, "rb") as f:
                small = f.read()
        if small and len(small) < len(audio_bytes):
            return small, "audio/mpeg"
    except Exception:
        pass
    return audio_bytes, mime


def transcribe(audio_bytes: bytes, mime: str, api_key: str = "") -> str:
    # keep the client in a variable: if it is only used inline, Python discards it
    # (closing its connection) before the request is sent
    client = _client(api_key)
    audio_bytes, mime = compress_audio(audio_bytes, mime)   # smaller upload, same speech quality
    contents = [
        types.Part.from_bytes(data=audio_bytes, mime_type=mime or "audio/mpeg"),
        "Transcribe this meeting. Label speakers as 'Name:' if names are spoken, "
        "otherwise 'Speaker 1:', 'Speaker 2:'. Output plain text only.",
    ]
    last = None
    for model in (AUDIO_MODEL, AUDIO_FALLBACK):
        config = _fast_config()
        for attempt in range(3):   # Google's models sometimes return 503 for a few seconds
            try:
                resp = client.models.generate_content(model=model, contents=contents, config=config)
                return (resp.text or "").strip()
            except errors.APIError as e:
                last = e
                code = getattr(e, "code", None)
                if code == 400 and config is not None:
                    config = None            # this model may not accept the thinking setting, retry without it
                    continue
                if code in RETRY_CODES:
                    time.sleep(attempt + 1)  # waits 1s, 2s, 3s
                    continue
                break                        # model not found / not usable: try the backup model
    raise ValueError(
        f"Transcription failed ({getattr(last, 'code', '?')}): "
        f"{getattr(last, 'message', None) or last}. Wait a minute and press Transcribe recording again."
    )


RETRY_CODES = (429, 500, 502, 503, 504)   # temporary problems on the server side


def _call(client, model: str, prompt: str):
    """Call the model, retrying with a short wait when the server reports a temporary error."""
    last = None
    for attempt in range(3):
        try:
            return client.models.generate_content(model=model, contents=prompt)
        except errors.APIError as e:
            last = e
            if getattr(e, "code", None) in RETRY_CODES:
                time.sleep(2 ** attempt)   # 1s, 2s, 4s
                continue
            raise
    raise last


def generate(transcript: str, api_key: str = "") -> dict:
    client = _client(api_key)
    prompt = PROMPT.format(transcript=transcript[:MAX_CHARS])
    api_error = None
    for model in (MODEL, FALLBACK_MODEL):
        for _ in range(2):  # retry once if the JSON comes back broken
            try:
                resp = _call(client, model, prompt)
                return parse_response(resp.text, transcript)
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue
            except errors.APIError as e:
                api_error = e
                break       # this model is failing, try the next one
    if api_error is not None:
        raise ValueError(
            f"The AI service is busy or unavailable right now (error {getattr(api_error, 'code', '?')}). "
            "Wait a minute and press Create minutes again."
        )
    raise ValueError("The model did not return valid JSON. Try again.")


def to_markdown(m: dict) -> str:
    L = [f"# {m['title']}", ""]
    if m.get("attendees"):
        L += [f"**Attendees:** {', '.join(m['attendees'])}", ""]
    L += ["## Summary", m["summary"], ""]
    if m.get("topics"):
        L += ["## Topics discussed"] + [f"- {t}" for t in m["topics"]] + [""]
    L += ["## Decisions"] + ([f"- {d}" for d in m["decisions"]] or ["- None"]) + [""]
    L += ["## Action items", "", "| Task | Owner | Due |", "|---|---|---|"]
    for i in m["action_items"]:
        L.append(f"| {i.get('task') or '-'} | {i.get('owner') or '-'} | {i.get('due_date') or '-'} |")
    if m.get("open_questions"):
        L += ["", "## Open questions"] + [f"- {q}" for q in m["open_questions"]]
    return "\n".join(L)