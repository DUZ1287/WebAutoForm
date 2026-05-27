# web-auto-form Playground

Run the web-auto-form playground locally, or deploy your own to Hugging Face Spaces.

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

Once deployed, you'll get your own URL like `https://huggingface.co/spaces/<your-username>/web-auto-form-playground` that anyone can use.
