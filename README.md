# YouTube Transcript Generator — Render Ready

This package is ready to deploy online on Render.

## What it does

- Paste a YouTube URL
- Fetch the full available caption transcript
- No summarization or rewriting
- Format the transcript into readable paragraphs
- Copy transcript text
- Save as `.txt`
- Save as PDF

## Deploy on Render

### Option A — GitHub + Render

1. Create a new GitHub repository.
2. Upload all files from this folder to the repository.
3. Go to https://render.com/
4. Sign in and choose **New +** → **Web Service**.
5. Connect your GitHub repository.
6. Render should detect the `render.yaml` configuration automatically.

If you configure it manually, use:

- Environment: `Python`
- Build Command:

```text
pip install -r requirements.txt
```

- Start Command:

```text
gunicorn app:app
```

7. Deploy the service.
8. Render will give you a public URL such as:

```text
https://youtube-transcript-generator.onrender.com
```

## Important limitation

The app relies on YouTube caption/transcript access. Some videos may fail if:

- captions are disabled
- no transcript exists
- YouTube blocks transcript retrieval from the hosting server IP
- the requested language is unavailable

In those cases the app reports the error instead of inventing transcript text.

## Local Windows run (optional)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```
