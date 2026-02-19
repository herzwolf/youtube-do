from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import os
import uuid
import time
from pathlib import Path

app = FastAPI()

# Allow your Blogger site to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.get("/")
async def root():
    return {"message": "YouTube Downloader API is running with improved formats!"}

@app.get("/info")
async def get_info(url: str):
    """Get video information with proper format filtering"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Filter and organize formats
            formats = []
            seen_qualities = set()
            
            for f in info.get('formats', []):
                # Skip MHTML storyboards
                if f.get('ext') == 'mhtml' or 'storyboard' in str(f.get('format_note', '')).lower():
                    continue
                
                # Video formats (with height)
                if f.get('height'):
                    # Only include each quality once (prefer mp4)
                    quality_key = f"{f.get('height')}p"
                    if quality_key not in seen_qualities:
                        formats.append({
                            'format_id': f.get('format_id'),
                            'quality': quality_key,
                            'ext': f.get('ext', 'mp4'),
                            'filesize': f.get('filesize'),
                            'has_audio': f.get('acodec') != 'none'
                        })
                        seen_qualities.add(quality_key)
                
                # Audio-only formats
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    # Only include best audio formats
                    if f.get('ext') in ['m4a', 'webm']:
                        formats.append({
                            'format_id': f.get('format_id'),
                            'quality': 'audio',
                            'ext': f.get('ext', 'm4a'),
                            'filesize': f.get('filesize'),
                            'has_audio': True
                        })
            
            # Add combined format for best quality
            formats.append({
                'format_id': 'bestvideo+bestaudio',
                'quality': 'Best Available (merged)',
                'ext': 'mp4',
                'has_audio': True,
                'note': 'Best quality (requires ffmpeg)'
            })
            
            return {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'formats': formats[:15]  # Limit to 15 formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download")
async def download_video(url: str, format_id: str = 'best'):
    """Download video with format selection"""
    filename = f"{uuid.uuid4()}.%(ext)s"
    output_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    # Handle merged format
    if format_id == 'bestvideo+bestaudio':
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',  # Try to merge
        }
    else:
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            actual_filename = ydl.prepare_filename(info)
            
            # Handle merged files
            if not os.path.exists(actual_filename):
                actual_filename = actual_filename.replace('.webm', '.mp4').replace('.m4a', '.mp4')
            
            return FileResponse(
                path=actual_filename,
                filename=os.path.basename(actual_filename),
                media_type='application/octet-stream'
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # Clean up old files
        cleanup_old_files()

def cleanup_old_files():
    """Remove files older than 1 hour"""
    try:
        now = time.time()
        for f in os.listdir(DOWNLOAD_FOLDER):
            f_path = os.path.join(DOWNLOAD_FOLDER, f)
            if os.path.isfile(f_path):
                if os.stat(f_path).st_mtime < now - 3600:
                    os.remove(f_path)
    except:
        pass
