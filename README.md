# 🎬 Sahir's Pro Editor (Ultimate Bulk Video Editor)

A powerful, multi-threaded desktop application built with Python for bulk video processing. Designed specifically for content creators, YouTube Shorts/Reels editors, and automated faceless channels to edit multiple videos simultaneously with a modern, sleek UI.

## ✨ Features

* **Modern User Interface:** Sleek dark-mode dashboard powered by `CustomTkinter`.
* **Batch Processing:** Multi-threaded architecture allows processing multiple videos (1, 2, 3, 5, or 10) at the exact same time.
* **Live Progress Tracking:** Individual real-time progress bars for each video being processed.
* **Aspect Ratio Conversion:** Convert standard videos to 9:16 (Shorts), 1:1 (Square), or 16:9 with automatic background generation.
* **Dynamic Backgrounds:** Fill empty space with a high-quality blurred version of the video or solid colors (Black, White, Dark Gray).
* **4-Sided Progress Bar:** A dynamic progress bar that wraps around the 4 sides of the video border. Includes color selection (Red, Green, Blue, Yellow, etc.).
* **Audio Noise Reduction:** One-click local AI audio cleaning to remove background hiss and fan noise.
* **Unique Video Filters:** Apply effects like Color Boost (1.2x), Black & White, or Slight Zoom (to bypass simple content ID checks and create fresh frames).
* **High-Quality Export:** Preserves video quality with 8000k bitrate upscaling options (720p, 1080p, 2K, 4K).

## 🛠️ Prerequisites & Installation

Make sure you have Python installed on your system. Then, install the required libraries. 

**Note:** The app requires an older, stable version of MoviePy (v1.0.3) to work seamlessly with CustomTkinter and OpenCV.

Run the following command in your terminal or command prompt:

```bash
pip install customtkinter Pillow numpy moviepy opencv-python noisereduce scipy google-api-python-client google-auth-httplib2 google-auth-oauthlib
