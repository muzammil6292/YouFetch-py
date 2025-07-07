# app.py - Flask backend for YouTube downloader
from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable cross-origin requests

# Create downloads folder
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def index():
    # Serve the HTML frontend
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/api/video-info', methods=['POST'])
def get_video_info():
    """Get video information without downloading"""
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        video_info = {
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', 'Unknown'),
            'view_count': info.get('view_count', 0),
            'upload_date': info.get('upload_date', ''),
            'thumbnail': info.get('thumbnail', ''),
            'formats_available': len(info.get('formats', []))
        }
        
        return jsonify(video_info)
        
    except Exception as e:
        error_message = str(e)
        if 'Video unavailable' in error_message or "This content isn't available" in error_message:
            user_friendly = 'This video is unavailable. It may be private, deleted, region-locked, or age-restricted.'
            return jsonify({'error': user_friendly}), 400
        return jsonify({'error': error_message}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    """Download video with specified quality"""
    try:
        data = request.json
        url = data.get('url')
        quality = data.get('quality', 'best')
        custom_format = data.get('customFormat', '')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Map quality to yt-dlp format
        quality_map = {
            'best': 'bestvideo+bestaudio/best',
            '4k': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
            '2k': 'bestvideo[height<=1440]+bestaudio/best[height<=1440]',
            '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            'audio': 'bestaudio/best',
            'custom': custom_format or 'best'
        }
        
        format_selector = quality_map.get(quality, 'best')
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'%(title)s_{timestamp}.%(ext)s'),
            'restrictfilenames': True,  # Avoid special characters
        }
        
        # For audio downloads, add post-processor
        if quality == 'audio':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
        # Find the downloaded file
        downloaded_files = []
        for file in os.listdir(DOWNLOAD_FOLDER):
            if timestamp in file:
                downloaded_files.append(file)
        
        if downloaded_files:
            filename = downloaded_files[0]
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            file_size = os.path.getsize(file_path)

            # If not mp4, convert to mp4 using ffmpeg
            base, ext = os.path.splitext(filename)
            if ext.lower() != '.mp4':
                mp4_filename = base + '.mp4'
                mp4_file_path = os.path.join(DOWNLOAD_FOLDER, mp4_filename)
                # Convert to mp4 using ffmpeg
                os.system(f'ffmpeg -y -i "{file_path}" -c:v copy -c:a aac "{mp4_file_path}"')
                # Optionally, remove the original file
                # os.remove(file_path)
                filename = mp4_filename
                file_path = mp4_file_path
                file_size = os.path.getsize(file_path)

            return jsonify({
                'status': 'success',
                'filename': filename,
                'file_size': file_size,
                'download_path': file_path,
                'title': info.get('title', 'Unknown')
            })
        else:
            return jsonify({'error': 'Download completed but file not found'}), 500
            
    except Exception as e:
        error_message = str(e)
        if 'Video unavailable' in error_message or "This content isn't available" in error_message:
            user_friendly = 'This video is unavailable. It may be private, deleted, region-locked, or age-restricted.'
            return jsonify({'error': user_friendly}), 400
        return jsonify({'error': error_message}), 500

@app.route('/api/list-downloads', methods=['GET'])
def list_downloads():
    """List all downloaded files"""
    try:
        files = []
        if os.path.exists(DOWNLOAD_FOLDER):
            for filename in os.listdir(DOWNLOAD_FOLDER):
                file_path = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(file_path):
                    file_info = {
                        'filename': filename,
                        'size': os.path.getsize(file_path),
                        'modified': os.path.getmtime(file_path)
                    }
                    files.append(file_info)
        
        return jsonify({'files': files})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-file/<filename>')
def download_file(filename):
    """Download a file to user's computer"""
    try:
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    print("🚀 Starting YouTube Downloader Server...")
    print("📁 Downloads will be saved in:", os.path.abspath(DOWNLOAD_FOLDER))
    print(f"🌐 Open your browser to: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)