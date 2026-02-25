import os
import sys
import time # <-- YEH NAYA IMPORT ADD KIYA HAI DELETE LOOP KE LIYE
import threading
import tempfile
import traceback
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageTk
import numpy as np
import uuid 

# --- GOOGLE DRIVE OAUTH LIBRARIES ---
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
# ------------------------------------

# --- WINDOWED MODE CRASH FIX ---
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
# -------------------------------

from moviepy.editor import VideoFileClip, CompositeVideoClip, ColorClip, CompositeAudioClip, ImageClip
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
        self.title("Sahir's Ultimate Bulk Editor (Google Drive OAuth)")
        self.geometry("820x920") 
        self.minsize(720, 850)   
        
        self.input_files = [] 
        self.output_folder = ""
        self.active_bars = {} 
        self.custom_blur_boxes = [] 

        # --- HEADER ---
        self.title_label = ctk.CTkLabel(self, text="🎬 Sahir's Pro Editor", font=("Helvetica", 26, "bold"))
        self.title_label.pack(pady=(15, 5))

        # --- FOLDERS & DRIVE SETTINGS ---
        self.frame_folders = ctk.CTkFrame(self)
        self.frame_folders.pack(pady=5, padx=20, fill="x")
        
        self.btn_input = ctk.CTkButton(self.frame_folders, text="📂 Select Videos", command=self.select_input_files)
        self.btn_input.pack(side="left", padx=10, pady=10, expand=True)
        
        self.btn_output = ctk.CTkButton(self.frame_folders, text="📁 Select Output Folder", command=self.select_output)
        self.btn_output.pack(side="right", padx=10, pady=10, expand=True)

        self.folder_status_label = ctk.CTkLabel(self.frame_folders, text="Videos aur Output folder select karein...", text_color="gray")
        self.folder_status_label.pack(side="bottom", pady=5)

        # GOOGLE DRIVE FOLDER ID INPUT
        self.drive_id_var = ctk.StringVar()
        self.entry_drive = ctk.CTkEntry(self, textvariable=self.drive_id_var, placeholder_text="Paste Google Drive Folder ID Here (e.g. 1A2b3C4d5ExYz...)", width=400)
        self.entry_drive.pack(pady=(5, 5), padx=20, fill="x")

        # --- DASHBOARD CONTROLS ---
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

        # --- Auto-Trim & Custom Blur ---
        self.auto_trim_var = ctk.BooleanVar(value=True)
        self.check_auto_trim = ctk.CTkSwitch(self.frame_controls, text="✂️ Auto-Trim (Cut 1s Start/End)", variable=self.auto_trim_var)
        self.check_auto_trim.grid(row=8, column=0, padx=15, pady=(15,0), sticky="w")

        self.blur_frame_label = ctk.CTkLabel(self.frame_controls, text="🚫 Optional: Custom Caption Hider", font=("Helvetica", 12, "bold"))
        self.blur_frame_label.grid(row=7, column=1, padx=15, pady=(15,0), sticky="w")
        
        self.btn_draw_blur = ctk.CTkButton(self.frame_controls, text="✏️ Draw Custom Blur Areas", command=self.draw_custom_blur, fg_color="#ff9900", hover_color="#e68a00", text_color="black")
        self.btn_draw_blur.grid(row=8, column=1, padx=15, pady=5, sticky="ew")
        
        # --- Audio Hacker & Blur Status ---
        self.audio_lbl = ctk.CTkLabel(self.frame_controls, text="🎧 Audio Hacker (Bypass):", font=("Helvetica", 14, "bold"))
        self.audio_lbl.grid(row=9, column=0, padx=15, pady=(10,0), sticky="w")

        self.blur_status_label = ctk.CTkLabel(self.frame_controls, text="Status: App will not blur any area", text_color="gray", font=("Helvetica", 10))
        self.blur_status_label.grid(row=9, column=1, padx=15, pady=(0,5), sticky="w")

        # --- Mask Noise & Anti-Copy Visuals ---
        self.mask_noise_var = ctk.BooleanVar(value=True)
        self.check_mask = ctk.CTkSwitch(self.frame_controls, text="Add White Noise Mask (2%)", variable=self.mask_noise_var)
        self.check_mask.grid(row=10, column=0, padx=15, pady=(5,5), sticky="w")

        self.anti_copy_var = ctk.BooleanVar(value=True) 
        self.check_anti_copy = ctk.CTkSwitch(self.frame_controls, text="Anti-Copyright Visuals (White Layer)", variable=self.anti_copy_var)
        self.check_anti_copy.grid(row=10, column=1, padx=15, pady=(5,5), sticky="w")

        # --- Reverb & Invisible Grain ---
        self.reverb_var = ctk.BooleanVar(value=False)
        self.check_reverb = ctk.CTkSwitch(self.frame_controls, text="Add Reverb / Echo", variable=self.reverb_var)
        self.check_reverb.grid(row=11, column=0, padx=15, pady=(5,5), sticky="w")

        self.film_grain_var = ctk.BooleanVar(value=True) 
        self.check_film_grain = ctk.CTkSwitch(self.frame_controls, text="🎬 Invisible Film Grain (Hash Buster)", variable=self.film_grain_var)
        self.check_film_grain.grid(row=11, column=1, padx=15, pady=(5,5), sticky="w")

        # --- Clean Audio ---
        self.clean_audio_var = ctk.BooleanVar(value=False)
        self.check_audio = ctk.CTkSwitch(self.frame_controls, text="Clean Audio (Noise Reducer)", variable=self.clean_audio_var)
        self.check_audio.grid(row=12, column=0, padx=15, pady=(5,5), sticky="w")

        # --- AUTO UPLOAD ---
        self.upload_var = ctk.BooleanVar(value=False)
        self.check_upload = ctk.CTkSwitch(self.frame_controls, text="☁️ Auto-Upload to G-Drive & Delete Local", variable=self.upload_var, progress_color="#28a745")
        self.check_upload.grid(row=12, column=1, padx=15, pady=(5,5), sticky="w")

        # --- SPEED SLIDER ---
        self.speed_label = ctk.CTkLabel(self.frame_controls, text="Speed: 1.15x")
        self.speed_label.grid(row=13, column=0, padx=15, pady=(10,0), sticky="w")

        self.slider_speed = ctk.CTkSlider(self.frame_controls, from_=0.5, to=2.0, command=self.update_speed_label)
        self.slider_speed.set(1.15)
        self.slider_speed.grid(row=14, column=0, columnspan=2, padx=15, pady=(0,15), sticky="ew")

        self.frame_controls.grid_columnconfigure(0, weight=1)
        self.frame_controls.grid_columnconfigure(1, weight=1)

        # --- ACTION BAR ---
        self.frame_action = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_action.pack(pady=(10, 5), padx=20, fill="x")

        self.btn_start = ctk.CTkButton(self.frame_action, text="▶ Start Processing", font=("Helvetica", 16, "bold"), fg_color="#28a745", hover_color="#218838", height=40, command=self.start_processing)
        self.btn_start.pack(side="left", padx=(0, 15))

        self.status_label = ctk.CTkLabel(self.frame_action, text="Ready to start!", font=("Helvetica", 14), text_color="gray", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)

        self.progress_frame = ctk.CTkScrollableFrame(self, height=130)
        self.progress_frame.pack(fill="x", padx=20, pady=(0, 20))

    def draw_custom_blur(self):
        if not self.input_files:
            self.blur_status_label.configure(text="❌ Pehle 'Select Videos' par click karein!", text_color="red")
            return
            
        try:
            self.blur_status_label.configure(text="Opening Canvas...", text_color="yellow")
            self.update()
            
            self.withdraw()
            
            first_video = self.input_files[0]
            clip = VideoFileClip(first_video)
            t = min(3.0, clip.duration / 2) 
            frame_rgb = clip.get_frame(t) 
            clip.close()
            
            orig_h, orig_w = frame_rgb.shape[:2]
            display_h = 600 
            scale = display_h / float(orig_h)
            display_w = int(orig_w * scale)
            
            display_frame = cv2.resize(frame_rgb, (display_w, display_h))
            img_pil = Image.fromarray(display_frame)
            
            self.draw_win = ctk.CTkToplevel(self)
            self.draw_win.title("Sahir's Editor - Draw Blur Areas")
            self.draw_win.geometry(f"{display_w}x{display_h + 80}")
            self.draw_win.attributes("-topmost", True)
            
            def on_cancel():
                self.draw_win.destroy()
                self.deiconify()
                self.blur_status_label.configure(text="Status: Drawing cancelled", text_color="gray")
                
            self.draw_win.protocol("WM_DELETE_WINDOW", on_cancel)
            
            lbl_inst = ctk.CTkLabel(self.draw_win, text="Mouse se text par box draw karein. Multiple boxes allowed hain!", font=("Helvetica", 12, "bold"))
            lbl_inst.pack(pady=5)

            self.canvas = tk.Canvas(self.draw_win, width=display_w, height=display_h, cursor="cross", highlightthickness=0)
            self.canvas.pack()

            self.photo = ImageTk.PhotoImage(image=img_pil)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

            self.rects = [] 
            self.temp_rect = None
            self.start_x = None
            self.start_y = None

            def on_button_press(event):
                self.start_x = event.x
                self.start_y = event.y
                self.temp_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='#ffcc00', width=3)

            def on_move_press(event):
                cur_x, cur_y = event.x, event.y
                self.canvas.coords(self.temp_rect, self.start_x, self.start_y, cur_x, cur_y)

            def on_button_release(event):
                end_x, end_y = event.x, event.y
                x1, x2 = min(self.start_x, end_x), max(self.start_x, end_x)
                y1, y2 = min(self.start_y, end_y), max(self.start_y, end_y)
                w, h = x2 - x1, y2 - y1
                
                if w > 10 and h > 10:
                    self.rects.append((x1, y1, w, h))
                else:
                    self.canvas.delete(self.temp_rect) 

            self.canvas.bind("<ButtonPress-1>", on_button_press)
            self.canvas.bind("<B1-Motion>", on_move_press)
            self.canvas.bind("<ButtonRelease-1>", on_button_release)

            def save_and_close():
                real_boxes = []
                for (x, y, w, h) in self.rects:
                    real_boxes.append((int(x/scale), int(y/scale), int(w/scale), int(h/scale)))
                
                if real_boxes:
                    self.custom_blur_boxes = real_boxes
                    self.blur_status_label.configure(text=f"✅ {len(real_boxes)} Custom Areas Applied!", text_color="#28a745")
                else:
                    self.custom_blur_boxes = []
                    self.blur_status_label.configure(text="Status: No areas selected", text_color="gray")
                    
                self.draw_win.destroy()
                self.deiconify() 

            def clear_boxes():
                for item in self.canvas.find_all():
                    if self.canvas.type(item) == "rectangle":
                        self.canvas.delete(item)
                self.rects.clear()

            btn_frame = ctk.CTkFrame(self.draw_win, fg_color="transparent")
            btn_frame.pack(fill="x", pady=5, padx=10)
            
            btn_save = ctk.CTkButton(btn_frame, text="✅ Save & Close", command=save_and_close, fg_color="#28a745", hover_color="#218838")
            btn_save.pack(side="left", padx=5, expand=True)
            
            btn_clear = ctk.CTkButton(btn_frame, text="🗑️ Clear All Boxes", command=clear_boxes, fg_color="#dc3545", hover_color="#c82333")
            btn_clear.pack(side="right", padx=5, expand=True)
            
        except Exception as e:
            self.deiconify() 
            self.blur_status_label.configure(text=f"❌ Error: {str(e)[:30]}", text_color="red")

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

    def complete_ui_bar(self, filename, success, error_msg="", is_uploaded=False):
        if filename in self.active_bars:
            if success:
                self.active_bars[filename]["bar"].set(1.0)
                if is_uploaded:
                    self.active_bars[filename]["label"].configure(text=f"☁️ Uploaded {filename[:10]}", text_color="#17a2b8")
                else:
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
            self.custom_blur_boxes = []
            self.blur_status_label.configure(text="Status: App will not blur any area", text_color="gray")

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

    def process_single_video(self, input_path, filename, params): 
        temp_wav_path = None
        clean_wav_path = None
        new_audio_clip = None
        bg_clip = None
        
        try:
            self.after(0, self.create_ui_bar, filename)
            output_path = os.path.join(self.output_folder, f"edited_{filename}")
            
            clip = VideoFileClip(input_path)
            
            if params['auto_trim'] and clip.duration > 3.0:
                clip = clip.subclip(1.0, clip.duration - 1.0)
                
            original_fps = clip.fps if clip.fps else 30.0

            if len(self.custom_blur_boxes) > 0:
                def apply_user_drawn_blur(frame):
                    safe_frame = frame[:,:,:3].copy() if frame.shape[2] == 4 else frame.copy()
                    h, w, _ = safe_frame.shape
                    
                    for (bx, by, bw, bh) in self.custom_blur_boxes:
                        y1 = max(0, by)
                        y2 = min(h, by + bh)
                        x1 = max(0, bx)
                        x2 = min(w, bx + bw)
                        
                        roi = safe_frame[y1:y2, x1:x2]
                        if roi.size > 0:
                            safe_frame[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (75, 75), 0)
                            
                    return safe_frame
                    
                clip = clip.fl_image(apply_user_drawn_blur)
            
            raw_target_w, raw_target_h = self.get_resolution_dims(params['res_val'], params['ratio_val'], clip.w, clip.h)
            target_w = self.make_even(raw_target_w)
            target_h = self.make_even(raw_target_h)
            
            inner_w = self.make_even(target_w - (2 * params['border_size']))
            inner_h = self.make_even(target_h - (2 * params['border_size']))
            
            bg_type = params['bg_val']
            target_is_portrait = target_h > target_w
            input_is_portrait = clip.h > clip.w
            
            if target_is_portrait and input_is_portrait:
                bg_type = "Zoom to Fit (Fill Frame)"

            if bg_type in ["Blur Video", "Zoom to Fit (Fill Frame)", "Half Fit (Blur Background)"]:
                def blur_bg_frame(frame):
                    safe_frame = frame[:,:,:3] if frame.shape[2] == 4 else frame
                    small = cv2.resize(safe_frame, (0,0), fx=0.5, fy=0.5)
                    blurred_small = cv2.GaussianBlur(small, (51, 51), 0)
                    return cv2.resize(blurred_small, (safe_frame.shape[1], safe_frame.shape[0]))
                
                bg_scale = max(target_w / clip.w, target_h / clip.h)
                bg_resized = clip.resize(bg_scale)
                bg_cropped = bg_resized.fx(vfx.crop, x_center=bg_resized.w/2, y_center=bg_resized.h/2, width=target_w, height=target_h)
                bg_clip = bg_cropped.fl_image(blur_bg_frame)
            else:
                colors = {"Black": (0,0,0), "White": (255,255,255), "Dark Gray": (50,50,50)}
                bg_clip = ColorClip(size=(target_w, target_h), color=colors.get(bg_type, (0,0,0)), duration=clip.duration)

            bg_clip = bg_clip.set_fps(original_fps)
            
            if bg_type == "Zoom to Fit (Fill Frame)":
                scale = max(inner_w / clip.w, inner_h / clip.h)
                resized_clip = clip.resize(scale)
                main_clip = resized_clip.fx(vfx.crop, x_center=resized_clip.w/2, y_center=resized_clip.h/2, width=inner_w, height=inner_h)
            
            elif bg_type == "Half Fit (Blur Background)":
                if target_is_portrait: 
                    box_w = inner_w
                    box_h = self.make_even(inner_h * 0.60)
                    scale = max(box_w / clip.w, box_h / clip.h)
                    resized_clip = clip.resize(scale)
                    main_clip = resized_clip.fx(vfx.crop, x_center=resized_clip.w/2, y_center=resized_clip.h/2, width=box_w, height=box_h)
                else: 
                    if input_is_portrait: 
                        box_w = self.make_even(inner_w * 0.60)
                        box_h = inner_h
                        scale = max(box_w / clip.w, box_h / clip.h)
                        resized_clip = clip.resize(scale)
                        main_clip = resized_clip.fx(vfx.crop, x_center=resized_clip.w/2, y_center=resized_clip.h/2, width=box_w, height=box_h)
                    else: 
                        scale = max(inner_w / clip.w, inner_h / clip.h)
                        resized_clip = clip.resize(scale)
                        main_clip = resized_clip.fx(vfx.crop, x_center=resized_clip.w/2, y_center=resized_clip.h/2, width=inner_w, height=inner_h)
            else:
                scale = min(inner_w / clip.w, inner_h / clip.h)
                main_clip = clip.resize(scale)

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

            top_layers = [final_clip]

            if params['anti_copy']:
                top_invisible_layer = ColorClip(size=(target_w, target_h), color=(255, 255, 255), duration=final_clip.duration).set_opacity(0.01)
                top_invisible_layer = top_invisible_layer.set_fps(original_fps)
                top_layers.append(top_invisible_layer)
                
            if params['film_grain']:
                noise_frame = np.random.randint(0, 256, (target_h, target_w, 3), dtype=np.uint8)
                grain_clip = ImageClip(noise_frame).set_duration(final_clip.duration).set_opacity(0.015)
                grain_clip = grain_clip.set_fps(original_fps)
                top_layers.append(grain_clip)
                
            if len(top_layers) > 1:
                final_clip = CompositeVideoClip(top_layers)

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
                self.after(0, self.update_ui_bar, fname, progress * 0.95)

            custom_logger = LiveVideoLogger(filename, ui_update_callback)

            selected_codec = "libx264"
            if params['engine'] == "GPU (Nvidia Fast)":
                selected_codec = "h264_nvenc" 

            safe_temp_audio = os.path.join(tempfile.gettempdir(), f"audio_{uuid.uuid4().hex}.m4a")

            final_clip.write_videofile(
                output_path, 
                fps=original_fps,   
                codec=selected_codec, 
                audio_codec="aac", 
                temp_audiofile=safe_temp_audio, 
                remove_temp=True,
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
            if params['film_grain']:
                grain_clip.close()
            if new_audio_clip: new_audio_clip.close()

            # =========================================================
            # OFFICIAL GOOGLE DRIVE OAUTH UPLOAD & ROBUST DELETE
            # =========================================================
            is_uploaded = False
            if params['auto_upload']:
                try:
                    self.after(0, lambda: self.active_bars[filename]["label"].configure(text=f"☁️ Uploading...", text_color="#17a2b8"))
                    
                    SCOPES = ['https://www.googleapis.com/auth/drive.file']
                    creds = None
                    
                    if os.path.exists('token.json'):
                        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
                        
                    if not creds or not creds.valid:
                        if creds and creds.expired and creds.refresh_token:
                            creds.refresh(Request())
                        else:
                            if not os.path.exists('credentials.json'):
                                raise Exception("credentials.json file nahi mili! Pehli dafa login ke liye yeh zaroori hai.")
                            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                            creds = flow.run_local_server(port=0)
                            
                        with open('token.json', 'w') as token:
                            token.write(creds.to_json())

                    service = build('drive', 'v3', credentials=creds)

                    file_metadata = {
                        'name': f"edited_{filename}",
                        'parents': [params['drive_id']]
                    }
                    media = MediaFileUpload(output_path, resumable=True)
                    service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                    
                    # Agar yahan tak aa gaya, matlab Google ne video qabool kar li hai!
                    is_uploaded = True
                    
                    # File delete kar do taake storage full na ho (Windows Fix ke sath)
                    del media # File ka connection toar diya
                    
                    for _ in range(5):
                        try:
                            os.remove(output_path)
                            break # Delete successful
                        except PermissionError:
                            time.sleep(1) # Agar Windows rokay toh 1 sec wait karke wapis jao

                except Exception as e:
                    raise Exception(f"Upload Fail: {str(e)[:30]}")
            # =========================================================

            self.after(0, self.complete_ui_bar, filename, True, "", is_uploaded)
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
            
        if self.upload_var.get() and len(self.drive_id_var.get()) < 10:
            self.status_label.configure(text="⚠️ Auto-Upload ke liye Drive Folder ID zaroori hai!", text_color="red")
            return

        self.btn_start.configure(state="disabled")
        for widget in self.progress_frame.winfo_children():
            widget.destroy()
        self.active_bars.clear()
        threading.Thread(target=self.run_batch, daemon=True).start()

    def run_batch(self):
        total_videos = len(self.input_files) 
        
        color_map = {
            "Red": (255, 0, 0), "Green": (0, 255, 0), "Blue": (0, 0, 255),
            "Yellow": (255, 255, 0), "Cyan": (0, 255, 255), 
            "Magenta": (255, 0, 255), "White": (255, 255, 255)
        }
        
        params = {
            'do_flip': self.flip_var.get(), 'speed_val': self.slider_speed.get(),
            'ratio_val': self.ratio_menu.get(), 'bg_val': self.bg_menu.get(),
            'res_val': self.res_menu.get(), 'filter_val': self.filter_menu.get(),
            'prog_color': color_map.get(self.color_menu.get(), (255, 0, 0)),
            'clean_audio': self.clean_audio_var.get(),
            'anti_copy': self.anti_copy_var.get(), 
            'mask_noise': self.mask_noise_var.get(),
            'reverb': self.reverb_var.get(),
            'engine': self.engine_menu.get(), 
            'auto_trim': self.auto_trim_var.get(),
            'film_grain': self.film_grain_var.get(), 
            'border_size': 5,
            'auto_upload': self.upload_var.get(),
            'drive_id': self.drive_id_var.get().strip()
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
