import pyttsx3

def on_finished_utterance(self, name, completed):
    """Callback fired when an utterance is finished.

    It stops the event loop so that you can start a new one for a subsequent utterance.
    """
    if completed:
        print("Finished utterance:", name)
        try:
            self.endLoop()
        except RuntimeError as e:
            print("Error ending loop:", e)

def list_voices(engine):
    voices = engine.getProperty('voices')
    for index, voice in enumerate(voices):
        print(f"Voice {index}:")
        print(" - ID:", voice.id)
        print(" - Name:", voice.name)
        print(" - Languages:", voice.languages)
        print(" - Age:", voice.age)
        print(" - Gender:", getattr(voice, 'gender', 'Unknown'))
        print()


def speak(text, reader_id, lang="en_US"):
    engine = pyttsx3.init()
    engine.setProperty('rate', 160)
    engine.connect('finished-utterance', on_finished_utterance)
    if lang == "vi_VN":
        set_vie_reader(engine)
    else:
        set_eng_reader(engine, reader_id)
    engine.say(text)
    engine.startLoop(True)


def set_vie_reader(engine):
    engine.setProperty('voice', 'com.apple.voice.compact.vi-VN.Linh')

def set_eng_reader(engine, reader_id):
    voiceIds = [66, 108, 14, 38]
    voices = engine.getProperty('voices')
    try:
        reader = int(reader_id)
    except ValueError:
        reader = 0
    if reader < 0 or reader >= len(voiceIds):
        reader = 0
    engine.setProperty('voice', voices[voiceIds[reader]].id)
