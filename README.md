# Access Fixer

Access Fixer is an agent that takes a GitHub repo of a static website, finds its pages and checks them against WCAG 2.2 AA with axe-core. It then writes fixes with Gemini, applies them, re-checks the pages, and throws out any change that makes things worse. When it's done it asks you to approve the changes before it opens a pull request. It's built with Google's Agent Development Kit (ADK) and runs on Cloud Run. Right now it only handles plain HTML and CSS, and it never runs anything from the repo it's checking.

## Quick start

You need [uv](https://docs.astral.sh/uv/).

```
cp .env.example .env      # then fill in your keys
uv sync
uv run playwright install chromium
uv run pytest
uv run adk web            # open the dev UI and pick access_fixer
```
