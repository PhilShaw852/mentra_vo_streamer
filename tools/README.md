# Tools

## Camera calibration (9×6 chessboard)

Computes camera intrinsics (camera matrix and distortion coefficients) using the standard OpenCV **9×6 chessboard** (9 columns × 6 rows of **inner** corners).

### Setup

Use a separate venv or the project’s `.venv`:

```bash
pip install -r tools/requirements.txt
```

Print a 9×6 chessboard (inner corners) and fix it to a flat surface. OpenCV provides a [calibration pattern generator](https://docs.opencv.org/4.x/da/d0d/tutorial_camera_calibration_pattern.html); many printable 9×6 patterns are available online.

### Run

**Default webcam (camera 0):**

```bash
python tools/calibrate_camera.py
```

**Another camera or video URL:**

```bash
python tools/calibrate_camera.py --source 1
python tools/calibrate_camera.py --source "http://localhost:3010/receiver/flv"
```

**Options:**

- `--output`, `-o` – Output JSON file (default: `camera_intrinsics.json`).
- `--min-views` – Minimum number of captured views before calibration (default: 12).

### Usage in the window

1. Point the camera at the chessboard so the full 9×6 pattern is visible and in focus.
2. **SPACE** – Capture the current frame (only when the board is detected; corners are drawn in color).
3. Move the board to a different angle or distance and capture again. Collect at least 12–15 varied views for better results.
4. **C** – Run calibration and write `camera_intrinsics.json` (then exits).
5. **Q** – Quit without calibrating.

### Output format

`camera_intrinsics.json` contains:

- `image_size` – `[width, height]` of the calibration images.
- `camera_matrix` – 3×3 intrinsic matrix (fx, fy, cx, cy).
- `dist_coeffs` – Distortion coefficients (e.g. k1, k2, p1, p2, k3).
- `rms_error`, `mean_reprojection_error` – Quality metrics (lower is better).
- `num_views` – Number of views used.

Use these with `cv2.undistort()` or `cv2.initUndistortRectifyMap()` for your pipeline.

---

## QR pose (domain calibrator)

Stream the camera feed (e.g. Mentra FLV), run the **domain calibrator** QR detection, and show **camera pose** in a side panel in the browser (like the object detection page).

**Requirements**

- Install the **zbar** system library (required by pyzbar for QR decoding). On macOS: `brew install zbar`.
- Install the domain calibrator package and set its config (auth + camera intrinsics):
  ```bash
  .venv/bin/pip install -e auki_robotics_domain_calibrator/python
  ```
  Ensure `auki_robotics_domain_calibrator/python/config.yaml` has `auth` and `camera` (camera_matrix, dist_coeffs). You can use the output of the [camera calibration](#camera-calibration-96-chessboard) tool for intrinsics.

- Install websockets if not already present:
  ```bash
  pip install websockets
  ```

**Run**

From the project root, with the app and stream running:

```bash
python tools/qr_pose_stream.py
# or: bun run qr-pose
```

Then open **http://localhost:3010/qr_pose.html**. The page shows the live stream and a side panel with **position (x, y, z)**, **rotation (yaw, pitch, roll)**, and **domain ID** when a portal QR code is in view.
