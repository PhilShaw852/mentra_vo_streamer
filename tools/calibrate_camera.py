#!/usr/bin/env python3
"""
Camera calibration using a standard OpenCV 9x6 chessboard (9x6 inner corners).
Capture multiple views of the printed board, then compute and save intrinsics.
"""
import argparse
import json
import sys

import cv2
import numpy as np

# Standard OpenCV 9x6 chessboard: 9 columns and 6 rows of *inner* corners
CHESSBOARD_SIZE = (9, 6)
# Square size in arbitrary units (only affects scale of tvecs; intrinsics are unchanged)
SQUARE_SIZE = 1.0

# 3D object points for the chessboard (Z=0 plane)
def get_object_points():
    objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), dtype=np.float32)
    objp[:, :2] = np.mgrid[0 : CHESSBOARD_SIZE[0], 0 : CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
    objp *= SQUARE_SIZE
    return objp


def find_corners(frame, gray):
    found, corners = cv2.findChessboardCorners(
        gray,
        CHESSBOARD_SIZE,
        cv2.CALIB_CB_ADAPTIVE_THRESH
        + cv2.CALIB_CB_NORMALIZE_IMAGE
        + cv2.CALIB_CB_FAST_CHECK,
    )
    if not found:
        return None, frame
    # Refine to subpixel
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    corners = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)
    vis = frame.copy()
    cv2.drawChessboardCorners(vis, CHESSBOARD_SIZE, corners, found)
    return corners, vis


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate camera using a 9x6 OpenCV chessboard. Press SPACE to capture a frame, C to calibrate, Q to quit."
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Video source: 0 for default webcam, or a URL/path (e.g. http://localhost:3010/receiver/flv)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="camera_intrinsics.json",
        help="Output file for camera matrix and distortion coefficients (default: camera_intrinsics.json)",
    )
    parser.add_argument(
        "--min-views",
        type=int,
        default=12,
        help="Minimum number of captured views before allowing calibration (default: 12)",
    )
    args = parser.parse_args()

    source = args.source
    if source.isdigit():
        source = int(source)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Could not open video source: {args.source}", file=sys.stderr)
        sys.exit(1)

    object_points = get_object_points()
    obj_points_list = []  # list of object points for each view
    img_points_list = []  # list of image points for each view
    image_size = None

    print("Camera calibration – 9x6 chessboard")
    print("  SPACE = capture this frame (if board detected)")
    print("  C     = run calibration and save (after at least --min-views)")
    print("  Q     = quit")
    print()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame.", file=sys.stderr)
            break
        if image_size is None:
            image_size = (frame.shape[1], frame.shape[0])

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, vis = find_corners(frame, gray)

        n = len(obj_points_list)
        cv2.putText(
            vis,
            f"Captured: {n}  (need {args.min_views} to calibrate)",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )
        if corners is not None:
            cv2.putText(vis, "Board detected - SPACE to capture", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow("Calibration – 9x6 chessboard", vis)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == ord("Q"):
            break
        if key == ord(" "):
            if corners is not None:
                obj_points_list.append(object_points.copy())
                img_points_list.append(corners.copy())
                print(f"  Captured view {len(obj_points_list)}")
            else:
                print("  No board in this frame – move the board into view.")
        if key == ord("c") or key == ord("C"):
            if len(obj_points_list) < args.min_views:
                print(f"  Need at least {args.min_views} views (have {len(obj_points_list)}).")
                continue
            print("Calibrating...")
            rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
                obj_points_list,
                img_points_list,
                image_size,
                None,
                None,
            )
            print(f"  RMS reprojection error: {rms:.4f}")

            # Per-view errors
            total_error = 0
            for i in range(len(obj_points_list)):
                projected, _ = cv2.projectPoints(
                    obj_points_list[i], rvecs[i], tvecs[i], camera_matrix, dist_coeffs
                )
                err = cv2.norm(img_points_list[i], projected, cv2.NORM_L2) / len(projected)
                total_error += err
            mean_error = total_error / len(obj_points_list)
            print(f"  Mean reprojection error: {mean_error:.4f}")

            out = {
                "image_size": list(image_size),
                "camera_matrix": camera_matrix.tolist(),
                "dist_coeffs": dist_coeffs.ravel().tolist(),
                "rms_error": float(rms),
                "mean_reprojection_error": float(mean_error),
                "num_views": len(obj_points_list),
            }
            with open(args.output, "w") as f:
                json.dump(out, f, indent=2)
            print(f"  Saved to {args.output}")
            break

    cap.release()
    cv2.destroyAllWindows()

    if not obj_points_list:
        print("No frames captured. Exiting.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
