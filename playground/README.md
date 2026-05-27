# web-auto-form Playground

Try web-auto-form instantly in your browser. Paste a JSON config, click Run, and see the results — no installation needed.

## Online

→ **[Launch on Hugging Face Spaces](https://huggingface.co/spaces/DUZ1287/web-auto-form)**

## Local

```bash
pip install gradio web-auto-form
python playground/app.py
```

Then open <http://localhost:7860>.

## Features

- **JSON editor** with syntax highlighting and validation
- **Preset examples** — load a demo config with one click
- **Live output** — see results as the engine executes
- **Download** — save the output as JSON

## Deploy to Hugging Face Spaces

1. Fork this repository
2. Create a new Space at <https://huggingface.co/new-space>
3. Choose **Gradio** as the SDK
4. Set the Space's `app.py` to `playground/app.py`
5. Add `web-auto-form` and `playwright` to `requirements.txt`
6. The Space will auto-build and deploy

Or use the Duplicate button:

[![Duplicate Space](https://huggingface.co/datasets/huggingface/badges/raw/main/duplicate-this-space-sm.svg)](https://huggingface.co/spaces/DUZ1287/web-auto-form?duplicate=true)
