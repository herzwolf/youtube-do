from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import os
import uuid
import shutil
from pathlib import Path

app = FastAPI()

# Allow your Blogger site to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For testing, we'll allow all
    allow_methods=["*"],
)

# Create downloads folder if it doesn't exist
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.get("/")
async def root():
    return {"message": "YouTube Downloader API is running!"}

@app.get("/info")
async def get_info(url: str):
    """Get video information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info without downloading
            info = ydl.extract_info(url, download=False)
            
            # Get available formats
            formats = []
            for f in info.get('formats', []):
                if f.get('height'):  # Video formats
                    formats.append({
                        'format_id': f.get('format_id'),
                        'quality': f"{f.get('height')}p",
                        'ext': f.get('ext'),
                        'filesize': f.get('filesize')
                    })
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':  # Audio only
                    formats.append({
                        'format_id': f.get('format_id'),
                        'quality': 'audio',
                        'ext': f.get('ext'),
                        'filesize': f.get('filesize')
                    })
            
            return {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'formats': formats[:10]  # Limit to 10 formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download")
async def download_video(url: str, format_id: str = 'best'):
    """Download video and return file"""
    # Generate unique filename
    filename = f"{uuid.uuid4()}.%(ext)s"
    output_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    ydl_opts = {
        'format': format_id,
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Download the video
            info = ydl.extract_info(url, download=True)
            
            # Get the actual filename
            actual_filename = ydl.prepare_filename(info)
            
            # Return the file
            return FileResponse(
                path=actual_filename,
                filename=os.path.basename(actual_filename),
                media_type='application/octet-stream'
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # Clean up old files (optional)
        cleanup_old_files()

def cleanup_old_files():
    """Remove files older than 1 hour"""
    try:
        now = time.time()
        for f in os.listdir(DOWNLOAD_FOLDER):
            f_path = os.path.join(DOWNLOAD_FOLDER, f)
            if os.path.isfile(f_path):
                # Remove if older than 1 hour (3600 seconds)
                if os.stat(f_path).st_mtime < now - 3600:
                    os.remove(f_path)
    except:
        pass
