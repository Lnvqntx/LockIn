# LockIn

## Webcam head pose

From the repository root, use Python 3.12 to install the dependencies and download
the MediaPipe Face Landmarker model.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
curl --fail --location \
  https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task \
  --output daemon/face_landmarker.task
python daemon/vision.py
```

The script prints yaw and pitch in degrees. Positive yaw means you turned to your
right, and positive pitch means you looked up. After two consecutive seconds
without a detected face, the script prints `face missing` once and resumes printing
angles when the face returns. Video frames are processed locally in memory.

Run `python daemon/vision.py --debug` to see the live video with the angles and
face status overlaid. Press **Q** or **Esc** in the preview, or **Ctrl+C** in your
terminal, to stop.

### Camera permission on macOS

When macOS prompts for camera access, click **Allow**. If you previously denied
access, open **System Settings → Privacy & Security → Camera** and enable access
for the app you launched Python from, such as Terminal, iTerm, or your IDE.
Quit and reopen that app, then run the script again. If the app isn't listed,
run the script from the app once to trigger the permission prompt.
