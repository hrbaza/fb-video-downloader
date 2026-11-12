# SaveFB — Facebook Video Downloader

A simple web app to download public Facebook videos and reels as MP4 (HD / SD).

Built with **Flask** + **yt-dlp**. The front page is a single HTML file (`static/index.html`).

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000

## How it works

- `GET /api/info?url=<facebook link>` returns the title, thumbnail, duration and available qualities.
- `GET /api/download?url=<facebook link>&format_id=<id>` streams the chosen MP4 to the browser.

Only public videos are supported. If downloads stop working, update yt-dlp:

```bash
pip install -U yt-dlp
```

> Only download videos you have the right to save. Not affiliated with Facebook or Meta.
