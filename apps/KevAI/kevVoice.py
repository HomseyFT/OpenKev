from PySide6.QtWidgets import QPushButton, QWidget
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtCore import QUrl, QSize
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QThread, Signal, QUrl, QTimer

loadedTPS=False
audio_ready = Signal(str)
error = Signal(str)
token_received = Signal(str)

class AudioButton(QPushButton):
    def __init__(self, text, voice_file: str, parent: QWidget = None):
        print("Kev here")
        super().__init__(parent)
        self.setFixedSize(40, 40)  # Small button size
        self.setText("🔊")          # Emoji icon, or use setIcon for an image
        self.text = text

        # Setup the sound
        self.sound = QSoundEffect()
        self.sound.setSource(QUrl.fromLocalFile(voice_file))
        self.sound.setVolume(0.5)

        # Connect click to play sound
        self.clicked.connect(self._speak(text=self.text))

        # TTS
        self.enable_tts: bool = True,
        self.tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        self._tts = None
        self._tts_ready = False

        # Text buffering
        self._buffer = ""
        self._sentence_split = re.compile(r"[.!?]\s")

     # ---------------- TTS ----------------
    def _init_tts(self):
        if self._tts is None and self.enable_tts:
            try:
                self._tts = TTS(self.tts_model)
                self._tts_ready = True
            except Exception as e:
                self.error.emit(f"TTS init failed: {e}")
                self._tts_ready = False
        self._flush_timer = QTimer()
        self._flush_timer.setInterval(350)
        self._flush_timer.timeout.connect(self._flush_buffer)
        self._flush_timer.start()

        # ---------------- AUDIO SYSTEM ----------------
        self._audio_output = QAudioOutput()
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)

        self._audio_queue: list[QUrl] = []
        self._is_playing = False

        # connect playback chain
        self._player.mediaStatusChanged.connect(self._on_media_status)

        # connect TTS → playback
        self.clicked.connect(lambda: self._speak(self.text))

    def _speak(self, text: str):
        if not loadedTPS:
            from TTS.api import TTS
            loadedTPS = True

        if not self.enable_tts:
            return

        self._init_tts()
        if not self._tts_ready:
            return

        try:
            filename = f"tts_{uuid.uuid4().hex}.wav"

            self._tts.tts_to_file(
                text=text,
                file_path=filename,
                speaker_wav="KevSpeech.wav",
                language="en"
            )

            self.audio_ready.emit(filename)

        except Exception as e:
            self.error.emit(f"TTS error: {e}")

    # ---------------- AUDIO PLAYBACK ----------------
    def _play_audio(self, path: str):
        """Auto-play audio when TTS finishes."""
        url = QUrl.fromLocalFile(path)

        if self._is_playing:
            self._audio_queue.append(url)
            return

        self._is_playing = True
        self._player.setSource(url)
        self._player.play()

    def _on_media_status(self, status):
        from PySide6.QtMultimedia import QMediaPlayer

        if status == QMediaPlayer.EndOfMedia:
            if self._audio_queue:
                next_url = self._audio_queue.pop(0)
                self._player.setSource(next_url)
                self._player.play()
            else:
                self._is_playing = False
    
    def _flush_buffer(self):
        if self._buffer.strip():
            chunk = self._buffer.strip()
            self._buffer = ""
            self._speak(chunk)

     # ---------------- STREAM PROCESSING ----------------
    def _process_chunk(self, content: str, full_parts: list[str]):
        self.token_received.emit(content)
        full_parts.append(content)

        self._buffer += content

        # MUCH smaller chunk threshold
        if len(self._buffer) >= 20:
            chunk = self._buffer.strip()
            self._buffer = ""

            self._speak(chunk)

    

    # # Optional: allow setting icon instead of emoji
    # def set_icon(self, icon_path: str, size: QSize = QSize(24, 24)):
    #     from PySide6.QtGui import QIcon
    #     self.setIcon(QIcon(icon_path))
    #     self.setIconSize(size)
    #     self.setText("")  # Remove text if using an icon