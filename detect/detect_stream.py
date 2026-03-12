#!/usr/bin/env python3
"""
YOLO object detection on the Mentra stream. Filters to laptop, cell phone.
(Keys are not in the COCO dataset; add a custom model to detect keys.)
"""
import asyncio
import json
import os
import sys
import threading

import cv2
import websockets
from ultralytics import YOLO

ALLOWED_NAMES = {"laptop", "cell phone"}

STREAM_URL = os.environ.get("STREAM_URL", "http://localhost:3010/receiver/flv")
WS_HOST = os.environ.get("DETECT_WS_HOST", "0.0.0.0")
WS_PORT = int(os.environ.get("DETECT_WS_PORT", "8765"))
CONFIDENCE = float(os.environ.get("DETECT_CONFIDENCE", "0.5"))
# Run inference every Nth frame (1 = every frame; increase to reduce CPU)
EVERY_N_FRAMES = int(os.environ.get("DETECT_EVERY_N_FRAMES", "1"))

clients = set()
detection_queue = None


def detection_loop(model, cap, names, allowed_ids, loop, queue):
    frame_count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        frame_count += 1
        if EVERY_N_FRAMES > 1 and frame_count % EVERY_N_FRAMES != 0:
            continue
        results = model(frame, conf=CONFIDENCE, verbose=False)[0]
        boxes = []
        for box in results.boxes:
            cls_id = int(box.cls.item())
            if cls_id not in allowed_ids:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf.item())
            name = names[cls_id]
            boxes.append({
                "class": name,
                "confidence": round(conf, 2),
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
            })
        if boxes:
            h, w = frame.shape[:2]
            def put():
                try:
                    queue.put_nowait({
                        "detections": boxes,
                        "frameWidth": w,
                        "frameHeight": h,
                    })
                except asyncio.QueueFull:
                    pass
            loop.call_soon_threadsafe(put)


async def broadcast_worker(queue):
    while True:
        msg = await queue.get()
        try:
            while True:
                msg = queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        if not clients:
            continue
        # Debug: log every 30th message to avoid spam
        if hasattr(broadcast_worker, "_count"):
            broadcast_worker._count += 1
        else:
            broadcast_worker._count = 0
        if broadcast_worker._count % 30 == 0:
            dets = msg.get("detections", [])
            fw = msg.get("frameWidth", "?")
            fh = msg.get("frameHeight", "?")
            first = dets[0]["bbox"] if dets else None
            print(f"[detect] broadcast: {len(dets)} detections, frame {fw}x{fh}, first bbox={first}", flush=True)
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
    model = YOLO("yolov8n.pt")
    cap = cv2.VideoCapture(STREAM_URL)
    if not cap.isOpened():
        print(f"Could not open stream {STREAM_URL}", file=sys.stderr)
        sys.exit(1)

    names = model.model.names
    allowed_ids = {i for i, name in names.items() if name in ALLOWED_NAMES}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    queue = asyncio.Queue(maxsize=1)

    thread = threading.Thread(
        target=detection_loop,
        args=(model, cap, names, allowed_ids, loop, queue),
        daemon=True,
    )
    thread.start()

    async def run():
        asyncio.create_task(broadcast_worker(queue))
        async with websockets.serve(handler, WS_HOST, WS_PORT):
            print(f"Detection WebSocket on ws://{WS_HOST}:{WS_PORT}", flush=True)
            await asyncio.Future()

    loop.run_until_complete(run())


if __name__ == "__main__":
    main()
