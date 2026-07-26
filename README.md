# STT for macOS

Simple, fast, local speech-to-text dictation macOS app with Faster Whisper.

## Install

Download the ZIP for your Mac from Releases:

- `arm64` for Apple Silicon.
- `x86_64` for Intel.

Move `STT.app` to Applications, right-click it, and choose **Open** the first
time.

To install from source:

```bash
git clone https://github.com/juancruzrossi/stt.git
cd stt
./install.sh
```

Open STT and allow Microphone and Accessibility when macOS
asks.

## Use

Double-tap `Command` to start listening. Double-tap it again to transcribe.

Open **Settings** from the Dock or menu bar to:

- Change the shortcut.
- Choose **Toggle** or **Hold to Talk**.
- Add custom words under **Terms**.

Audio and transcripts stay on the Mac during normal use. The model and locked
Python dependencies are downloaded only during installation.

See [SECURITY.md](SECURITY.md) for the complete data flow and permissions.
