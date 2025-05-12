import json
import pyaudio
import tkinter as tk
from tkinter import ttk, messagebox

SETTINGS_FILE = 'device_settings.json'

# Load the available devices
def list_devices():
    """List all available audio devices (input and output)."""
    p = pyaudio.PyAudio()
    device_list = []
    for i in range(p.get_device_count()):
        device = p.get_device_info_by_index(i)
        device_list.append((i, device['name'], device['maxInputChannels'], device['maxOutputChannels']))
    p.terminate()
    return device_list

# Save settings to a JSON file
def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

# Load settings from a JSON file
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"mic_keyword": "", "voice_speaker_keyword": "", "notification_speaker_keyword": ""}

# GUI for selecting devices
def show_device_selector():
    def apply_and_save():
        """Save the selected keywords to settings and close the window."""
        mic_keyword = mic_combobox.get()
        voice_speaker_keyword = voice_speaker_combobox.get()
        notification_speaker_keyword = notification_speaker_combobox.get()

        settings = {
            "mic_keyword": mic_keyword,
            "voice_speaker_keyword": voice_speaker_keyword,
            "notification_speaker_keyword": notification_speaker_keyword
        }

        save_settings(settings)
        messagebox.showinfo("成功", "デバイスの設定が保存されました。")
        root.quit()

    # Load available devices and settings
    device_list = list_devices()
    settings = load_settings()

    # Create the GUI window
    root = tk.Tk()
    root.title("マイクとスピーカー設定")
    root.geometry("500x300")

    # Device names for combobox options
    device_names = [name for _, name, _, _ in device_list]

    # Mic combobox
    tk.Label(root, text="🎤マイク:").pack(pady=5)
    mic_combobox = ttk.Combobox(root, values=device_names, width=50)
    mic_combobox.pack(pady=5)
    mic_combobox.set(settings.get("mic_keyword", ""))

    # Speaker 1 combobox
    tk.Label(root, text="🔊音声スピーカー:").pack(pady=5)
    voice_speaker_combobox = ttk.Combobox(root, values=device_names, width=50)
    voice_speaker_combobox.pack(pady=5)
    voice_speaker_combobox.set(settings.get("voice_speaker_keyword", ""))

    # Speaker 2 combobox
    tk.Label(root, text="🔔通知音用スピーカー:").pack(pady=5)
    notification_speaker_combobox = ttk.Combobox(root, values=device_names, width=50)
    notification_speaker_combobox.pack(pady=5)
    notification_speaker_combobox.set(settings.get("notification_speaker_keyword", ""))

    # Apply and Save button
    apply_button = tk.Button(root, text="保存", command=apply_and_save)
    apply_button.pack(pady=20)

    root.mainloop()

# Select devices based on keywords
def select_device_by_keyword(device_list, keyword, is_output=False):
    """Select the first device that matches the given keyword."""
    for index, name, input_channels, output_channels in device_list:
        if keyword.lower() in name.lower():
            if is_output and output_channels > 0:
                return index, name
            if not is_output and input_channels > 0:
                return index, name
    return None, None

if __name__ == "__main__":
    # Show the device selector UI
    show_device_selector()

    # Once the UI is closed, load the selected keywords from the settings file
    settings = load_settings()
    mic_keyword = settings.get("mic_keyword", "")
    voice_speaker_keyword = settings.get("voice_speaker_keyword", "")
    notification_speaker_keyword = settings.get("notification_speaker_keyword", "")

    # Get device list again
    device_list = list_devices()

    # Automatically select devices based on keywords
    mic_index, mic_name = select_device_by_keyword(device_list, mic_keyword)
    voice_output_device_index, voice_speaker_name = select_device_by_keyword(device_list, voice_speaker_keyword, is_output=True)
    notification_output_device_index, notification_speaker_name = select_device_by_keyword(device_list, notification_speaker_keyword, is_output=True)

    # Handle case when no matching devices are found
    if mic_index is None:
        print(f"Microphone with keyword '{mic_keyword}' not found.")
    else:
        print(f"Selected Microphone: {mic_index} - {mic_name}")

    if voice_output_device_index is None:
        print(f"Speaker 1 with keyword '{voice_speaker_keyword}' not found.")
    else:
        print(f"Selected Voice Speaker: {voice_output_device_index} - {speaker1_name}")

    if notification_output_device_index is None:
        print(f"Speaker 2 with keyword '{notification_speaker_keyword}' not found.")
    else:
        print(f"Selected Notification Speaker: {notification_output_device_index} - {speaker2_name}")

    # Now you can use mic_index, voice_output_device_index, and notification_output_device_index in your main program logic
