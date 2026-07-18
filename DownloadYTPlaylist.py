import yt_dlp
import os

playlist_url = input("Playlist URL: ").strip()

output_dir = "downloads"

video_dir = os.path.join(output_dir, "mp4")
audio_dir = os.path.join(output_dir, "mp3")

os.makedirs(video_dir, exist_ok=True)
os.makedirs(audio_dir, exist_ok=True)


common_opts = {
    "noplaylist": False,
    "ignoreerrors": True,
    "continuedl": True,
    "retries": 10,
    "fragment_retries": 10,
    "quiet": False,
    "no_warnings": False,
}


# -------------------------
# Download MP4 files
# -------------------------

video_opts = {
    **common_opts,
    "format": "bestvideo+bestaudio/best",
    "merge_output_format": "mp4",
    "outtmpl": f"{video_dir}/%(playlist_index)s - %(title)s.%(ext)s",
}

print("\n=== Downloading MP4 playlist ===\n")

with yt_dlp.YoutubeDL(video_opts) as ydl:
    ydl.download([playlist_url])


# -------------------------
# Download and convert MP3
# -------------------------

audio_opts = {
    **common_opts,
    "format": "bestaudio/best",
    "outtmpl": f"{audio_dir}/%(playlist_index)s - %(title)s.%(ext)s",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }
    ],
}

print("\n=== Extracting MP3 playlist ===\n")

with yt_dlp.YoutubeDL(audio_opts) as ydl:
    ydl.download([playlist_url])


print("\n=== Finished ===")
