import requests
import json
import speech_recognition as sr
import os
import re
import time
import wave
import pyaudio
import urllib.parse
import hashlib
import pyperclip

# VoiceVox engine settings
VOICEVOX_ENGINE_URL = "http://127.0.0.1:50021"
DEVICE_SETTINGS_FILE = 'device_settings.json'
SPEAKERS_FILE = 'speakers.json'  # The path to the speakers.json
CHARA_SETTINGS_FILE = 'chara_settings.json'  # File to save/load character and style indices
VOICE_ID = 3  # Default speaker

# Path to the audio folder
AUDIO_FOLDER = 'audio'

# Global variable for the current character and style
current_character_index = 24
current_style_index = 0

# Define the notification audio files
NOTIFICATIONS = {
    "processing": os.path.join("notifications", "processing.wav"),
    "synthesizing": os.path.join("notifications", "synthesizing.wav"),
    "could_not_understand": os.path.join("notifications", "could_not_understand.wav"),
    "error": os.path.join("notifications", "error.wav"),
    "copy": os.path.join("notifications", "copy.wav"),
}

english_to_japanese = {}

# Preload notification sounds
notification_sounds = {}

# Global variables for language
language = "ja-JP"

def load_chara_settings():
    """Load current character and style indices from JSON file."""
    global current_character_index, current_style_index, VOICE_ID
    try:
        with open(CHARA_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            current_character_index = data.get("current_character_index", 1)
            current_style_index = data.get("current_style_index", 0)
            VOICE_ID = speakers_data[current_character_index]["styles"][current_style_index]["id"]
    except (FileNotFoundError, KeyError, IndexError):
        current_character_index = 1
        current_style_index = 0
        VOICE_ID = speakers_data[current_character_index]["styles"][current_style_index]["id"]

def save_chara_settings():
    """Save current character and style indices to JSON file."""
    data = {
        "current_character_index": current_character_index,
        "current_style_index": current_style_index
    }
    with open(CHARA_SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_gairaigo_dict(filepath):
    """Load the gairaigo (loanword) dictionary from the given file."""
    gairaigo_dict = {}
    with open(filepath, 'r', encoding='utf-8') as file:
        for line in file:
            if line.strip():  # Ignore empty lines
                english_word, japanese_word = line.strip().split(maxsplit=1)
                gairaigo_dict[english_word.lower()] = japanese_word  # Store the lowercase version
                gairaigo_dict[english_word] = japanese_word  # Store the original version
    return gairaigo_dict

def preload_notification_sounds():
    """Preload notification sounds for fast playback."""
    for key, file_path in NOTIFICATIONS.items():
        if os.path.exists(file_path):
            with wave.open(file_path, 'rb') as wf:
                notification_sounds[key] = {
                    "file": file_path,
                    "params": wf.getparams(),
                    "frames": wf.readframes(wf.getnframes())
                }
        else:
            print(f"警告 通知音 {file_path} が見つかりません。")
            
def play_notification(notification_type, output_device_index):
    """Play the preloaded notification sound on a specified output device."""
    if notification_type in notification_sounds:
        sound_data = notification_sounds[notification_type]
        try:
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(sound_data["params"].sampwidth),
                            channels=sound_data["params"].nchannels,
                            rate=sound_data["params"].framerate,
                            output=True,
                            output_device_index=output_device_index)
            stream.write(sound_data["frames"])
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            print(f"通知{notification_type}を再生するエラー： {e}")
    else:
        print(f"通知タイプ '{notification_type}' が見つかりません。")
            
# Ensure the "audio" folder exists
if not os.path.exists(AUDIO_FOLDER):
    os.makedirs(AUDIO_FOLDER)

def load_settings():
    """Load the device settings from a JSON file."""
    try:
        with open(DEVICE_SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "mic_keyword": "steam streaming microphone",
            "voice_speaker_keyword": "usb pnp sound device",
            "notification_speaker_keyword": "vb-audio virtual cable"
        }

def list_devices():
    """List all available audio devices (input and output)."""
    p = pyaudio.PyAudio()
    device_list = []
    for i in range(p.get_device_count()):
        device = p.get_device_info_by_index(i)
        device_list.append((i, device['name'], device['maxInputChannels'], device['maxOutputChannels']))
    p.terminate()
    return device_list
    
def select_device_by_keyword(device_list, keyword, is_output=False):
    """Select the first device that matches the given keyword (case-insensitive, partial match)."""
    keyword = keyword.lower().strip()  # Lowercase and strip the keyword for better matching
    
    for index, name, input_channels, output_channels in device_list:
        name_lower = name.lower().strip()  # Also lowercase and strip device names
        if keyword in name_lower:  # Partial matching
            if is_output and output_channels > 0:
                return index, name
            if not is_output and input_channels > 0:
                return index, name
    return None, None

def play_audio_to_device(file_path, output_device_index):
    """Play a WAV file on a specific output device."""
    if os.path.exists(file_path):
        print(f"デバイス{output_device_index}でオーディオを再生している...")

        with wave.open(file_path, 'rb') as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()

            p = pyaudio.PyAudio()

            try:
                stream = p.open(format=p.get_format_from_width(sample_width),
                                channels=num_channels,
                                rate=frame_rate,
                                output=True,
                                output_device_index=output_device_index)

                chunk_size = 1024
                data = wf.readframes(chunk_size)

                while data:
                    stream.write(data)
                    data = wf.readframes(chunk_size)

                stream.stop_stream()
                stream.close()

            except OSError as e:
                print(f"ストリームを開く際のエラー：{e}。")
            finally:
                p.terminate()
    else:
        print(f"エラー： オーディオファイル {file_path} が見つかりません。")
        
def play_audio_to_two_devices(file_path, output_device_index1, output_device_index2):
    """Play a WAV file simultaneously on two output devices."""
    if os.path.exists(file_path):
        print(f"{output_device_index1}と{output_device_index2}のデバイスで同時にオーディオを再生する...")

        with wave.open(file_path, 'rb') as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()

            p = pyaudio.PyAudio()

            try:
                # Open two output streams for two devices
                stream1 = p.open(format=p.get_format_from_width(sample_width),
                                 channels=num_channels,
                                 rate=frame_rate,
                                 output=True,
                                 output_device_index=output_device_index1)

                stream2 = p.open(format=p.get_format_from_width(sample_width),
                                 channels=num_channels,
                                 rate=frame_rate,
                                 output=True,
                                 output_device_index=output_device_index2)

                chunk_size = 1024
                data = wf.readframes(chunk_size)

                # Play audio simultaneously on both streams
                while data:
                    stream1.write(data)
                    stream2.write(data)
                    data = wf.readframes(chunk_size)

                # Stop and close the streams
                stream1.stop_stream()
                stream1.close()
                stream2.stop_stream()
                stream2.close()

            except OSError as e:
                print(f"ストリームを開くのにエラーが発生しました： {e}")
            finally:
                p.terminate()
    else:
        print(f"エラー： オーディオファイル {file_path} が見つかりません。")

# Load speakers.json data
def load_speakers():
    """Load the VoiceVox speakers information from the speakers.json file."""
    with open(SPEAKERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

speakers_data = load_speakers()

# Get the character and style names based on current_character_id and current_style_id
def get_character_style_name(character_index, style_index):
    try:
        # Ensure the character index is within the range of available characters
        if character_index < len(speakers_data):
            character_data = speakers_data[character_index]
            character_name = character_data["name"]

            # Ensure the style index is within the range of available styles for the selected character
            if style_index < len(character_data["styles"]):
                style_data = character_data["styles"][style_index]
                style_name = style_data["name"]
                return character_name, style_name
            else:
                return character_name, None  # Style not found, return None for style
        else:
            return None, None  # Character not found
    except Exception as e:
        print(f"エラー： {e}")
        return None, None

# Function to map Japanese and kanji numbers to integers, extended for character and style switching
def japanese_text_to_number(text):
    kanji_to_number = {
        "ゼロ": 0, 
        "一": 1, 
        "二": 2, 
        "三": 3,
        "四": 4, 
        "五": 5,
        "六": 6, 
        "七": 7, 
        "八": 8, 
        "九": 9,
        "十": 10,
        "十一": 11,
        "十二": 12,
        "十三": 13,
        "十四": 14,
        "十五": 15,
        "十六": 16,
        "十七": 17,
        "十八": 18,
        "十九": 19,        
        "二十": 20,
        "二十一": 21,
        "二十二": 22,
        "二十三": 23,
        "二十四": 24,
        "二十五": 25,
        "二十六": 26,
        "二十七": 27,
        "二十八": 28,
        "二十九": 29
    }
    kanji_pattern = '|'.join(re.escape(kanji) for kanji in kanji_to_number.keys())
    number_pattern = f'({kanji_pattern}|\\d+)'

    matches = re.findall(number_pattern, text)
    for match in matches:
        if match in kanji_to_number:
            return kanji_to_number[match]
        try:
            return int(match)
        except ValueError:
            continue
    return None

# Switch to the specified character and style
def switch_character_style(character_index=None, style_index=None):
    global VOICE_ID, current_character_index, current_style_index
    try:
        if character_index is not None:
            current_character_index = character_index
            current_style_index = 0  # Default to the first style
            # If the character exists, apply its first style's id as VOICE_ID
            current_style_data = speakers_data[character_index]["styles"][0]
            VOICE_ID = current_style_data["id"]
        if style_index is not None:
            current_style_index = style_index
            # Ensure the style index is within range and get the style's id
            if style_index < len(speakers_data[current_character_index]["styles"]):
                current_style_data = speakers_data[current_character_index]["styles"][style_index]
                VOICE_ID = current_style_data["id"]
            else:
                return "スタイル番号が範囲外です"

        # Get the character and style names
        char_name, style_name = get_character_style_name(current_character_index, current_style_index)

        if char_name and style_name:
            save_chara_settings()  # <-- Save settings here
            return f"{char_name}の{style_name}に変更成功"
        else:
            return "キャラクターまたはスタイルの認識に失敗しました"
    except Exception as e:
        print(f"エラー： {e}")
        return "キャラクターまたはスタイルの認識に失敗しました"


def generate_hashed_filename(text, voice_id):
    """Generate a hashed filename based on the text and voice_id."""
    # Combine the text and voice_id into one string and encode it
    combined = f"{text}_{voice_id}".encode('utf-8')
    
    # Use SHA256 to create a hash of the combined string
    hashed = hashlib.sha256(combined).hexdigest()
    
    # Return the first 16 characters of the hash for a short but unique filename
    return hashed[:16]  # Adjust length as needed for uniqueness vs brevity


def replace_english_words_with_japanese(text, english_to_japanese):
    """
    Replace common English words in a Japanese sentence with their Japanese counterparts.
    """
    def replace_word(match):
        word = match.group(0)
        # Replace the matched word using the dictionary
        return english_to_japanese.get(word.lower(), word)

    # Use a regular expression to match English words (letters, numbers, hyphens)
    pattern = re.compile(r'\b([a-zA-Z0-9\-]+)\b')

    # Perform the substitution
    modified_text = pattern.sub(replace_word, text)

    # Remove spaces before and after Japanese replacements only if they are part of replacements
    return re.sub(r'\s+(?=[ぁ-んァ-ン一-龯])|(?<=[ぁ-んァ-ン一-龯])\s+', '', modified_text)

def text_to_speech(text, speaker=VOICE_ID):
    """Convert text to speech using the VoiceVox engine and save as WAV file."""
    if current_character_index == 1:
        cleaned_text = text.replace(" ", "").replace("　", "")
    else:
        cleaned_text = text
        
    cleaned_text = replace_english_words_with_japanese(cleaned_text, english_to_japanese)

    # Generate the hashed filename based on the cleaned text and voice_id
    hashed_filename = generate_hashed_filename(cleaned_text, speaker)
    output_path = os.path.join(AUDIO_FOLDER, f"{hashed_filename}.wav")  # Save to "audio" folder

    if os.path.exists(output_path):
        print(f"オーディオファイル '{output_path}' は既に存在します。")
        return output_path

    try:
        print(f"テキストの音声クエリをVoiceVoxエンジンに送信： {cleaned_text}")
        play_notification("synthesizing", output_device_index2)
        query_payload = {"text": cleaned_text, "speaker": speaker}

        query_response = requests.post(f"{VOICEVOX_ENGINE_URL}/audio_query", params=query_payload)
        if query_response.status_code != 200:
            print(f"オーディオクエリの生成エラー: {query_response.status_code} - {query_response.text}")
            return None
        
        audio_query = query_response.json()
        
        print("VoiceVoxエンジンに音声合成を依頼...")
        synthesis_response = requests.post(
            f"{VOICEVOX_ENGINE_URL}/synthesis",
            params={"speaker": speaker},
            data=json.dumps(audio_query),
            headers={"Content-Type": "application/json"}
        )

        if synthesis_response.status_code != 200:
            print(f"生成中のエラー: {synthesis_response.status_code} - {synthesis_response.text}")
            return None

        with open(output_path, "wb") as audio_file:
            audio_file.write(synthesis_response.content)

        print(f"音声を{output_path}に保存しました")
        return output_path

    except requests.exceptions.RequestException as e:
        print(f"VoiceVoxエンジンとの通信でネットワークエラーが発生しました：{e}。")
        return None


def recognize_speech_from_mic(mic_index, output_device_index1, output_device_index2):
    global VOICE_ID, language
    
    recognizer = sr.Recognizer()

    with sr.Microphone(device_index=mic_index) as source:
        print("周囲の騒音を調整中...")
        # Increase from the default threshold (100-300) to make it less sensitive
        recognizer.adjust_for_ambient_noise(source, duration=1)

        # Adjust settings to make recognizer more sensitive to shorter phrases and less background noise
        #recognizer.energy_threshold = 1000  #default: 300
        
        recognizer.dynamic_energy_threshold = False  #Default: True

        #recognizer.pause_threshold = 0.4  # Stop recording after 0.4 seconds of silence 0.8 seconds
        
        recognizer.phrase_threshold = 0.3  # Ignore sounds shorter than 0.3 seconds 0.3 seconds
        
        recognizer.non_speaking_duration = 0.4  # Minimal silence before/after phrase 0.5 seconds
        
        recognizer.operation_timeout = 5  # Allow up to 5 seconds per recognition operation Default: None

        print("聞き取り中…")
        while True:
            try:
                audio = recognizer.listen(source, timeout=1)
                print("オーディオの処理...")
                play_notification("processing", output_device_index2)
                
                # Recognize the speech using Google Web Speech API
                text = recognizer.recognize_google(audio, language=language)
                print(f"認識されたテキスト: {text}")
                
                if language is "ja-JP":
                    if "切り替えて" in text:
                        if "英語" in text:
                            language = "en-US"
                            audio_path = text_to_speech("英語に変更成功", speaker=VOICE_ID)
                            if audio_path:
                                play_audio_to_device(audio_path, output_device_index2)
                            continue
                    
                        char_match = re.search(r"([0-9一二三四五六七八九十ゼロ]+)番目のキャラ", text)
                        style_match = re.search(r"([0-9一二三四五六七八九十ゼロ]+)番目のスタイル", text)
                        
                        if char_match:
                            print(f"キャラクター: {char_match.group(1)}")
     
                        if style_match:
                            print(f"スタイル: {style_match.group(1)}")

                        new_char_index = japanese_text_to_number(char_match.group(1)) if char_match else current_character_index
                        print(f"新しいキャラクター番号: {new_char_index}")
                        
                        new_style_index = japanese_text_to_number(style_match.group(1)) if style_match else 0
                        print(f"新しいスタイル番号: {new_style_index}")
                        
                        if new_char_index is not None or new_style_index is not None:
                            result_message = switch_character_style(character_index=new_char_index, style_index=new_style_index)
                            print(result_message)

                            confirmation_audio = text_to_speech(result_message, speaker=VOICE_ID)
                            if confirmation_audio:
                                play_audio_to_device(confirmation_audio, output_device_index2)
                            continue

                        error_message = "番号認識に失敗しました"
                        error_audio_path = text_to_speech(error_message, speaker=VOICE_ID)
                        if error_audio_path:
                            play_audio_to_device(error_audio_path, output_device_index2)
                        continue
                        
                    if "疑問" in text:
                        text = text.replace("疑問", "？")
                    if "ピリオド" in text:
                        text = text.replace("ピリオド", "。")                
                    if "伸ばし棒" in text:
                        text = text.replace("伸ばし棒", "ー")                
                    if "伸ばしぼ" in text:
                        text = text.replace("伸ばしぼ", "ー")                

                    if text.endswith("疑"):
                        text = text[:-1] + "？"
                        
                    #copy to clipboard
                    pyperclip.copy(text)
                                           
                    # Regular speech synthesis and playback
                    output_audio_path = text_to_speech(text, speaker=VOICE_ID)

                    if output_audio_path:
                        play_audio_to_two_devices(output_audio_path, output_device_index1, output_device_index2)

                elif language is "en-US":
                    if "switch to Japanese" in text:
                        language = "ja-JP"
                        audio_path = text_to_speech("日本語に変更成功", speaker=VOICE_ID)
                        if audio_path:
                            play_audio_to_device(audio_path, output_device_index2)
                        continue
                    play_notification("copy", output_device_index2)
                    #copy to clipboard
                    pyperclip.copy(text)

            except sr.WaitTimeoutError:
                # This is the specific timeout error we want to ignore, so just print and continue
                #print("フレーズの開始を待っている間にリスニングがタイムアウト。")
                #do nothing
                continue
            except sr.UnknownValueError:
                # Play "could-not-understand" notification
                print("音声は理解できなかった。")
                play_notification("could_not_understand", output_device_index2)
            except sr.RequestError as e:
                # Play "error" notification for Google Web Speech API errors
                print(f"グーグル音声認識エラー: {e}")
                play_notification("error", output_device_index2)
            except Exception as e:
                # Play "error" notification for any other exceptions
                print(f"エラーが発生しました: {e}")
                play_notification("error", output_device_index2)

def list_and_select_devices():
    """List devices and automatically select based on keywords from settings."""
    device_list = list_devices()
    settings = load_settings()

    mic_keyword = settings.get("mic_keyword", "")
    print(f"🎤マイク: {mic_keyword}")
    voice_speaker_keyword = settings.get("voice_speaker_keyword", "")
    print(f"🔊音声スピーカー: {voice_speaker_keyword}")
    notification_speaker_keyword = settings.get("notification_speaker_keyword", "")
    print(f"🔔通知音用スピーカー: {notification_speaker_keyword}")
    

    print("使用可能なオーディオ機器:")
    for index, name, input_channels, output_channels in device_list:
        print(f"{index}: {name} (Inputs: {input_channels}, Outputs: {output_channels})")

    mic_index, mic_name = select_device_by_keyword(device_list, mic_keyword)
    output_device_index1, speaker1_name = select_device_by_keyword(device_list, voice_speaker_keyword, is_output=True)
    output_device_index2, speaker2_name = select_device_by_keyword(device_list, notification_speaker_keyword, is_output=True)
    
    print(f"マイク番号: {mic_index}")
    voice_speaker_keyword = settings.get("voice_speaker_keyword", "")
    print(f"音声スピーカー番号: {output_device_index1}")
    notification_speaker_keyword = settings.get("notification_speaker_keyword", "")
    print(f"通知音用スピーカー番号: {output_device_index2}")

    return mic_index, output_device_index1, output_device_index2

if __name__ == "__main__":
    mic_index, output_device_index1, output_device_index2 = list_and_select_devices()
    preload_notification_sounds()
    english_to_japanese = load_gairaigo_dict("gairaigo.txt")
    load_chara_settings()
    recognize_speech_from_mic(mic_index, output_device_index1, output_device_index2)
