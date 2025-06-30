# Installation


```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```


```bash
MODAL_PROFILE=modal-labs modal run --env=joy-dev sandbox/main.py
MODAL_PROFILE=modal-labs modal serve --env=joy-dev web/main.py
```

Make sure you add your Anthropic API key to both the `.env` for local testing and also in `Modal > Workspace > Secrets`.