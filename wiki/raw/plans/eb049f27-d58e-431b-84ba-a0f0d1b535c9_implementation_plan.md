# Second Brain Compression & Summarization Skill

Build a python-based service to parse, format, and summarize Antigravity chats and workspace plan files. The summarized contents will be saved into the `wiki/summaries/` directory, while their formatted raw equivalents will be archived in `wiki/raw/`. An index will be compiled at `wiki/second_brain_summaries.md`, and the entire process will be integrated into the existing `wiki_service.py` pipeline.

## User Review Required

> [!NOTE]
> The summarization tool uses the configured AI provider in `.env` (Gemini, Moonshot, OpenAI, or LMStudio). If the provider is set to `mock`, the summary will use a fallback mock template.

> [!IMPORTANT]
> The chat logs are located in the host's app data directory (e.g., `C:\Users\finnp\.gemini\antigravity\brain`). The Python script runs locally, so it has access to read these logs, convert them from JSONL steps into readable markdown, and generate summaries.

## Open Questions

> [!WARNING]
> Do you want the summarization process to automatically run on every access of the command center dashboard (which calls `GET /api/db/second-brain`), or should it run on a background timer (every 5-15 mins) or via a manual button trigger?
>
> *Recommendation*: Since LLM API calls take time and cost tokens, we will use a **file modification time check** (mtime-based cache). It will only call the LLM to summarize a chat or plan if the raw file is newer than the existing summary file, or if no summary exists. This prevents redundant API requests.

## Proposed Changes

We will introduce a new compressor service, modify the wiki service to integrate it, and expose endpoints to manage it.

---

### core / service

#### [NEW] [brain_compressor.py](file:///g:/Downloads_Sortiert_2026-05-20/ai_trading_jules_prompt_pack/app/services/brain_compressor.py)
Create a service class `BrainCompressor` that implements:
- Locating raw workspace plans (`*plan*.md`, `01_jules_masterprompt*.md`, `AGENTS.md`, `JULES_24H_SCHEDULE.md`).
- Scanning the Antigravity `brain/` directory for conversation logs.
- Formatting raw `.jsonl` transcripts into readable markdown dialog transcripts:
  - `**User**: <message>`
  - `**Assistant**: <response>`
- Storing raw formatted files in `wiki/raw/chats/` and `wiki/raw/plans/`.
- Calling the configured LLM API (via the app's standard `AsyncOpenAI` client) to summarize each raw chat or plan.
- Writing summaries to `wiki/summaries/chats/` and `wiki/summaries/plans/`.
- Compiling a consolidated markdown index at `wiki/second_brain_summaries.md` that maps each summary to its raw source.

#### [MODIFY] [wiki_service.py](file:///g:/Downloads_Sortiert_2026-05-20/ai_trading_jules_prompt_pack/app/services/wiki_service.py)
- Import `BrainCompressor` and run its compression routine inside `update_second_brain()`.
- Append a link/reference or summary block in `wiki/second_brain.md` pointing to `wiki/second_brain_summaries.md` to ensure any AI reading the main second brain file knows about the conversation and plan summaries.

---

### api / endpoints

#### [MODIFY] [db_insight.py](file:///g:/Downloads_Sortiert_2026-05-20/ai_trading_jules_prompt_pack/app/api/db_insight.py)
- Add a new endpoint `POST /api/db/second-brain/compress` to manually trigger the compression and summarization.
- Add an endpoint `GET /api/db/second-brain/summaries` to fetch the compiled consolidated index content (`wiki/second_brain_summaries.md`).

## Verification Plan

### Automated Tests
- Create a test `tests/services/test_brain_compressor.py` to:
  - Validate formatting of JSONL logs into markdown.
  - Verify that file modification time caching correctly skips unchanged files.
  - Test LLM calls (mocked or with configured provider).

### Manual Verification
- Execute `update_second_brain()` directly via a scratch script and verify that `wiki/raw/` and `wiki/summaries/` are created and populated.
- Review the generated `wiki/second_brain_summaries.md` structure.
- Trigger the API endpoints and ensure they return the expected outputs.
