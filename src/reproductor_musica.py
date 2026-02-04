import os
import threading
import time
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk
import random
from mutagen.id3 import ID3, APIC
from pathlib import Path
from typing import Optional, List
import tempfile
import pygame


try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None


class AudioFormats:
    EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac", ".mod", ".xm", ".it", ".s3m"}
    FILETYPES = [("Audio", "*.mp3 *.ogg *.wav *.flac *.mod *.xm *.it *.s3m"), ("All", "*.*")]


class PlaybackState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.is_playing = False
        self.is_paused = False
        self.track_length = 0.0
        self.start_time = 0.0
        self.pause_accum = 0.0
        self.last_pause = 0.0


class PlaylistManager:
    def __init__(self):
        self.playlist: List[str] = []
        self.original_order: List[str] = []
        self.current_index = -1
        self.repeat_mode = 0 
        self.shuffle_mode = False
    
    def add_files(self, files: List[str]):
        for file in files:
            if Path(file).suffix.lower() in AudioFormats.EXTENSIONS:
                self.playlist.append(file)
        self._update_original_order()
    
    def add_folder(self, folder: str) -> int:
        added = 0
        folder_path = Path(folder)
        
        for file_path in folder_path.rglob("*"):
            if file_path.suffix.lower() in AudioFormats.EXTENSIONS:
                self.playlist.append(str(file_path))
                added += 1
        
        self._update_original_order()
        return added
    
    def remove_items(self, indices: List[int]):
        for idx in sorted(indices, reverse=True):
            if 0 <= idx < len(self.playlist):
                del self.playlist[idx]
                if idx == self.current_index:
                    self.current_index = -1
                elif idx < self.current_index:
                    self.current_index -= 1
        
        self._update_original_order()
        
        if self.playlist and self.current_index >= len(self.playlist):
            self.current_index = len(self.playlist) - 1
    
    def clear(self):
        self.playlist.clear()
        self.original_order.clear()
        self.current_index = -1
    
    def toggle_shuffle(self):
        self.shuffle_mode = not self.shuffle_mode
        
        if self.shuffle_mode:
            self._apply_shuffle()
        else:
            self._restore_original_order()
    
    def _apply_shuffle(self):
        if not self.playlist:
            return
            
        current_track = self.playlist[self.current_index] if self.current_index >= 0 else None
        temp_playlist = self.playlist.copy()
        
        if current_track:
            temp_playlist.pop(self.current_index)
        
        random.shuffle(temp_playlist)
        
        if current_track:
            temp_playlist.insert(0, current_track)
            self.current_index = 0
        
        self.playlist = temp_playlist
    
    def _restore_original_order(self):
        if not self.original_order:
            return
            
        current_track = self.playlist[self.current_index] if self.current_index >= 0 else None
        self.playlist = self.original_order.copy()
        
        if current_track and current_track in self.playlist:
            self.current_index = self.playlist.index(current_track)
    
    def _update_original_order(self):
        self.original_order = self.playlist.copy()
    
    def get_next_index(self) -> int:
        if not self.playlist:
            return -1
        
        if self.repeat_mode == 1:
            return self.current_index
        
        return (self.current_index + 1) % len(self.playlist)
    
    def get_prev_index(self) -> int:
        if not self.playlist:
            return -1
        
        if self.repeat_mode == 1:
            return self.current_index
        
        return (self.current_index - 1) % len(self.playlist)


class VinylVisualizer:
    def __init__(self, canvas: tk.Canvas, size: int = 360):
        self.canvas = canvas
        self.size = size
        self.angle = 0.0
        self.deg_per_sec = 200.0
        self.vinyl_base = self._create_vinyl_image()
        self.vinyl_imgtk = ImageTk.PhotoImage(self.vinyl_base)
        self.vinyl_item = canvas.create_image(size // 2, size // 2, image=self.vinyl_imgtk)
        self.temp_cover_path = None
    
    def _create_vinyl_image(self, cover_path: Optional[str] = None) -> Image.Image:
        img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        radius = self.size // 2 - 2
        center = (self.size // 2, self.size // 2)
        draw.ellipse([center[0] - radius, center[1] - radius, 
                     center[0] + radius, center[1] + radius],
                    fill=(12, 12, 12), outline=(40, 40, 40), width=2)
        
        for i in range(12, radius, 8):
            bbox = [center[0] - i, center[1] - i, center[0] + i, center[1] + i]
            draw.ellipse(bbox, outline=(26, 26, 26))
        
        label_radius = self.size // 6
        
        if cover_path and os.path.exists(cover_path):
            try:
                cover_img = Image.open(cover_path).convert("RGBA")
                cover_img = cover_img.resize((label_radius * 2, label_radius * 2), Image.LANCZOS)
                
                mask = Image.new("L", (label_radius * 2, label_radius * 2), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, label_radius * 2, label_radius * 2), fill=255)
                
                cover_img.putalpha(mask)
                img.paste(cover_img, (center[0] - label_radius, center[1] - label_radius), cover_img)
            except Exception as e:
                print(f"Error loading cover: {e}")
                self._draw_default_label(draw, center, label_radius)
        else:
            self._draw_default_label(draw, center, label_radius)
        
        hole_radius = max(3, self.size // 90)
        draw.ellipse([center[0] - hole_radius, center[1] - hole_radius,
                     center[0] + hole_radius, center[1] + hole_radius],
                    fill=(230, 230, 230))
        
        return img
    
    def _draw_default_label(self, draw, center, radius):
        draw.ellipse([center[0] - radius, center[1] - radius,
                     center[0] + radius, center[1] + radius],
                    fill=(210, 80, 90), outline=(240, 120, 130), width=2)
    
    def update_cover(self, audio_path: str):
        if self.temp_cover_path and os.path.exists(self.temp_cover_path):
            try:
                os.unlink(self.temp_cover_path)
            except OSError:
                pass
        
        cover_path = self._extract_cover_from_mp3(audio_path)
        self.vinyl_base = self._create_vinyl_image(cover_path)
        self.temp_cover_path = cover_path
        self.rotate_frame()
    
    def _extract_cover_from_mp3(self, path: str) -> Optional[str]:
        if not path.lower().endswith(".mp3"):
            return None
        
        try:
            tags = ID3(path)
            for tag in tags.values():
                if isinstance(tag, APIC):
                    temp_fd, temp_path = tempfile.mkstemp(suffix=".png")
                    with os.fdopen(temp_fd, "wb") as f:
                        f.write(tag.data)
                    return temp_path
        except Exception as e:
            print(f"Could not extract cover: {e}")
        return None
    
    def rotate_frame(self):
        rotated = self.vinyl_base.rotate(self.angle, resample=Image.BICUBIC)
        self.vinyl_imgtk = ImageTk.PhotoImage(rotated)
        self.canvas.itemconfig(self.vinyl_item, image=self.vinyl_imgtk)
    
    def update_rotation(self, dt: float, is_playing: bool, is_paused: bool):
        if is_playing and not is_paused:
            self.angle = (self.angle + self.deg_per_sec * dt) % 360.0
            self.rotate_frame()
        elif self.angle != 0 and not is_playing:
            self.angle = 0
            self.rotate_frame()
    
    def cleanup(self):
        if self.temp_cover_path and os.path.exists(self.temp_cover_path):
            try:
                os.unlink(self.temp_cover_path)
            except OSError:
                pass


class VinylPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Vinyl Player 🎵 0.3")
        self.root.geometry("880x680")
        self.root.configure(bg="#121212")
        
        self.playlist_manager = PlaylistManager()
        self.playback_state = PlaybackState()
        
        self.user_dragging = False
        self.filtered_indices = []
        
        pygame.mixer.init()
        
        self._build_ui()
        
        self.vinyl_visualizer = VinylVisualizer(self.canvas)
        
        self._setup_keyboard_shortcuts()
        
        self._update_ui()
    
    def _build_ui(self):
        self._setup_styles()
        
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=14, pady=14)
        
        self._build_left_panel(main)
        
        self._build_right_panel(main)
        
        self.lbl_now = ttk.Label(self.root, text="—")
        self.lbl_now.pack(anchor="w", padx=16)
    
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("TFrame", background="#121212")
        style.configure("TLabel", background="#121212", foreground="#EAEAEA")
        style.configure("TButton", background="#1F1F1F", foreground="#EAEAEA", 
                       padding=6, relief="flat")
        style.map("TButton", background=[("active", "#2A2A2A")])
        style.configure("Horizontal.TScale", background="#121212")
        style.configure("Playlist.TFrame", background="#181818")
    
    def _build_left_panel(self, parent):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="both", expand=True)
        
        self.canvas = tk.Canvas(left, width=360, height=360, bg="#121212", highlightthickness=0)
        self.canvas.pack(pady=10)
        
        self._build_progress_controls(left)
        
        self._build_playback_controls(left)
        
        self._build_volume_control(left)
    
    def _build_progress_controls(self, parent):
        time_frame = ttk.Frame(parent)
        time_frame.pack(fill="x", pady=(10, 4))
        
        self.lbl_time = ttk.Label(time_frame, text="00:00 / --:--")
        self.lbl_time.pack(side="left")
        
        self.progress = ttk.Scale(parent, from_=0, to=1000, orient="horizontal", 
                                 command=self._on_seek_drag)
        self.progress.pack(fill="x", padx=2)
        self.progress.bind("<Button-1>", self._seek_start)
        self.progress.bind("<ButtonRelease-1>", self._seek_end)
    
    def _build_playback_controls(self, parent):
        controls = ttk.Frame(parent)
        controls.pack(pady=10)
        
        self.btn_prev = ttk.Button(controls, text="⏮️ Previous", command=self.prev_track)
        self.btn_play = ttk.Button(controls, text="▶️ Play", command=self.play_pause)
        self.btn_stop = ttk.Button(controls, text="⏹️ Stop", command=self.stop)
        self.btn_next = ttk.Button(controls, text="⏭️ Next", command=self.next_track)
        
        self.btn_prev.grid(row=0, column=0, padx=4)
        self.btn_play.grid(row=0, column=1, padx=4)
        self.btn_stop.grid(row=0, column=2, padx=4)
        self.btn_next.grid(row=0, column=3, padx=4)
        
        mode_frame = ttk.Frame(parent)
        mode_frame.pack(pady=6)
        
        self.btn_repeat = ttk.Button(mode_frame, text="🔁 Off", command=self.toggle_repeat)
        self.btn_shuffle = ttk.Button(mode_frame, text="🔀 Shuffle", command=self.toggle_shuffle)
        
        self.btn_repeat.grid(row=0, column=0, padx=4)
        self.btn_shuffle.grid(row=0, column=1, padx=4)
    
    def _build_volume_control(self, parent):
        vol_frame = ttk.Frame(parent)
        vol_frame.pack(pady=(6, 0), fill="x")
        
        ttk.Label(vol_frame, text="Volume").pack(side="left")
        self.vol_scale = ttk.Scale(vol_frame, from_=0, to=1, value=0.8, 
                                  orient="horizontal", command=self._on_volume)
        self.vol_scale.pack(side="left", fill="x", expand=True, padx=8)
        pygame.mixer.music.set_volume(0.8)
    
    def _build_right_panel(self, parent):
        right = ttk.Frame(parent, style="Playlist.TFrame")
        right.pack(side="right", fill="both", expand=True, padx=(12, 0))
        
        self._build_search_controls(right)
        
        ttk.Label(right, text="Playlist").pack(anchor="w", padx=8, pady=(6, 2))
        self.listbox = tk.Listbox(right, bg="#101010", fg="#EAEAEA", 
                                 selectbackground="#333333", activestyle="none", 
                                 highlightthickness=0)
        self.listbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.listbox.bind("<Double-Button-1>", lambda e: self._double_click_play())
        
        self._build_playlist_buttons(right)
    
    def _build_search_controls(self, parent):
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill="x", padx=8, pady=(6, 4))
        
        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.search_entry.bind("<KeyRelease>", self._on_search)
    
    def _build_playlist_buttons(self, parent):
        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        
        ttk.Button(btns, text="➕ Add Files", command=self.add_files).pack(side="left", padx=2)
        ttk.Button(btns, text="📂 Add Folder", command=self.add_folder).pack(side="left", padx=2)
        ttk.Button(btns, text="🗑️ Remove", command=self.remove_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="🧹 Clear", command=self.clear_playlist).pack(side="left", padx=2)
    
    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Choose audio files",
            filetypes=AudioFormats.FILETYPES
        )
        if not files:
            return
        
        self.playlist_manager.add_files(files)
        self._refresh_playlist_display()
        
        if self.playlist_manager.current_index == -1 and self.playlist_manager.playlist:
            self.playlist_manager.current_index = 0
            self._update_selection()
    
    def add_folder(self):
        folder = filedialog.askdirectory(title="Choose folder")
        if not folder:
            return
        
        added = self.playlist_manager.add_folder(folder)
        self._refresh_playlist_display()
        
        if added == 0:
            messagebox.showinfo("Empty Folder", "No compatible audio files found.")
        elif self.playlist_manager.current_index == -1 and self.playlist_manager.playlist:
            self.playlist_manager.current_index = 0
            self._update_selection()
    
    def remove_selected(self):
        selection = list(self.listbox.curselection())
        if not selection:
            return
        
        if self.filtered_indices:
            actual_indices = [self.filtered_indices[i] for i in selection]
        else:
            actual_indices = selection
        
        self.playlist_manager.remove_items(actual_indices)
        self._refresh_playlist_display()
        
        if not self.playlist_manager.playlist:
            self.stop()
            self.lbl_now.config(text="—")
        else:
            self._update_selection()
    
    def clear_playlist(self):
        self.playlist_manager.clear()
        self.listbox.delete(0, "end")
        self.filtered_indices.clear()
        self.stop()
        self.lbl_now.config(text="—")
    
    def _refresh_playlist_display(self):
        self.listbox.delete(0, "end")
        self.filtered_indices.clear()
        
        search_text = self.search_var.get().lower()
        
        for i, track in enumerate(self.playlist_manager.playlist):
            track_name = os.path.basename(track)
            if not search_text or search_text in track_name.lower():
                self.listbox.insert("end", track_name)
                self.filtered_indices.append(i)
        
        self._update_selection()
    
    def _update_selection(self):
        if self.playlist_manager.current_index >= 0:
            display_index = -1
            if self.filtered_indices:
                try:
                    display_index = self.filtered_indices.index(self.playlist_manager.current_index)
                except ValueError:
                    pass
            else:
                display_index = self.playlist_manager.current_index
            
            if display_index >= 0:
                self.listbox.selection_clear(0, "end")
                self.listbox.selection_set(display_index)
                self.listbox.see(display_index)
    
    def _on_search(self, event):
        self._refresh_playlist_display()
    
    def _double_click_play(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        
        if self.filtered_indices:
            actual_index = self.filtered_indices[selection[0]]
        else:
            actual_index = selection[0]
        
        self.playlist_manager.current_index = actual_index
        self.load_and_play(actual_index)
    
    def play_pause(self):
        if not self.playlist_manager.playlist:
            messagebox.showinfo("No Songs", "Add files or folder first.")
            return
        
        if self.playback_state.is_playing and not self.playback_state.is_paused:
            pygame.mixer.music.pause()
            self.playback_state.is_paused = True
            self.playback_state.last_pause = time.time()
            self.btn_play.config(text="▶️ Resume")
            return
        
        if self.playback_state.is_playing and self.playback_state.is_paused:
            pygame.mixer.music.unpause()
            self.playback_state.is_paused = False
            self.playback_state.pause_accum += time.time() - self.playback_state.last_pause
            self.btn_play.config(text="⏸️ Pause")
            return
        
        selection = self.listbox.curselection()
        if selection:
            if self.filtered_indices:
                self.playlist_manager.current_index = self.filtered_indices[selection[0]]
            else:
                self.playlist_manager.current_index = selection[0]
        elif self.playlist_manager.current_index == -1:
            self.playlist_manager.current_index = 0
        
        self.load_and_play(self.playlist_manager.current_index)
    
    def stop(self):
        pygame.mixer.music.stop()
        self.playback_state.reset()
        self.btn_play.config(text="▶️ Play")
        self.progress.set(0)
        self.lbl_time.config(text="00:00 / --:--")
    
    def next_track(self):
        if not self.playlist_manager.playlist:
            return
        
        next_index = self.playlist_manager.get_next_index()
        self.playlist_manager.current_index = next_index
        self._update_selection()
        self.load_and_play(next_index)
    
    def prev_track(self):
        if not self.playlist_manager.playlist:
            return
        
        prev_index = self.playlist_manager.get_prev_index()
        self.playlist_manager.current_index = prev_index
        self._update_selection()
        self.load_and_play(prev_index)
    
    def load_and_play(self, index: int):
        if index < 0 or index >= len(self.playlist_manager.playlist):
            return
        
        path = self.playlist_manager.playlist[index]
        
        self.vinyl_visualizer.update_cover(path)
        
        try:
            pygame.mixer.music.load(path)
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load:\n{path}\n\n{e}")
            return
        
        self.playback_state.track_length = self._probe_length(path)
        max_progress = max(1, int(self.playback_state.track_length * 1000)) if self.playback_state.track_length else 1000
        self.progress.configure(from_=0, to=max_progress)
        
        pygame.mixer.music.play()
        self.playback_state.is_playing = True
        self.playback_state.is_paused = False
        self.playback_state.start_time = time.time()
        self.playback_state.pause_accum = 0.0
        self.playback_state.last_pause = 0.0
        
        self.btn_play.config(text="⏸️ Pause")
        self.lbl_now.config(text=f"Playing: {os.path.basename(path)}")
    
    def _probe_length(self, path: str) -> float:
        if MutagenFile is not None:
            try:
                mf = MutagenFile(path)
                if mf and mf.info and hasattr(mf.info, 'length'):
                    return float(mf.info.length)
            except Exception:
                pass
        
        try:
            sound = pygame.mixer.Sound(path)
            length = sound.get_length()
            del sound
            if length > 0.2:
                return float(length)
        except Exception:
            pass
        
        return 0.0
    
    def toggle_repeat(self):
        self.playlist_manager.repeat_mode = (self.playlist_manager.repeat_mode + 1) % 2
        self._update_repeat_button()
    
    def _update_repeat_button(self):
        if self.playlist_manager.repeat_mode == 0:
            self.btn_repeat.config(text="🔁 Off")
        else:
            self.btn_repeat.config(text="🔂 One")
    
    def toggle_shuffle(self):
        self.playlist_manager.toggle_shuffle()
        self._refresh_playlist_display()
        self._update_shuffle_button()
    
    def _update_shuffle_button(self):
        if self.playlist_manager.shuffle_mode:
            self.btn_shuffle.config(text="🔀 On")
        else:
            self.btn_shuffle.config(text="🔀 Shuffle")
    
    def _on_volume(self, val):
        try:
            pygame.mixer.music.set_volume(float(val))
        except Exception:
            pass
    
    def _seek_start(self, event):
        self.user_dragging = True
    
    def _on_seek_drag(self, val):
        pass
    
    def _seek_end(self, event):
        if not self.playback_state.is_playing or self.playback_state.track_length <= 0:
            self.user_dragging = False
            return
        
        value = float(self.progress.get())
        if self.playback_state.track_length > 0:
            ms = int(value)
            sec = ms / 1000.0
        else:
            self.user_dragging = False
            return
        
        was_paused = self.playback_state.is_paused
        try:
            pygame.mixer.music.play(start=sec)
            if was_paused:
                pygame.mixer.music.pause()
        except Exception:
            pass
        
        self.playback_state.start_time = time.time() - sec
        self.playback_state.pause_accum = 0.0
        self.playback_state.last_pause = time.time() if was_paused else 0.0
        
        self.user_dragging = False
    
    def _setup_keyboard_shortcuts(self):
        bindings = {
            "<space>": lambda e: self.play_pause(),
            "<Right>": lambda e: self.next_track(),
            "<Left>": lambda e: self.prev_track(),
            "<Up>": lambda e: self._adjust_volume(0.1),
            "<Down>": lambda e: self._adjust_volume(-0.1),
            "s": lambda e: self.toggle_shuffle(),
            "r": lambda e: self.toggle_repeat(),
            "<Control-f>": lambda e: self.search_entry.focus(),
        }
        
        for key, handler in bindings.items():
            self.root.bind(key, handler)
    
    def _adjust_volume(self, delta: float):
        current_vol = pygame.mixer.music.get_volume()
        new_vol = max(0.0, min(1.0, current_vol + delta))
        pygame.mixer.music.set_volume(new_vol)
        self.vol_scale.set(new_vol)
    
    def _update_ui(self):
        dt = 1 / 60.0
        
        self.vinyl_visualizer.update_rotation(
            dt, 
            self.playback_state.is_playing, 
            self.playback_state.is_paused
        )
        
        if self.playback_state.is_playing:
            elapsed = self._elapsed_time()
            
            if not pygame.mixer.music.get_busy() and not self.playback_state.is_paused:
                if (self.playback_state.track_length and 
                    elapsed >= self.playback_state.track_length - 0.25):
                    self._handle_track_end()
                else:
                    self._handle_track_end()
            
            self._update_progress_display(elapsed)
        
        self.root.after(int(dt * 1000), self._update_ui)
    
    def _update_progress_display(self, elapsed: float):
        if self.playback_state.track_length > 0:
            ms = int(elapsed * 1000)
            if not self.user_dragging:
                max_ms = int(self.playback_state.track_length * 1000)
                self.progress.set(max(0, min(ms, max_ms)))
            
            time_text = f"{self._fmt_time(elapsed)} / {self._fmt_time(self.playback_state.track_length)}"
            self.lbl_time.config(foreground="#EAEAEA", text=time_text)
        else:
            if not self.user_dragging:
                self.progress.set(int((time.time() * 1000) % 1000))
            self.lbl_time.config(text=f"{self._fmt_time(elapsed)} / --:--")
    
    def _handle_track_end(self):
        if self.playlist_manager.repeat_mode == 1:
            self.load_and_play(self.playlist_manager.current_index)
        else:
            self.next_track()
    
    def _elapsed_time(self) -> float:
        if not self.playback_state.is_playing:
            return 0.0
        
        if self.playback_state.is_paused:
            return max(0.0, (self.playback_state.last_pause - self.playback_state.start_time) - 
                          self.playback_state.pause_accum)
        else:
            return max(0.0, (time.time() - self.playback_state.start_time) - 
                          self.playback_state.pause_accum)
    
    @staticmethod
    def _fmt_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    
    def cleanup(self):
        self.vinyl_visualizer.cleanup()
        pygame.mixer.quit()


def main():
    root = tk.Tk()
    
    try:
        app = VinylPlayer(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        try:
            app.cleanup()
        except:
            pass
        
        try:
            pygame.mixer.quit()
        except:
            pass


if __name__ == "__main__":
    main()