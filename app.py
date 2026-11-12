"""Simple Facebook video downloader (Flask + yt-dlp)."""
import re
from urllib.parse import quote

import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from yt_dlp import YoutubeDL

app = Flask(__name__, static_folder="static")

FB_PATTERN = re.compile(r"^https?://([a-z0-9-]+\.)?(facebook\.com|fb\.watch|fb\.com)/", re.I)


def extract(url):
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    # Some links resolve to a playlist-like wrapper; take the first entry.
    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)
    return info


def playable_formats(info):
    """Formats that already contain both video and audio (no ffmpeg merge needed)."""
    out = []
    for f in info.get("formats") or []:
        if not f.get("url") or f.get("protocol", "https") not in ("https", "http"):
            continue
        if f.get("vcodec") == "none" or f.get("acodec") == "none":
            continue
        out.append(f)
    out.sort(key=lambda f: (f.get("height") or 0, "hd" in (f.get("format_id") or "").lower(),
                            f.get("tbr") or 0), reverse=True)
    return out


def label(f):
    fid = (f.get("format_id") or "").lower()
    if f.get("height"):
        q = f"{f['height']}p"
    elif "hd" in fid:
        q = "HD"
    elif "sd" in fid:
        q = "SD"
    else:
        q = fid or "Video"
    return q


def validate(url):
    if not url or not FB_PATTERN.match(url):
        return "Please paste a valid Facebook video link."
    return None


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/info")
def api_info():
    url = (request.args.get("url") or "").strip()
    if err := validate(url):
        return jsonify(error=err), 400
    try:
        info = extract(url)
    except Exception as e:  # yt-dlp raises many error types
        return jsonify(error=friendly_error(e)), 422

    formats = playable_formats(info)
    if not formats:
        return jsonify(error="No downloadable video found. The video may be private."), 404

    seen, items = set(), []
    for f in formats:
        lbl = label(f)
        if lbl in seen:
            continue
        seen.add(lbl)
        items.append({
            "format_id": f["format_id"],
            "label": lbl,
            "ext": f.get("ext") or "mp4",
            "filesize": f.get("filesize") or f.get("filesize_approx"),
        })

    return jsonify(
        title=info.get("title") or "Facebook video",
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        formats=items,
    )


@app.get("/api/download")
def api_download():
    url = (request.args.get("url") or "").strip()
    format_id = request.args.get("format_id") or ""
    if err := validate(url):
        return jsonify(error=err), 400
    try:
        info = extract(url)
    except Exception as e:
        return jsonify(error=friendly_error(e)), 422

    fmt = next((f for f in playable_formats(info) if f["format_id"] == format_id), None)
    if fmt is None:
        return jsonify(error="That quality is no longer available. Try again."), 404

    upstream = requests.get(fmt["url"], headers=fmt.get("http_headers") or {}, stream=True, timeout=30)
    if upstream.status_code != 200:
        return jsonify(error="Facebook refused the download. Try again."), 502

    title = re.sub(r'[\\/:*?"<>|\r\n]+', " ", info.get("title") or "facebook_video").strip()[:80]
    filename = f"{title or 'facebook_video'}.{fmt.get('ext') or 'mp4'}"
    headers = {
        "Content-Disposition": f"attachment; filename=\"video.{fmt.get('ext') or 'mp4'}\"; filename*=UTF-8''{quote(filename)}",
        "Content-Type": upstream.headers.get("Content-Type", "video/mp4"),
    }
    if upstream.headers.get("Content-Length"):
        headers["Content-Length"] = upstream.headers["Content-Length"]

    def stream():
        try:
            for chunk in upstream.iter_content(chunk_size=256 * 1024):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return Response(stream(), headers=headers)


def friendly_error(e):
    msg = str(e).lower()
    if "login" in msg or "private" in msg or "cookies" in msg:
        return "This video is private or needs login. Only public videos can be downloaded."
    if "unsupported url" in msg:
        return "This link is not supported. Paste a direct Facebook video / reel link."
    return "Could not fetch this video. Check the link and try again."


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
