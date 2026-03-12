#!/usr/bin/env python3
"""
Read camera feed (Mentra stream or device), run domain calibrator QR detection,
and broadcast camera pose over WebSocket for the QR pose viewer page.

Requires the domain_calibrator package (from auki_robotics_domain_calibrator) and
config.yaml with auth and camera intrinsics. Install with:
  pip install -e auki_robotics_domain_calibrator/python
  # and set auki_robotics_domain_calibrator/python/config.yaml (camera_matrix, auth, etc.)

Usage:
  python tools/qr_pose_stream.py [--source URL|INDEX] [--config PATH] [--ws-port PORT]
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import cv2
import websockets

# Optional: domain calibrator (from auki_robotics_domain_calibrator)
_import_error = None
try:
    from scipy.spatial.transform import Rotation as R
    from domain_calibrator import DomainCalibratorPy, load_config
    HAS_CALIBRATOR = True
except ImportError as e:
    HAS_CALIBRATOR = False
    R = None
    _import_error = e

STREAM_URL = os.environ.get("STREAM_URL", "http://localhost:3010/receiver/flv")
WS_HOST = os.environ.get("QR_POSE_WS_HOST", "0.0.0.0")
WS_PORT_DEFAULT = int(os.environ.get("QR_POSE_WS_PORT", "8766"))

clients = set()
pose_queue = asyncio.Queue(maxsize=1)


def get_default_config_path():
    # From tools/qr_pose_stream.py -> auki_robotics_domain_calibrator/python/config.yaml
    tools_dir = Path(__file__).resolve().parent
    repo_root = tools_dir.parent
    return repo_root / "auki_robotics_domain_calibrator" / "python" / "config.yaml"


def detection_loop(calibrator, cap, loop):
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        try:
            result = calibrator.detect_and_calibrate(frame)
        except Exception as e:
            print(f"[qr_pose] calibrate error: {e}", flush=True)
            continue
        if result is None:
            continue
        camera_pos = result[:3, 3]
        camera_rot_matrix = result[:3, :3]
        camera_rot = R.from_matrix(camera_rot_matrix)
        yaw, pitch, roll = camera_rot.as_euler("zyx", degrees=True)
        domain_id = getattr(calibrator, "_authenticated_domain_id", None)
        msg = {
            "position": {"x": float(camera_pos[0]), "y": float(camera_pos[1]), "z": float(camera_pos[2])},
            "rotation": {"yaw": round(yaw, 2), "pitch": round(pitch, 2), "roll": round(roll, 2)},
            "domain_id": domain_id,
        }

        def put_msg():
            try:
                pose_queue.put_nowait(msg)
            except asyncio.QueueFull:
                try:
                    pose_queue.get_nowait()
                    pose_queue.put_nowait(msg)
                except asyncio.QueueEmpty:
                    pass

        loop.call_soon_threadsafe(put_msg)


async def broadcast_worker():
    while True:
        msg = await pose_queue.get()
        try:
            while True:
                msg = pose_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        if not clients:
            continue
        payload = json.dumps(msg)
        dead = set()
        for ws in clients:
            try:
                await ws.send(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            clients.discard(ws)


async def handler(websocket):
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.discard(websocket)


def main():
    parser = argparse.ArgumentParser(
        description="QR pose stream: camera feed -> domain calibrator -> WebSocket pose."
    )
    parser.add_argument(
        "--source",
        default=os.environ.get("QR_POSE_SOURCE", STREAM_URL),
        help="Video source: 0 for webcam, or URL (e.g. http://localhost:3010/receiver/flv)",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("AUKI_CONFIG", str(get_default_config_path())),
        help="Path to domain calibrator config.yaml (auth + camera intrinsics)",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=WS_PORT_DEFAULT,
        help=f"WebSocket port for pose (default: {WS_PORT_DEFAULT})",
    )
    args = parser.parse_args()

    if not HAS_CALIBRATOR:
        err = str(_import_error) if _import_error else ""
        print("domain_calibrator not available.", file=sys.stderr)
        if "zbar" in err.lower():
            print(
                "pyzbar needs the zbar shared library. On macOS: brew install zbar\n"
                "Then: .venv/bin/pip install -e auki_robotics_domain_calibrator/python",
                file=sys.stderr,
            )
        else:
            print(
                "  .venv/bin/pip install -e auki_robotics_domain_calibrator/python\n"
                "Run with: .venv/bin/python tools/qr_pose_stream.py (or bun run qr-pose)",
                file=sys.stderr,
            )
        if _import_error is not None:
            print(f"Import error: {_import_error}", file=sys.stderr)
        sys.exit(1)

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    source = args.source
    if source.isdigit():
        source = int(source)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Could not open source: {args.source}", file=sys.stderr)
        sys.exit(1)

    calibrator = DomainCalibratorPy(config_path=config_path)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    import threading
    thread = threading.Thread(
        target=detection_loop,
        args=(calibrator, cap, loop),
        daemon=True,
    )
    thread.start()

    async def run():
        asyncio.create_task(broadcast_worker())
        async with websockets.serve(handler, WS_HOST, args.ws_port):
            print(f"QR pose WebSocket on ws://{WS_HOST}:{args.ws_port}", flush=True)
            await asyncio.Future()

    loop.run_until_complete(run())


if __name__ == "__main__":
    main()
