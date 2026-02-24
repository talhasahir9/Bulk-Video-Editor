import os
import threading
import tempfile
import customtkinter as ctk
from tkinter import filedialog
import numpy as np
from moviepy.editor import VideoFileClip, CompositeVideoClip, ColorClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
import moviepy.video.fx.all as vfx
import cv2
import noisereduce as nr
from scipy.io import wavfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from proglog import ProgressBarLogger

# Modern UI Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class LiveVideoLogger(ProgressBarLogger):
    def __init__(self, filename, update_callback):
        super().__init__()
        self.filename = filename
        self.update_callback = update_callback

    def bars_callback(self, bar, attr, value, old_value=None):
        if bar == 't':
            total = self.bars[bar]['total']
            if total > 0:
                progress = value / total
                self.update_callback(self.filename, progress)

class UltimateBulkEditor(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sahir's Ultimate Bulk Editor")
        self.geometry("800x820") 
        self.minsize(700, 750)   
        
        self.input_files = [] 
        self.output_folder = ""
        self.active_bars = {} 

        # --- HEADER ---
        self.title_label = ctk.CTkLabel(self, text="🎬 Sahir's Pro Editor", font=("Helvetica", 26, "bold"))
        self.title_label.pack(pady=(15, 5))

        # --- FOLDERS & FILES ---
        self.frame_folders = ctk.CTkFrame(self)
        self.frame_folders.pack(pady=5, padx=20, fill="x")
        
        self.btn_input = ctk.CTkButton(self.frame_folders, text="📂 Select Videos", command=self.select_input_files)
        self.btn_input.pack(side="left", padx=10, pady=10, expand=True)
        
        self.btn_output = ctk.CTkButton(self.frame_folders, text="📁 Select Output Folder", command=self.select_output)
        self.btn_output.pack(side="right", padx=10, pady=10, expand=True)
        
        self.folder_status_label = ctk.CTkLabel(self, text="Videos aur Output folder select karein...", text_color="gray")
        self.folder_status_label.pack(pady=5)

        # --- DASHBOARD CONTROLS ---
        self.frame_controls = ctk.CTkFrame(self)
        self.frame_controls.pack(pady=5, padx=20, fill="x") 
        
        # Row 1: Ratio & Background
        self.ratio_label = ctk.CTkLabel(self.frame_controls, text="Aspect Ratio:")
        self.ratio_label.grid(row=0, column=0, padx=15, pady=(10,0), sticky="w")
        self.ratio_menu = ctk.CTkOptionMenu(self.frame_controls, values=["Original", "9:16 (Shorts/Reels)", "16:9 (YouTube)", "1:1 (Square)"])
        self.ratio_menu.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

        self.bg_label = ctk.CTkLabel(self.frame_controls, text="Background Fill:")
        self.bg_label.grid(row=0, column=1, padx=15, pady=(10,0), sticky="w")
        self.bg_menu = ctk.CTkOptionMenu(self.frame_controls, values=["Blur Video", "Black", "White", "Dark Gray"])
        self.bg_menu.grid(row=1, column=1, padx=15, pady=5, sticky="ew")

        # Row 2: Resolution & Filter
        self.res_label = ctk.CTkLabel(self.frame_controls, text="Output Resolution:")
        self.res_label.grid(row=2, column=0, padx=15, pady=(10,0), sticky="w")
        self.res_menu = ctk.CTkOptionMenu(self.frame_controls, values=["Original", "720p", "1080p", "2K", "4K"])
        self.res_menu.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        self.filter_label = ctk.CTkLabel(self.frame_controls, text="Unique Filter:")
        self.filter_label.grid(row=2, column=1, padx=15, pady=(10,0), sticky="w")
        self.filter_menu = ctk.CTkOptionMenu(self.frame_controls, values=["None", "Color Boost (1.2x)", "Black & White", "Slight Zoom"])
        self.filter_menu.grid(row=3, column=1, padx=15, pady=5, sticky="ew")

        # Row 3: Batch Size & Progress Color
        self.batch_label = ctk.CTkLabel(self.frame_controls, text="Batch Size (Videos at once):")
        self.batch_label.grid(row=4, column=0, padx=15, pady=(10,0), sticky="w")
        self.batch_menu = ctk.CTkOptionMenu(self.frame_controls, values=["1", "2", "3", "5", "10"])
        self.batch_menu.set("3")
        self.batch_menu.grid(row=5, column=0, padx=15, pady=5, sticky="ew")

        self.color_label = ctk.CTkLabel(self.frame_controls, text="Progress Bar Color:")
        self.color_label.grid(row=4, column=1, padx=15, pady=(10,0), sticky="w")
        self.color_menu = ctk.CTkOptionMenu(self.frame_controls, values=["Red", "Green", "Blue", "Yellow", "Cyan", "Magenta", "White"])
        self.color_menu.set("Red")
        self.color_menu.grid(row=5, column=1, padx=15, pady=5, sticky="ew")

        # Row 4: Toggles (Flip & Audio)
        self.flip_var = ctk.BooleanVar(value=True)
        self.check_flip = ctk.CTkSwitch(self.frame_controls, text="Flip Horizontally", variable=self.flip_var)
        self.check_flip.grid(row=6, column=0, padx=15, pady=(20,5), sticky="w")

        self.clean_audio_var = ctk.BooleanVar(value=False)
        self.check_audio = ctk.CTkSwitch(self.frame_controls, text="Clean Audio (Remove Noise)", variable=self.clean_audio_var)
        self.check_audio.grid(row=6, column=1, padx=15, pady=(20,5), sticky="w")

        # Row 5: Speed Slider
        self.speed_label = ctk.CTkLabel(self.frame_controls, text="Speed: 1.15x")
        self.speed_label.grid(row=7, column=0, padx=15, pady=(10,0), sticky="w")
        self.slider_speed = ctk.CTkSlider(self.frame_controls, from_=0.5, to=2.0, command=self.update_speed_label)
        self.slider_speed.set(1.15)
        self.slider_speed.grid(row=8, column=0, columnspan=2, padx=15, pady=(0,15), sticky="ew")

        self.frame_controls.grid_columnconfigure(0, weight=1)
        self.frame_controls.grid_columnconfigure(1, weight=1)

        # --- ACTION BAR ---
        self.frame_action = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_action.pack(pady=(10, 5), padx=20, fill="x")

        self.btn_start = ctk.CTkButton(self.frame_action, text="▶ Start Processing", font=("Helvetica", 16, "bold"), fg_color="#28a745", hover_color="#218838", height=40, command=self.start_processing)
        self.btn_start.pack(side="left", padx=(0, 15))

        self.status_label = ctk.CTkLabel(self.frame_action, text="Ready to start!", font=("Helvetica", 14), text_color="gray", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)

        # --- SCROLLABLE PROGRESS ---
        self.progress_frame = ctk.CTkScrollableFrame(self)
        self.progress_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def create_ui_bar(self, filename):
        frame = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        display_name = (filename[:25] + '..') if len(filename) > 25 else filename
        lbl = ctk.CTkLabel(frame, text=f"{display_name} - 0%", font=("Helvetica", 12), width=150, anchor="w")
        lbl.pack(side="left", padx=5)
        bar = ctk.CTkProgressBar(frame)
        bar.set(0.0)
        bar.pack(side="right", padx=5, fill="x", expand=True)
        self.active_bars[filename] = {"frame": frame, "label": lbl, "bar": bar}

    def update_ui_bar(self, filename, progress):
        if filename in self.active_bars:
            self.active_bars[filename]["bar"].set(progress)
            self.active_bars[filename]["label"].configure(text=f"{(filename[:20]+'..') if len(filename)>20 else filename} - {int(progress*100)}%")

    def complete_ui_bar(self, filename, success, error_msg=""):
        if filename in self.active_bars:
            if success:
                self.active_bars[filename]["bar"].set(1.0)
                self.active_bars[filename]["label"].configure(text=f"✅ {filename[:20]}", text_color="#28a745")
            else:
                self.active_bars[filename]["label"].configure(text=f"❌ ERROR: {filename[:15]}", text_color="#dc3545")

    def update_speed_label(self, value):
        self.speed_label.configure(text=f"Speed: {round(value, 2)}x")

    def select_input_files(self):
        files = filedialog.askopenfilenames(title="Select Videos", filetypes=[("Video Files", "*.mp4 *.mov *.mkv"), ("All Files", "*.*")])
        if files:
            self.input_files = list(files) 
            self.folder_status_label.configure(text=f"Selected {len(self.input_files)} videos | Output: {os.path.basename(self.output_folder) if self.output_folder else 'Not Selected'}")

    def select_output(self):
        self.output_folder = filedialog.askdirectory(title="Select Output Folder")
        if self.output_folder:
            file_count = len(self.input_files)
            self.folder_status_label.configure(text=f"Selected {file_count} videos | Output: {os.path.basename(self.output_folder)}")

    def get_resolution_dims(self, res_name, ratio_name, orig_w, orig_h):
        dims = {"720p": (1280, 720), "1080p": (1920, 1080), "2K": (2560, 1440), "4K": (3840, 2160)}
        w, h = dims[res_name] if res_name != "Original" else (orig_w, orig_h)
        if ratio_name == "9:16 (Shorts/Reels)": return min(w, h), max(w, h) 
        elif ratio_name == "16:9 (YouTube)": return max(w, h), min(w, h) 
        elif ratio_name == "1:1 (Square)": size = min(w, h); return size, size
        return w, h

    def process_single_video(self, input_path, filename, params): 
        temp_wav_path = None
        clean_wav_path = None
        new_audio_clip = None
        
        try:
            self.after(0, self.create_ui_bar, filename)
            output_path = os.path.join(self.output_folder, f"edited_{filename}")
            
            clip = VideoFileClip(input_path)
            
            # --- YAHAN FPS EXTRACT HO RAHA HAI ---
            original_fps = clip.fps if clip.fps else 30
            
            target_w, target_h = self.get_resolution_dims(params['res_val'], params['ratio_val'], clip.w, clip.h)
            
            inner_w = target_w - (2 * params['border_size'])
            inner_h = target_h - (2 * params['border_size'])
            main_clip = clip.resize(width=inner_w) if (clip.w / clip.h) > (inner_w / inner_h) else clip.resize(height=inner_h)
            
            if params['bg_val'] == "Blur Video":
                def blur_frame(frame):
                    safe_frame = np.zeros((frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
                    if frame.shape[2] == 4: safe_frame[:,:,:] = frame[:,:,:3]
                    else: safe_frame[:,:,:] = frame
                    return cv2.GaussianBlur(safe_frame, (99, 99), 0)
                bg_clip = clip.resize(newsize=(target_w, target_h)).fl_image(blur_frame)
            else:
                colors = {"Black": (0,0,0), "White": (255,255,255), "Dark Gray": (50,50,50)}
                bg_clip = ColorClip(size=(target_w, target_h), color=colors.get(params['bg_val'], (0,0,0)), duration=clip.duration)

            final_clip = CompositeVideoClip([bg_clip, main_clip.set_position("center")])

            if params['do_flip']: final_clip = final_clip.fx(vfx.mirror_x)
            if params['speed_val'] != 1.0: final_clip = final_clip.fx(vfx.speedx, params['speed_val'])
            if params['filter_val'] == "Color Boost (1.2x)": final_clip = final_clip.fx(vfx.colorx, 1.2)
            elif params['filter_val'] == "Black & White": final_clip = final_clip.fx(vfx.blackwhite)
            elif params['filter_val'] == "Slight Zoom": final_clip = final_clip.fx(vfx.crop, x_center=final_clip.w/2, y_center=final_clip.h/2, width=final_clip.w*0.9, height=final_clip.h*0.9).resize(width=final_clip.w)

            # Audio Processing
            if params['clean_audio'] and final_clip.audio is not None:
                try:
                    temp_dir = tempfile.gettempdir()
                    temp_wav_path = os.path.join(temp_dir, f"temp_{filename}.wav")
                    clean_wav_path = os.path.join(temp_dir, f"clean_{filename}.wav")
                    
                    final_clip.audio.write_audiofile(temp_wav_path, fps=44100, logger=None)
                    rate, data = wavfile.read(temp_wav_path)
                    reduced_data = nr.reduce_noise(y=data.T, sr=rate)
                    wavfile.write(clean_wav_path, rate, reduced_data.T)
                    
                    new_audio_clip = AudioFileClip(clean_wav_path)
                    final_clip = final_clip.set_audio(new_audio_clip)
                except Exception as audio_err:
                    print(f"Audio cleaning failed for {filename}, using original. Error: {audio_err}")

            duration = final_clip.duration
            b_size = params['border_size']
            prog_color = params['prog_color']
            
            def add_4sided_progress(get_frame, t):
                orig_frame = get_frame(t)
                safe_frame = np.zeros((orig_frame.shape[0], orig_frame.shape[1], 3), dtype=np.uint8)
                if orig_frame.shape[2] == 4: safe_frame[:,:,:] = orig_frame[:,:,:3]
                else: safe_frame[:,:,:] = orig_frame
                
                h, w, _ = safe_frame.shape
                total_perimeter = 2 * w + 2 * h
                current_distance = int((t / duration) * total_perimeter)
                
                if current_distance > 0:
                    cv2.rectangle(safe_frame, (0, 0), (min(current_distance, w), b_size), prog_color, -1)
                if current_distance > w:
                    dist_down = min(current_distance - w, h)
                    cv2.rectangle(safe_frame, (w - b_size, 0), (w, dist_down), prog_color, -1)
                if current_distance > w + h:
                    dist_left = min(current_distance - w - h, w)
                    cv2.rectangle(safe_frame, (w - dist_left, h - b_size), (w, h), prog_color, -1)
                if current_distance > 2 * w + h:
                    dist_up = min(current_distance - 2 * w - h, h)
                    cv2.rectangle(safe_frame, (0, h - dist_up), (b_size, h), prog_color, -1)

                return safe_frame
                
            final_clip = final_clip.fl(add_4sided_progress)

            def ui_update_callback(fname, progress):
                self.after(0, self.update_ui_bar, fname, progress)

            custom_logger = LiveVideoLogger(filename, ui_update_callback)

            # --- YAHAN FPS AUR THREADS KA FIX APPLY KIYA HAI ---
            final_clip.write_videofile(
                output_path, 
                fps=original_fps,   # <--- Original frame rate use karega
                codec="libx264", 
                audio_codec="aac", 
                bitrate="8000k", 
                preset="medium", 
                threads=4,          # <--- Rendering stable aur smooth banayega
                logger=custom_logger 
            )
            
            clip.close(); main_clip.close(); bg_clip.close(); final_clip.close()
            if new_audio_clip: new_audio_clip.close()
            
            self.after(0, self.complete_ui_bar, filename, True)
            return True, filename
            
        except Exception as e:
            self.after(0, self.complete_ui_bar, filename, False, str(e))
            return False, f"{filename}: {str(e)}"
            
        finally:
            if temp_wav_path and os.path.exists(temp_wav_path):
                try: os.remove(temp_wav_path)
                except: pass
            if clean_wav_path and os.path.exists(clean_wav_path):
                try: os.remove(clean_wav_path)
                except: pass

    def start_processing(self):
        if not self.input_files or not self.output_folder:
            self.status_label.configure(text="⚠️ Pehle Videos & Output Folder select karein!", text_color="#ffcc00")
            return
        self.btn_start.configure(state="disabled")
        for widget in self.progress_frame.winfo_children():
            widget.destroy()
        self.active_bars.clear()
        threading.Thread(target=self.run_batch, daemon=True).start()

    def run_batch(self):
        total_videos = len(self.input_files) 
        
        color_map = {
            "Red": (0, 0, 255), "Green": (0, 255, 0), "Blue": (255, 0, 0),
            "Yellow": (0, 255, 255), "Cyan": (255, 255, 0), 
            "Magenta": (255, 0, 255), "White": (255, 255, 255)
        }
        
        params = {
            'do_flip': self.flip_var.get(), 'speed_val': self.slider_speed.get(),
            'ratio_val': self.ratio_menu.get(), 'bg_val': self.bg_menu.get(),
            'res_val': self.res_menu.get(), 'filter_val': self.filter_menu.get(),
            'prog_color': color_map.get(self.color_menu.get(), (0, 0, 255)),
            'clean_audio': self.clean_audio_var.get(),
            'border_size': 10
        }
        
        max_workers = int(self.batch_menu.get())
        completed = 0
        self.status_label.configure(text=f"Processing... (0/{total_videos})", text_color="#17a2b8")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_video = {}
            for file_path in self.input_files:
                filename = os.path.basename(file_path)
                future = executor.submit(self.process_single_video, file_path, filename, params)
                future_to_video[future] = filename
            
            for future in as_completed(future_to_video):
                success, result = future.result()
                completed += 1
                self.status_label.configure(text=f"Progress: {completed}/{total_videos} videos done!", text_color="#17a2b8")
        
        self.status_label.configure(text=f"✅ All {total_videos} videos successfully processed!", text_color="#28a745")
        self.btn_start.configure(state="normal")

if __name__ == "__main__":
    app = UltimateBulkEditor()
    app.mainloop()
