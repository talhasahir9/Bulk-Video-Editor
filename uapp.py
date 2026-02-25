import os
import sys
import threading
import tempfile
import traceback
import customtkinter as ctk
from tkinter import filedialog
import numpy as np

# --- WINDOWED MODE CRASH FIX ---
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
# -------------------------------

from moviepy.editor import VideoFileClip, CompositeVideoClip, ColorClip, CompositeAudioClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import AudioClip, AudioArrayClip
import moviepy.video.fx.all as vfx
import moviepy.audio.fx.all as afx 
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
        self.title("Sahir's Ultimate Bulk Editor (Ninja AI)")
        self.geometry("820x820") 
        self.minsize(720, 750)   
        
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

        # --- DASHBOARD CONTROLS (SCROLLABLE) ---
        self.frame_controls = ctk.CTkScrollableFrame(self)
        self.frame_controls.pack(pady=5, padx=20, fill="both", expand=True)
        
        self.ratio_label = ctk.CTkLabel(self.frame_controls, text="Aspect Ratio:")
        self.ratio_label.grid(row=0, column=0, padx=15, pady=(10,0), sticky="w")
        self.ratio_menu = ctk.CTkOptionMenu(self.frame_controls, values=["Original", "9:16 (Shorts/Reels)", "16:9 (YouTube)", "1:1 (Square)"])
        self.ratio_menu.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

        self.bg_label = ctk.CTkLabel(self.frame_controls, text="Background Fill:")
        self.bg_label.grid(row=0, column=1, padx=15, pady=(10,0), sticky="w")
        self.bg_menu = ctk.CTkOptionMenu(self.frame_controls, values=["Blur Video", "Half Fit (Blur Background)", "Zoom to Fit (Fill Frame)", "Black", "White", "Dark Gray"])
        self.bg_menu.grid(row=1, column=1, padx=15, pady=5, sticky="ew")

        self.res_label = ctk.CTkLabel(self.frame_controls, text="Output Resolution:")
        self.res_label.grid(row=2, column=0, padx=15, pady=(10,0), sticky="w")
        self.res_menu = ctk.CTkOptionMenu(self.frame_controls, values=["Original", "720p", "1080p", "2K", "4K"])
        self.res_menu.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        self.filter_label = ctk.CTkLabel(self.frame_controls, text="Unique Filter:")
        self.filter_label.grid(row=2, column=1, padx=15, pady=(10,0), sticky="w")
        self.filter_menu = ctk.CTkOptionMenu(self.frame_controls, values=["None", "Color Boost (1.2x)", "Black & White", "Slight Zoom"])
        self.filter_menu.grid(row=3, column=1, padx=15, pady=5, sticky="ew")

        self.batch_label = ctk.CTkLabel(self.frame_controls, text="Batch Size (Videos at once):")
        self.batch_label.grid(row=4, column=0, padx=15, pady=(10,0), sticky="w")
        self.batch_menu = ctk.CTkOptionMenu(self.frame_controls, values=["1", "2", "3", "5", "10"])
        self.batch_menu.set("3")
        self.batch_menu.grid(row=5, column=0, padx=15, pady=5, sticky="ew")

        self.engine_label = ctk.CTkLabel(self.frame_controls, text="Render Engine (Speed):")
        self.engine_label.grid(row=4, column=1, padx=15, pady=(10,0), sticky="w")
        self.engine_menu = ctk.CTkOptionMenu(self.frame_controls, values=["CPU (Standard)", "GPU (Nvidia Fast)"])
        self.engine_menu.set("CPU (Standard)")
        self.engine_menu.grid(row=5, column=1, padx=15, pady=5, sticky="ew")

        self.color_label = ctk.CTkLabel(self.frame_controls, text="Progress Bar Color:")
        self.color_label.grid(row=6, column=0, padx=15, pady=(10,0), sticky="w")
        self.color_menu = ctk.CTkOptionMenu(self.frame_controls, values=["Red", "Green", "Blue", "Yellow", "Cyan", "Magenta", "White"])
        self.color_menu.set("Red")
        self.color_menu.grid(row=7, column=0, padx=15, pady=5, sticky="ew")

        self.flip_var = ctk.BooleanVar(value=True)
        self.check_flip = ctk.CTkSwitch(self.frame_controls, text="Flip Horizontally", variable=self.flip_var)
        self.check_flip.grid(row=6, column=1, padx=15, pady=(15,5), sticky="w")

        # --- NAYA OPTION: AI AUTO-TEXT HIDER ---
        self.auto_text_var = ctk.BooleanVar(value=False)
        self.check_auto_text = ctk.CTkSwitch(self.frame_controls, text="AI Auto-Hide Captions/Watermark", variable=self.auto_text_var)
        self.check_auto_text.grid(row=7, column=1, padx=15, pady=(5,5), sticky="w")

        self.anti_copy_var = ctk.BooleanVar(value=True) 
        self.check_anti_copy = ctk.CTkSwitch(self.frame_controls, text="Anti-Copyright Visuals", variable=self.anti_copy_var)
        self.check_anti_copy.grid(row=8, column=1, padx=15, pady=(5,5), sticky="w")

        self.audio_lbl = ctk.CTkLabel(self.frame_controls, text="🎧 Audio Hacker (Bypass):", font=("Helvetica", 14, "bold"))
        self.audio_lbl.grid(row=9, column=0, padx=15, pady=(15,0), sticky="w")

        self.mask_noise_var = ctk.BooleanVar(value=True)
        self.check_mask = ctk.CTkSwitch(self.frame_controls, text="Add White Noise Mask (2%)", variable=self.mask_noise_var)
        self.check_mask.grid(row=10, column=0, padx=15, pady=(5,5), sticky="w")

        self.reverb_var = ctk.BooleanVar(value=False)
        self.check_reverb = ctk.CTkSwitch(self.frame_controls, text="Add Reverb / Echo", variable=self.reverb_var)
        self.check_reverb.grid(row=10, column=1, padx=15, pady=(5,5), sticky="w")

        self.clean_audio_var = ctk.BooleanVar(value=False)
        self.check_audio = ctk.CTkSwitch(self.frame_controls, text="Clean Audio (Noise Reducer)", variable=self.clean_audio_var)
        self.check_audio.grid(row=11, column=0, padx=15, pady=(5,5), sticky="w")

        self.speed_label = ctk.CTkLabel(self.frame_controls, text="Speed: 1.15x")
        self.speed_label.grid(row=11, column=1, padx=15, pady=(5,0), sticky="w")

        self.slider_speed = ctk.CTkSlider(self.frame_controls, from_=0.5, to=2.0, command=self.update_speed_label)
        self.slider_speed.set(1.15)
        self.slider_speed.grid(row=12, column=1, padx=15, pady=(0,15), sticky="ew")

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
        self.progress_frame = ctk.CTkScrollableFrame(self, height=130)
        self.progress_frame.pack(fill="x", padx=20, pady=(0, 20))

    def create_ui_bar(self, filename):
        frame = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        display_name = (filename[:20] + '..') if len(filename) > 20 else filename
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
                short_err = error_msg[:25] + "..." if len(error_msg) > 25 else error_msg
                self.active_bars[filename]["label"].configure(text=f"❌ {short_err}", text_color="#dc3545")

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

    def make_even(self, num):
        return int(num) if int(num) % 2 == 0 else int(num) + 1

    # --- THE NINJA HACK: OpenCV Text Box Locator ---
    def detect_text_areas(self, clip):
        boxes = []
        try:
            times_to_scan = [clip.duration * 0.3, clip.duration * 0.7] # 30% aur 70% duration par check karega
            for t in times_to_scan:
                frame = clip.get_frame(t)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                h, w = gray.shape
                
                # Morphological Math to find text blocks
                rectKernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 7))
                grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, rectKernel)
                _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                connected = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, rectKernel)
                contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for c in contours:
                    bx, by, bw_w, bw_h = cv2.boundingRect(c)
                    # Agar box lamba hai aur text jaisa lag raha hai
                    if bw_w > 50 and bw_h > 15 and bw_w > bw_h:
                        # Sirf screen ke Top 20% aur Bottom 30% ko check karo taake face blur na ho
                        if by < h * 0.20 or by > h * 0.70:
                            boxes.append((bx, by, bw_w, bw_h))
            
            # Combine duplicate boxes
            merged_boxes = []
            for b in boxes:
                covered = False
                for mb in merged_boxes:
                    if abs(b[0]-mb[0]) < 50 and abs(b[1]-mb[1]) < 50:
                        covered = True
                        break
                if not covered:
                    merged_boxes.append(b)
            return merged_boxes
        except:
            return []

    def process_single_video(self, input_path, filename, params): 
        temp_wav_path = None
        clean_wav_path = None
        new_audio_clip = None
        bg_clip = None
        
        try:
            self.after(0, self.create_ui_bar, filename)
            output_path = os.path.join(self.output_folder, f"edited_{filename}")
            
            clip = VideoFileClip(input_path)
            original_fps = clip.fps if clip.fps else 30.0
            
            raw_target_w, raw_target_h = self.get_resolution_dims(params['res_val'], params['ratio_val'], clip.w, clip.h)
            target_w = self.make_even(raw_target_w)
            target_h = self.make_even(raw_target_h)
            
            inner_w = self.make_even(target_w - (2 * params['border_size']))
            inner_h = self.make_even(target_h - (2 * params['border_size']))
            
            bg_type = params['bg_val']
            if bg_type in ["Blur Video", "Zoom to Fit (Fill Frame)", "Half Fit (Blur Background)"]:
                def blur_frame(frame):
                    safe_frame = frame[:,:,:3] if frame.shape[2] == 4 else frame
                    small = cv2.resize(safe_frame, (0,0), fx=0.5, fy=0.5)
                    blurred_small = cv2.GaussianBlur(small, (51, 51), 0)
                    return cv2.resize(blurred_small, (safe_frame.shape[1], safe_frame.shape[0]))
                
                bg_clip = clip.resize(newsize=(target_w, target_h)).fl_image(blur_frame)
            else:
                colors = {"Black": (0,0,0), "White": (255,255,255), "Dark Gray": (50,50,50)}
                bg_clip = ColorClip(size=(target_w, target_h), color=colors.get(bg_type, (0,0,0)), duration=clip.duration)

            bg_clip = bg_clip.set_fps(original_fps)

            if bg_type == "Zoom to Fit (Fill Frame)":
                box_w, box_h = inner_w, inner_h
                scale = max(box_w / clip.w, box_h / clip.h)
                resized_clip = clip.resize(scale)
                main_clip = resized_clip.fx(vfx.crop, x_center=resized_clip.w/2, y_center=resized_clip.h/2, width=box_w, height=box_h)
            elif bg_type == "Half Fit (Blur Background)":
                box_w = inner_w
                box_h = self.make_even(inner_h * 0.60)
                scale = max(box_w / clip.w, box_h / clip.h)
                resized_clip = clip.resize(scale)
                main_clip = resized_clip.fx(vfx.crop, x_center=resized_clip.w/2, y_center=resized_clip.h/2, width=box_w, height=box_h)
            else:
                scale = min(inner_w / clip.w, inner_h / clip.h)
                main_clip = clip.resize(scale)

            # --- SMART AI CAPTION HIDER APLY KAREIN ---
            if params['auto_text']:
                text_boxes = self.detect_text_areas(main_clip)
                if text_boxes:
                    def hide_text(frame):
                        safe_frame = frame[:,:,:3].copy() if frame.shape[2] == 4 else frame.copy()
                        for (x, y, w, h) in text_boxes:
                            pad = 15 # Caption se thora bahar tak blur karega
                            x1 = max(0, x - pad)
                            y1 = max(0, y - pad)
                            x2 = min(safe_frame.shape[1], x + w + pad)
                            y2 = min(safe_frame.shape[0], y + h + pad)
                            
                            roi = safe_frame[y1:y2, x1:x2]
                            if roi.size > 0:
                                blurred_roi = cv2.GaussianBlur(roi, (51, 51), 0)
                                safe_frame[y1:y2, x1:x2] = blurred_roi
                        return safe_frame
                    main_clip = main_clip.fl_image(hide_text)
            # -------------------------------------------

            layers_to_composite = []
            if params['anti_copy']:
                base_white = ColorClip(size=(target_w, target_h), color=(255, 255, 255), duration=clip.duration)
                base_white = base_white.set_fps(original_fps)
                layers_to_composite.append(base_white)
            
            layers_to_composite.append(bg_clip)
            layers_to_composite.append(main_clip.set_position("center"))
            
            final_clip = CompositeVideoClip(layers_to_composite)

            if params['do_flip']: final_clip = final_clip.fx(vfx.mirror_x)
            if params['speed_val'] != 1.0: final_clip = final_clip.fx(vfx.speedx, params['speed_val'])
            if params['filter_val'] == "Color Boost (1.2x)": final_clip = final_clip.fx(vfx.colorx, 1.2)
            elif params['filter_val'] == "Black & White": final_clip = final_clip.fx(vfx.blackwhite)
            elif params['filter_val'] == "Slight Zoom": final_clip = final_clip.fx(vfx.crop, x_center=final_clip.w/2, y_center=final_clip.h/2, width=final_clip.w*0.9, height=final_clip.h*0.9).resize(width=final_clip.w)

            if params['anti_copy']:
                top_invisible_layer = ColorClip(size=(target_w, target_h), color=(255, 255, 255), duration=final_clip.duration).set_opacity(0.01)
                top_invisible_layer = top_invisible_layer.set_fps(original_fps)
                final_clip = CompositeVideoClip([final_clip, top_invisible_layer])

            if final_clip.audio is not None:
                audio_layers = [final_clip.audio]
                
                if params['clean_audio']:
                    try:
                        temp_dir = tempfile.gettempdir()
                        temp_wav_path = os.path.join(temp_dir, f"temp_{filename}.wav")
                        clean_wav_path = os.path.join(temp_dir, f"clean_{filename}.wav")
                        
                        final_clip.audio.write_audiofile(temp_wav_path, fps=44100, logger=None)
                        rate, data = wavfile.read(temp_wav_path)
                        reduced_data = nr.reduce_noise(y=data.T, sr=rate)
                        wavfile.write(clean_wav_path, rate, reduced_data.T)
                        
                        new_audio_clip = AudioFileClip(clean_wav_path)
                        audio_layers = [new_audio_clip] 
                    except Exception as audio_err:
                        pass

                if params['mask_noise']:
                    total_samples = int(44100 * final_clip.duration)
                    noise_array = np.random.uniform(-0.02, 0.02, (total_samples, 2))
                    noise_clip = AudioArrayClip(noise_array, fps=44100)
                    audio_layers.append(noise_clip)

                if params['reverb']:
                    echo_clip = audio_layers[0].set_start(0.05).fx(afx.volumex, 0.3)
                    audio_layers.append(echo_clip)

                if len(audio_layers) > 1:
                    final_audio = CompositeAudioClip(audio_layers)
                    final_audio = final_audio.set_duration(final_clip.duration)
                    final_audio.fps = 44100 
                    final_clip = final_clip.set_audio(final_audio)
                elif new_audio_clip:
                    final_clip = final_clip.set_audio(new_audio_clip)

            duration = final_clip.duration
            b_size = params['border_size']
            prog_color = params['prog_color']
            
            def add_4sided_progress(get_frame, t):
                orig_frame = get_frame(t)
                safe_frame = orig_frame[:, :, :3].copy() if orig_frame.shape[2] == 4 else orig_frame.copy()
                
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

            selected_codec = "libx264"
            if params['engine'] == "GPU (Nvidia Fast)":
                selected_codec = "h264_nvenc" 

            final_clip.write_videofile(
                output_path, 
                fps=original_fps,   
                codec=selected_codec, 
                audio_codec="aac", 
                bitrate="4000k",      
                preset="ultrafast",   
                threads=4,          
                logger=custom_logger 
            )
            
            clip.close(); main_clip.close(); final_clip.close()
            if bg_clip: bg_clip.close()
            if params['anti_copy']: 
                base_white.close()
                top_invisible_layer.close()
            if new_audio_clip: new_audio_clip.close()
            
            self.after(0, self.complete_ui_bar, filename, True)
            return True, filename
            
        except Exception as e:
            error_details = traceback.format_exc()
            try:
                with open("error_log.txt", "a", encoding="utf-8") as f:
                    f.write(f"--- ERROR IN {filename} ---\n{error_details}\n\n")
            except:
                pass
            
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
            'anti_copy': self.anti_copy_var.get(), 
            'auto_text': self.auto_text_var.get(), # <-- Ninja AI Hider On/Off
            'mask_noise': self.mask_noise_var.get(),
            'reverb': self.reverb_var.get(),
            'engine': self.engine_menu.get(), 
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
