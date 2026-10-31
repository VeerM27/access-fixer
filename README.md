# Access Fixer

Access Fixer takes the GitHub repo of a static website, checks every page against WCAG 2.2 AA, fixes what it can, and opens a pull request once you've said yes. It's built with Google's Agent Development Kit (ADK 2.x) and Gemini.

## Why

In the UK, public sector websites have to meet the Public Sector Bodies Accessibility Regulations 2018 (PSBAR), and the government's monitoring team checks them against WCAG 2.2 AA. Lots of small organisations (councils, schools, charities working with them) run simple static sites with nobody whose job is accessibility. The usual failures are boring and fixable: missing alt text, unlabelled form fields, low contrast text, tiny tap targets, a missing `lang` attribute. I wanted a tool that fixes those for you and shows its working, instead of handing you a 40-page audit report.

## How it works

The whole thing is one ADK 2.x `Workflow` graph. Only one step uses an LLM; everything else is plain Python, so the parts that decide whether a fix is good are deterministic.

```
START -> read_source -> fix_pipeline -> report -> ask_approval -> open_pr
```

1. **read_source** takes a GitHub HTTPS URL and does a shallow clone with limits: a GitHub API size check first, then a 60 second timeout and a 50 MB / 500 file cap after cloning. Nothing from the repo is ever run (no installs, no builds). Local folders only work in dev mode (`ACCESS_FIXER_ALLOW_LOCAL=1`).
2. **fix_pipeline** works on a temporary copy, so the original is never touched.
   - **Audit:** serves the copy on localhost and runs axe-core 4.12.1 in headless Chromium through Playwright. Any request to another origin is blocked, because page content is untrusted. Scored rules are the WCAG A/AA tags only; `best-practice` rules are reported as unscored advisories.
   - **Fixer agent:** a single Gemini `Agent` with `output_schema=list[Edit]` gets the failing rules, the failing elements and only the affected files, wrapped as untrusted data with an instruction never to follow instructions inside it. It returns find/replace edits.
   - **Apply:** plain code. Only `.html` and `.css` files, the resolved path must stay inside the copy, and `find` must match exactly once, otherwise the edit is rejected with a reason.
   - **Re-audit and revert:** if any rule's failing count goes up on any page, the touched files are restored and their edits are re-applied one at a time, re-auditing the affected pages after each (for a CSS file, every page that links it). Only the edit that made things worse is rejected. This matters because one shared stylesheet is used by every page.
   - **Loop:** at most 2 rounds.
3. **report** shows failures before and after, the score, accepted edits per rule, rejected edits with reasons, and a manual-check list (vague link text like "Read more", and every alt text the model wrote, marked as suggested).
4. **ask_approval** pauses the workflow with ADK's `RequestInput`. Anything other than "yes" stops there and GitHub is left alone.
5. **open_pr** calls the GitHub MCP server's `create_branch`, `push_files` and `create_pull_request` tools directly from code through `McpToolset`, with fixed arguments. The PR body (before/after table, fixes, rejected edits, manual checks) is built in code, so there are no LLM calls after the fix loop.

The score is the mean pass rate over the WCAG rules that apply to the site (`passing / (passing + failing)` nodes per rule, x100). The headline number is the count of failing elements, because that's what actually goes down as fixes land.

If Gemini is overloaded (503 after retries) or out of quota (429), the request is retried once on a fallback model inside the model call, and the log line for each round records which model actually ran.

## Results

On [demo-charity-site](https://github.com/VeerM27/demo-charity-site), a five-page site seeded with 30 failing elements across 12 WCAG rules (tag `broken-baseline`):

| Run | Model | Rounds | Failing elements | Score | Edits rejected |
|---|---|---|---|---|---|
| Local copy | gemini-3.6-flash | 1 | 30 → 0 | 87.8 → 100.0 | 0 |
| Local copy | gemini-3.5-flash-lite (fallback after a 429) | 1 | 30 → 0 | 87.8 → 100.0 | 0 |
| From the GitHub URL | gemini-3.5-flash-lite | 2 | 30 → 0 | 87.8 → 100.0 | 2 (`find` text not in file) |
| From the GitHub URL, opened the PR | gemini-3.5-flash-lite | 2 | 30 → 0 | 87.8 → 100.0 | 1 (`find` matched twice) |

No rule got worse in any of these runs. The pull request from the last run is [VeerM27/demo-charity-site#1](https://github.com/VeerM27/demo-charity-site/pull/1).

Before the one-at-a-time revert existed, runs ended at 30 → 7 and 30 → 14: a single bad edit on one page was throwing away every good fix in the shared stylesheet. That's the main thing the per-edit check fixed.

## Running it

You need [uv](https://docs.astral.sh/uv/) and git.

```
cp .env.example .env
uv sync
uv run playwright install chromium
uv run pytest
uv run adk web
```

Fill in `.env`:

- `GOOGLE_API_KEY`: a Gemini API key.
- `ACCESS_FIXER_MODEL` (default `gemini-3.6-flash`) and `ACCESS_FIXER_FALLBACK_MODEL` (default `gemini-3.5-flash-lite`).
- `GITHUB_PAT`: a fine-grained token with access to the target repo, with Contents and Pull requests set to read and write.
- `ACCESS_FIXER_ALLOW_LOCAL=1` only if you want to point it at a local folder while developing.

In `adk web`, pick `access_fixer` and send a repo URL like `https://github.com/VeerM27/demo-charity-site`. It audits, fixes, shows the report, then waits for your answer before touching GitHub.

The tests never call Gemini; they use a stub fixer. To run the one live test: `ACCESS_FIXER_LIVE=1 uv run pytest tests/test_fix_live.py`.

## Limits

- Static HTML and CSS only. No JavaScript frameworks, templates or build steps.
- Not deployed yet. It runs locally in `adk web`.
- Automated checks only cover part of WCAG. Keyboard use, focus order, screen reader output, captions and whether link text and alt text actually make sense still need a person, which is why the PR has a manual-check list.
- Alt text is written by the model from file names and context, so treat it as a suggestion.
- The free Gemini tier allows about 20 requests per model per day, which is one reason the fix loop stops at 2 rounds.
