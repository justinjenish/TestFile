import threading
import cv2
import tkinter as tk
from tkinter import ttk
from scenedetect import VideoManager
from scenedetect import SceneManager
from scenedetect import detect, ContentDetector, AdaptiveDetector, ThresholdDetector
from scenedetect.frame_timecode import FrameTimecode
from PIL import Image, ImageTk
import pygame
from moviepy.editor import *
import sys
import time

class VideoPlayer:
    def __init__(self, video_path):
        self.video_path = video_path
        self.movie_name = self.extract_moviename()
        self.fps = 30

        self.scenes = []
        self.shots = []
        self.subshots = []
        self.indexes = []
        self.key_frames = []

        self.structure = []
        self.segment_type = []
        self.last_scene = 0

        self.cap = cv2.VideoCapture(video_path)
        self.current_frame = 0
        self.playing = False
        self.paused = False
        self.video_started = False
        self.stopped = False
        self.new_segment = False
        self.last_time = 0
        pygame.mixer.init()

        # extract and convert the audio
        self.audio_path = 'temp_audio.wav'
        video = VideoFileClip(video_path)
        audio = video.audio
        audio.write_audiofile(self.audio_path, codec='pcm_s16le')
        self.audio = pygame.mixer.Sound(self.audio_path)
        '''
        with contextlib.closing(wave.open(self.audio_path, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            wav_length = frames / float(rate)
        '''
        # initialize the main window
        self.root = tk.Tk()
        self.root.title("Video Player")
        self.root.geometry("1000x600+0+0")

        # get video dimensions
        self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.new_video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) * 1.5)
        self.new_video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * 1.5)

        # make and configure the main layout
        main_frame = ttk.Frame(self.root, width=1000, height=600)
        main_frame.pack(side=tk.TOP, padx=10, pady=10)
        main_frame.grid_propagate(0)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=3)
        main_frame.rowconfigure(0, weight=1)

        # make the scene listbox with scrollbar
        structure_listbox_frame = ttk.Frame(main_frame, width=250)
        structure_listbox_frame.pack_propagate(0)
        structure_listbox_frame.grid(row=0, column=0, sticky='ns', padx=(0, 10))
        structure_listbox_frame.rowconfigure(0, weight=1)

        structure_listbox_label = ttk.Label(structure_listbox_frame, text="Movie: " + self.movie_name)
        structure_listbox_label.pack(side=tk.TOP)

        structure_listbox_scrollbar = ttk.Scrollbar(structure_listbox_frame)
        structure_listbox_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.structure_listbox = tk.Listbox(structure_listbox_frame, yscrollcommand=structure_listbox_scrollbar.set)
        self.structure_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.structure_listbox.bind('<<ListboxSelect>>', self.jump_to_structure)

        structure_listbox_scrollbar.config(command=self.structure_listbox.yview)

        s = ttk.Style()
        s.configure('1.TFrame', background='red')
        s.configure('2.TFrame', background='blue')
        right_frame = ttk.Frame(main_frame, width=750)
        right_frame.grid(row=0, column=1, sticky='ns')
        right_frame.grid_propagate(0)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=2)
        right_frame.rowconfigure(1, weight=1)

        # make the video canvas with a border
        self.canvas = tk.Canvas(right_frame, width=self.new_video_width, height=self.new_video_height, highlightthickness=1, highlightbackground="black")
        self.canvas.grid(row=0, column=0)

        # make the control frame with buttons
        control_frame = ttk.Frame(right_frame)
        control_frame.grid(row=1, column=0, sticky='ew')
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(2, weight=1)

        self.play_button = ttk.Button(control_frame, text="Play", command=self.start_video)
        self.play_button.grid(row=0, column=0)

        self.pause_button = ttk.Button(control_frame, text="Pause", command=self.pause_video)
        self.pause_button.grid(row=0, column=1)

        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_video)
        self.stop_button.grid(row=0, column=2)

        self.detect_scenes()
        self.detect_shots()
        self.generate_indexes()
        #self.structure, self.segment_type = self.generate_indexes_with_subshots()

        #self.fps = self.structure[-1][1].get_frames() / wav_length
        #print(self.structure[-1][1].get_frames(), self.fps)
        '''
        for i in range(0, len(self.structure)):
            if self.segment_type[i] == 0:
                print('Scene %2d: Start %s / Frame %d, End %s / Frame %d' % (
                    i + 1,
                    self.structure[i][0].get_timecode(), self.structure[i][0].get_frames(),
                    self.structure[i][1].get_timecode(), self.structure[i][1].get_frames(),))
            elif self.segment_type[i] == 1:
                print('    Shot %2d: Start %s / Frame %d, End %s / Frame %d' % (
                    i + 1,
                    self.structure[i][0].get_timecode(), self.structure[i][0].get_frames(),
                    self.structure[i][1].get_timecode(), self.structure[i][1].get_frames(),))
            else:
                print('        Subshot %2d: Start %s / Frame %d, End %s / Frame %d' % (
                    i + 1,
                    self.structure[i][0].get_timecode(), self.structure[i][0].get_frames(),
                    self.structure[i][1].get_timecode(), self.structure[i][1].get_frames(),))    
        '''
        self.populate_structure_listbox()

        self.root.mainloop()

    def extract_moviename(self):
        movie_name = self.video_path

        if self.video_path.find('\\') != -1:
            while movie_name[movie_name.find('\\') + 1:].find('\\') != -1:
                movie_name = movie_name[movie_name.find('\\') + 1:]
            movie_name = movie_name[:movie_name.find('\\')]
        elif self.video_path.find('/') != -1:
            while movie_name[movie_name.find('/') + 1:].find('/') != -1:
                movie_name = movie_name[movie_name.find('/') + 1:]
            movie_name = movie_name[:movie_name.find('/')]
        else:
            movie_name = movie_name[:movie_name.find('.')]

        movie_name = movie_name.replace('_', ' ')
        if (movie_name.find('rgb') != -1):
            movie_name = movie_name[:movie_name.find('rgb')]

        i = 0
        while (i < len(movie_name) - 1):
          if (movie_name[i] >= 'a' and movie_name[i] <= 'z' and movie_name[i + 1] >= 'A' and movie_name[i + 1] <= 'Z'):
              movie_name = movie_name[:i + 1] + ' ' + movie_name[i + 1:]
          i += 1

        return movie_name.strip()

    def populate_structure_listbox(self):
        num = 0
        for i, scene in enumerate(self.scenes):
            start_frame, end_frame = scene
            start_time = start_frame.get_timecode()
            end_time = end_frame.get_timecode()
            self.structure_listbox.insert(tk.END, f"Scene {i + 1} ({start_time}-{end_time})")
            self.structure.append([start_frame, end_frame])
            self.segment_type.append(0)
            
            if i == len(self.scenes) - 1:
                self.last_scene = num
            num += 1

            for j, shot in enumerate(self.indexes[i]):
                start_frame, end_frame = shot
                start_time = start_frame.get_timecode()
                end_time = end_frame.get_timecode()
                self.structure_listbox.insert(tk.END, f"    Shot {j + 1} ({start_time}-{end_time})")
                self.structure.append([start_frame, end_frame])
                self.segment_type.append(1)
                num += 1

                subshots = self.detect_subshots(shot)
                for k, subshot in enumerate(subshots):
                    start_frame, end_frame = subshot
                    start_time = start_frame.get_timecode()
                    end_time = end_frame.get_timecode()
                    self.structure_listbox.insert(tk.END, f"        Subshot {k + 1} ({start_time}-{end_time})")
                    self.structure.append([start_frame, end_frame])
                    self.segment_type.append(2)
                    num += 1

    def play_audio(self, start_ms):
        def audio_thread():
            pygame.mixer.music.load(self.audio_path)
            pygame.mixer.music.play()
            '''
            time.sleep(0.001)  # add a small pause before setting the position
            if (start_ms % 1000 >= 500):
                pygame.mixer.music.set_pos(start_ms // 1000 + 1)
            else:
                pygame.mixer.music.set_pos(start_ms // 1000)
            '''
            pygame.mixer.music.set_pos(start_ms / 1000)

        t = threading.Thread(target=audio_thread)
        t.start()

    def start_video(self):
        if not self.playing:
            self.playing = True
            if not self.structure or not self.structure_listbox.curselection():
                self.structure_listbox.select_set(0)
            start_frame, _ = self.structure[self.structure_listbox.curselection()[0]]
            start_ms = int(start_frame.get_seconds() * 1000)
            audio_thread = threading.Thread(target=self.play_audio, args=(start_ms,))
            audio_thread.start()

            if (self.stopped or not self.video_started):
              video_thread = threading.Thread(target=self.show_video)
              video_thread.start()
              self.video_started = True
              self.stopped = False

        elif self.paused:
            self.paused = False
            pygame.mixer.music.unpause()
            self.show_video()

        else:  # If not paused and already playing, do nothing
            # Check if it's the last scene and the video has ended
            selected_structure_index = self.structure_listbox.curselection()[0]
            if (selected_structure_index == len(self.structure) - 1 or selected_structure_index == self.last_scene) and self.current_frame >= self.structure[selected_structure_index][1].get_frames():
                self.stop_video()
                self.start_video()

    def stop_audio(self):
        pygame.mixer.music.stop()

    def stop_video(self):
        self.playing = False
        self.paused = False
        self.stopped = True
        self.stop_audio()

        if self.structure_listbox.curselection():
            start_frame, _ = self.structure[self.structure_listbox.curselection()[0]]
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame.get_frames())
            self.current_frame = start_frame.get_frames()

    def pause_video(self):
        if self.playing:
            self.paused = True
            pygame.mixer.music.pause()

    def jump_to_structure(self, event):
        if self.paused:
            self.paused = False
            pygame.mixer.music.unpause()
            self.show_video()

        if self.playing:
            self.playing = False
            self.paused = False
            self.stop_audio()

        selected_structure = self.structure_listbox.curselection()
        if selected_structure:
            start_frame, _ = self.structure[selected_structure[0]]
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame.get_frames())
            self.current_frame = start_frame.get_frames()
            self.start_video()
        
    def show_video(self):
        if self.playing and not self.paused:
            current_time = time.time() * 1000
            #print(current_time - self.last_time)
            self.last_time = current_time
            #print(current_time)

            ret, frame = self.cap.read()
            if ret:
                self.current_frame += 1
                start_frame, end_frame = self.structure[self.structure_listbox.curselection()[0]]
                
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = Image.fromarray(frame)
                frame = frame.resize([self.new_video_width, self.new_video_height], resample=0)
                frame = ImageTk.PhotoImage(frame)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=frame)
                self.canvas.image = frame

                if self.new_segment:
                    pygame.mixer.music.stop()
                    start_ms = int(start_frame.get_seconds() * 1000)
                    audio_thread = threading.Thread(target=self.play_audio, args=(start_ms,))
                    audio_thread.start()
                    self.new_segment = False
                
                if self.current_frame >= self.structure[self.last_scene][1]:
                    self.stop_video()
                    return

                if self.current_frame >= end_frame.get_frames():
                    current_cur = self.structure_listbox.curselection()[0]
                    current_type = self.segment_type[current_cur]
                    i = current_cur + 1
                    if current_type == 0 or current_type == 1:
                        while i < len(self.structure):
                            if self.segment_type[i] == current_type:
                                break
                            i += 1
                    elif current_cur + 1 < len(self.segment_type) and self.segment_type[current_cur + 1] != 2:
                        while i < len(self.structure):
                            if self.segment_type[i] == 1:
                                break
                            i += 1
                        
                    self.structure_listbox.selection_clear(self.structure_listbox.curselection()[0])
                    self.structure_listbox.selection_set(i)
                    
                    start_frame, _ = self.structure[i]
                    self.current_frame = start_frame.get_frames()
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame.get_frames())

                    self.new_segment = True
                
                time_diff = time.time() * 1000 - current_time
                #print(time_diff)
                if (time_diff < 1000 / self.fps):
                    self.root.after(int(1000 / self.fps - (time.time() * 1000 - current_time)), self.show_video)
                else:
                    self.root.after(0, self.show_video)

    # don't forget to remove the temporary audio file when done, this code will do that
    def __del__(self):
        if os.path.exists(self.audio_path):
            os.remove(self.audio_path)

    def detect_scenes(self):
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=30))
        video_manager = VideoManager([self.video_path])

        video_manager.set_duration()

        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)

        self.scenes = scene_manager.get_scene_list(video_manager.get_base_timecode())

        video_manager.release()

    def detect_shots(self):
        scene_manager = SceneManager()
        scene_manager.add_detector(ThresholdDetector(threshold=40)) # Change this line
        video_manager = VideoManager([self.video_path])

        video_manager.set_duration()

        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)

        self.shots = scene_manager.get_scene_list(video_manager.get_base_timecode())

        video_manager.release()

    def detect_subshots(self, shot):
        video_manager = VideoManager([self.video_path])
        video_manager.set_duration(start_time=shot[0], end_time=shot[1])

        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=10))

        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)

        subshots = scene_manager.get_scene_list(video_manager.get_base_timecode())

        video_manager.release()

        return subshots

    def generate_indexes(self):
        key_frames = []
        frame_num_set = set()

        for (start, end) in self.scenes:
            if start.get_frames() not in frame_num_set:
                key_frames.append(start)
                frame_num_set.add(start.get_frames())
                frame_num_set.add(start.get_frames() + 1)
                frame_num_set.add(start.get_frames() - 1)
            if end.get_frames() not in frame_num_set:
                key_frames.append(end)
                frame_num_set.add(end.get_frames())
                frame_num_set.add(end.get_frames() + 1)
                frame_num_set.add(end.get_frames() - 1)

        for (start, end) in self.shots:
            if start.get_frames() not in frame_num_set:
                key_frames.append(start)
                frame_num_set.add(start.get_frames())
                frame_num_set.add(start.get_frames() + 1)
                frame_num_set.add(start.get_frames() - 1)
            if end.get_frames() not in frame_num_set:
                key_frames.append(end)
                frame_num_set.add(end.get_frames())
                frame_num_set.add(end.get_frames() + 1)
                frame_num_set.add(end.get_frames() - 1)

        key_frames.sort(key=lambda x: x.get_frames())

        k = 0
        shot_list = []
        for i in range(1, len(key_frames)):
            if key_frames[i - 1].get_frames() >= self.scenes[k][0].get_frames() and key_frames[i].get_frames() <= self.scenes[k][1].get_frames():
                shot_list.append([key_frames[i - 1], key_frames[i]])

            if key_frames[i].get_frames() == self.scenes[k][1].get_frames():
                self.indexes.append(shot_list)
                shot_list = []
                k += 1

        for shot in shot_list:
            subshots = self.detect_subshots(shot)
            self.indexes.append(subshots)

if __name__ == "__main__":
    #video_path = 'moviename/InputVideo.mp4'
    #add the file path here within the single quotes, for the mp4 video
    video_path = sys.argv[1]
    video_player = VideoPlayer(video_path)

#justin jenish
