from TTS.api import TTS

tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")

# preload once at app startup
tts.speaker_manager = tts.synthesizer.tts_model.speaker_manager

tts.tts_to_file(text="hello", speaker_wav="KevSpeech.wav", language="en", file_path="1.wav")
tts.tts_to_file(text="hello again", speaker_wav="KevSpeech.wav", language="en", file_path="2.wav")
