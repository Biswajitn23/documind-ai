# DocuMind AI

A free, local-first document workspace with PDF/text upload, document library, summaries, action items and keyword-based Q&A.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

## Deploy to Render

1. Push this folder to its own GitHub repository.
2. In Render, choose **New → Web Service** and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Select the Free instance type and add a strong `SECRET_KEY`.

`render.yaml` is included as a Blueprint starting point.

## Important deployment note

Render free web services use an ephemeral filesystem. SQLite databases and uploaded files can be lost when the service restarts or redeploys. For durable production data, connect a managed PostgreSQL database and object storage, or use a paid persistent disk. This starter is intended for demos and evaluation.

## Security and scope

This is a functional student-project MVP, not a production service. Add proper authentication, authorization, rate limiting, CSRF protection, malware scanning and persistent storage before handling sensitive/public data. Demo mode does not call paid AI APIs.
