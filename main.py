import flet as ft
import subprocess
import os
import threading
import shutil
import sys
import json
import re

# تثبيت yt-dlp بتلقائي إذا لم تكن موجودة
def install_dependencies():
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        print("جاري تثبيت yt-dlp...")
        subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"], check=True)
        import yt_dlp
        print("تم تثبيت yt-dlp بنجاح!")
        return yt_dlp

yt_dlp = install_dependencies()

def main(page: ft.Page):
    page.title = "✂️ قاطع الفيديوهات للواتساب - السحابي"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#1E1E2E"
    page.window_width = 500
    page.window_height = 600
    page.window_resizable = False

    # متغيرات التطبيق
    video_path = ""
    progress_bar = ft.ProgressBar(width=400, visible=False)
    status_text = ft.Text("جاهز للعمل", size=14, color="#FAB387")
    download_btn = ft.ElevatedButton("🔗 تحميل ومعالجة", disabled=True)
    split_btn = ft.ElevatedButton("✂️ بدء التقسيم", disabled=True)

    # حقل رابط يوتيوب
    youtube_url = ft.TextField(
        label="أدخل رابط يوتيوب",
        width=400,
        border_color="#45475A",
        focused_border_color="#89B4FA"
    )

    # حقل اختيار ملف
    file_picker = ft.FilePicker(on_result=lambda e: on_file_selected(e))
    page.overlay.append(file_picker)

    def on_file_selected(e):
        nonlocal video_path
        if e.files:
            video_path = e.files[0].path
            status_text.value = f"تم اختيار: {os.path.basename(video_path)}"
            split_btn.disabled = False
            page.update()

    def select_file(e):
        file_picker.pick_files(allow_multiple=False, allowed_extensions=["mp4", "mov", "avi", "mkv"])

    def get_video_duration(video_path):
        """الحصول على مدة الفيديو بالثواني"""
        try:
            ffprobe_path = os.path.join(os.path.dirname(__file__), "ffprobe.exe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"

            cmd = [
                ffprobe_path, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1:noprint_sections=1",
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)

            if result.returncode != 0:
                ffmpeg_path = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
                if not os.path.exists(ffmpeg_path):
                    ffmpeg_path = "ffmpeg"

                cmd = [ffmpeg_path, "-i", video_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)

                output = result.stderr if result.stderr else result.stdout
                for line in output.split('\n'):
                    if 'Duration' in line:
                        match = re.search(r'Duration: (\d+):(\d+):(\d+\.?\d*)', line)
                        if match:
                            hours = int(match.group(1))
                            minutes = int(match.group(2))
                            seconds = float(match.group(3))
                            return hours * 3600 + minutes * 60 + seconds
                return 0

            duration_str = result.stdout.strip()
            return float(duration_str) if duration_str else 0

        except Exception as e:
            status_text.value = f"خطأ في قراءة المدة: {str(e)[:100]}"
            page.update()
            return 0

    def download_video(url, retry_count=0):
        try:
            temp_dir = "downloads"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            ydl_opts = {
                'format': 'best[ext=mp4][height<=720]/18/22',
                'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [lambda d: progress_hook(d)],
                'retries': 50,
                'fragment_retries': 50,
                'retry_sleep_functions': {
                    'http': lambda n: min(2 ** n, 300),
                    'fragment': lambda n: min(2 ** n, 120),
                },
                'socket_timeout': 120,
                'extractor_retries': 10,
                'skip_unavailable_fragments': True,
                'keep_fragments': True,
                'concurrent_fragment_downloads': 4,
                'http_chunk_size': 10485760,
                'buffersize': 1024*1024,
                'continuedl': True,
                'noresizebuffer': True,
            }

            progress_bar.visible = True
            status_text.value = "🚀 جاري التحميل مع إعادة المحاولة التلقائية..."
            page.update()

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                nonlocal video_path
                video_path = ydl.prepare_filename(info)
                video_title = info.get('title', 'فيديو')
                status_text.value = f"✅ تم تحميل: {video_title}"
                progress_bar.visible = False
                split_btn.disabled = False
                page.update()

        except Exception as e:
            error_msg = str(e)
            retry_count += 1

            if (retry_count < 5 and
                any(keyword in error_msg.lower() for keyword in ['timeout', 'connection', 'network', 'http', 'fragment', 'unavailable'])):
                wait_time = min(2 ** retry_count, 30)
                status_text.value = f"🔄 خطأ شبكة - إعادة المحاولة {retry_count}/5 في {wait_time} ثانية..."
                page.update()
                threading.Timer(wait_time, lambda: download_video(url, retry_count)).start()
            else:
                status_text.value = f"❌ خطأ التحميل: {error_msg[:100]}"
                download_btn.disabled = False
                progress_bar.visible = False
                page.update()

    def progress_hook(d):
        try:
            if d['status'] == 'downloading':
                if d.get('total_bytes'):
                    percent = min(99, (d['downloaded_bytes'] / d['total_bytes']) * 100)
                    progress_bar.value = percent / 100
                    speed = d.get('speed', 0)
                    if speed:
                        speed_mb = speed / (1024 * 1024)
                        downloaded_mb = d['downloaded_bytes'] / (1024 * 1024)
                        total_mb = d['total_bytes'] / (1024 * 1024)
                        status_text.value = f"⏳ {percent:.0f}% - {downloaded_mb:.1f}MB/{total_mb:.1f}MB - {speed_mb:.1f}MB/s"
                    else:
                        status_text.value = f"⏳ جاري التحميل ({percent:.0f}%)..."
                    page.update()
            elif d['status'] == 'finished':
                progress_bar.value = 1.0
                page.update()
        except:
            pass

    def start_download(e):
        url = youtube_url.value.strip()
        if not url:
            status_text.value = "❌ أدخل رابط يوتيوب أولاً"
            page.update()
            return

        download_btn.disabled = True
        status_text.value = "⏳ جاري جلب معلومات الفيديو..."
        page.update()

        threading.Thread(target=lambda: download_video(url), daemon=True).start()

    def process_video():
        try:
            nonlocal video_path
            if not video_path:
                status_text.value = "❌ اختر فيديو أولاً"
                page.update()
                return

            output_folder = os.path.join(os.path.expanduser("~\\Desktop"), "مقاطع_الواتساب")
            if os.path.exists(output_folder):
                shutil.rmtree(output_folder)
            os.makedirs(output_folder)

            ffmpeg_path = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"

            status_text.value = "⏳ جاري حساب مدة الفيديو..."
            page.update()

            duration = get_video_duration(video_path)
            if duration <= 0:
                raise Exception("❌ لم يتمكن من قراءة مدة الفيديو")

            total_segments = int(duration / 5)
            if duration % 5 > 0:
                total_segments += 1

            status_text.value = f"⏳ جاري تقسيم الفيديو ({total_segments} أجزاء)..."
            progress_bar.visible = True
            progress_bar.value = 0
            page.update()

            for i in range(total_segments):
                start_time = i * 5
                end_time = min((i + 1) * 5, duration)

                output_file = os.path.join(output_folder, f"{i+1:03d}.mp4")

                command = [
                    ffmpeg_path,
                    "-i", video_path,
                    "-ss", str(start_time),
                    "-to", str(end_time),
                    "-c", "copy",
                    "-avoid_negative_ts", "make_zero",
                    "-y",
                    output_file
                ]

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                stdout, stderr = process.communicate(timeout=60)

                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "خطأ غير معروف"
                    raise Exception(f"فشل التقسيم في الجزء {i+1}: {error_msg[:200]}")

                progress = (i + 1) / total_segments
                progress_bar.value = progress
                status_text.value = f"✅ الجزء {i+1}/{total_segments} - تقسيم سريع"
                page.update()

            status_text.value = "✅ تمت العملية بنجاح!"
            progress_bar.visible = False
            download_btn.disabled = False
            split_btn.disabled = True
            page.update()

            # رسالة نجاح
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("نجاح!"),
                content=ft.Text("تم الحفظ في مجلد 'مقاطع_الواتساب' على سطح المكتب"),
                actions=[
                    ft.TextButton("حسناً", on_click=lambda e: close_dialog(dlg)),
                ],
            )
            page.dialog = dlg
            dlg.open = True
            page.update()

        except Exception as e:
            status_text.value = f"❌ خطأ: {str(e)[:100]}"
            progress_bar.visible = False
            download_btn.disabled = False
            split_btn.disabled = False
            page.update()

    def start_split(e):
        split_btn.disabled = True
        status_text.value = "⏳ جاري التقسيم..."
        page.update()
        threading.Thread(target=process_video, daemon=True).start()

    def close_dialog(dlg):
        dlg.open = False
        page.update()

    # ربط الأحداث
    download_btn.on_click = start_download
    split_btn.on_click = start_split

    # تخطيط الواجهة
    page.add(
        ft.Container(
            content=ft.Column([
                # العنوان
                ft.Container(
                    content=ft.Text("قاطع الفيديوهات الذكي", size=24, weight=ft.FontWeight.BOLD, color="#CBA6F7"),
                    alignment=ft.alignment.center,
                    padding=20
                ),

                # قسم يوتيوب
                ft.Container(
                    content=ft.Column([
                        ft.Text("تحميل من يوتيوب:", size=16, color="#CDD6F4"),
                        youtube_url,
                        download_btn,
                    ]),
                    padding=20
                ),

                # فاصل
                ft.Divider(height=20, color="#45475A"),

                # قسم الملفات المحلية
                ft.Container(
                    content=ft.Column([
                        ft.Text("أو اختر فيديو من جهازك:", size=16, color="#CDD6F4"),
                        ft.ElevatedButton("📁 اختر ملف", on_click=select_file),
                        split_btn,
                    ]),
                    padding=20
                ),

                # شريط التقدم والحالة
                ft.Container(
                    content=ft.Column([
                        status_text,
                        progress_bar,
                    ]),
                    padding=20
                ),
            ]),
            bgcolor="#1E1E2E",
            padding=0
        )
    )

if __name__ == "__main__":
    ft.app(target=main)