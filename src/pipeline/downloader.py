import os
import sys
import argparse
import yt_dlp

DATA_DIR = "data"

def extract_video_id(url: str) -> str:
    """Uses yt-dlp to just extract the video id without downloading."""
    ydl_opts = {'quiet': True, 'extract_flat': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return info.get('id')
    except Exception as e:
        print(f"Error extracting video ID: {e}")
    return None

def download_video_and_transcript(url: str, video_id: str, *, overwrite: bool = False) -> bool:
    """
    Downloads the best mp4 video and vtt transcripts from a YouTube URL to data/<video_id>/.
    """
    print(f"Starting download for: {url}")
    video_dir = os.path.join(DATA_DIR, video_id)
    os.makedirs(video_dir, exist_ok=True)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': {
            'default': f'{video_dir}/%(id)s.%(ext)s',
            'subtitle': f'{video_dir}/%(id)s.%(ext)s'
        },
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'ru'],
        'subtitlesformat': 'vtt',
        'noplaylist': True,
        'overwrites': overwrite,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([url])
            if error_code != 0:
                print(f"Error downloading video. yt-dlp exited with code {error_code}")
                return False
            print(f"Successfully downloaded video and transcripts for ID: {video_id}")
            return True
            
    except Exception as e:
        print(f"An exception occurred during download: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download YouTube video and VTT transcripts.")
    parser.add_argument("url", help="YouTube video URL")
    args = parser.parse_args()
    
    os.makedirs(DATA_DIR, exist_ok=True)
    vid = extract_video_id(args.url)
    if not vid:
        sys.exit(1)
        
    success = download_video_and_transcript(args.url, vid)
    if not success:
        sys.exit(1)
