# Mentra Live – Unmanaged RTMP streaming

Simple app for **unmanaged RTMP streaming** from Mentra Live glasses. It includes an **edge RTMP receiver** on this device: the glasses stream to your machine, and you can watch in the browser. You can also use any other RTMP URL (e.g. OBS, a streaming server).

## Setup

1. **Install dependencies**

   ```bash
   bun install
   ```

   The app uses the official SDK from npm: `@mentra/sdk` (the public package name; some docs may refer to it as MentraOS SDK).

2. **Configure environment**

   Copy `.env.example` to `.env` and set:

   - `MENTRAOS_API_KEY` – from [console.mentra.glass](https://console.mentra.glass)
   - `MENTRAOS_PACKAGE_NAME` – your app’s package name (must match the console)

3. **Run the app**

   ```bash
   bun run dev
   ```

   Server runs at `http://localhost:3010` (or the port in `PORT`). The **edge receiver** listens for RTMP on port `19350` and serves HTTP-FLV on port `8010` (configurable via `RTMP_PORT`, `RTMP_HTTP_PORT`, `RTMP_APP`, `RTMP_STREAM_KEY` in `.env`).

4. **Tunnel (so the phone/cloud can reach your app)**

   For the Mentra app on your phone and the cloud to reach your dev server, expose it with ngrok:

   ```bash
   bun run tunnel
   ```

   Or run app and tunnel together:

   ```bash
   bun run dev:all
   ```

   Set your app’s **Public URL** in [console.mentra.glass](https://console.mentra.glass) to `https://modifiable-presymphysial-alisia.ngrok-free.dev` (or your ngrok URL). Port in the tunnel script must match `PORT` in `.env` (default 3010).

   **If the tunnel doesn’t run:** install ngrok (`brew install ngrok` on macOS), ensure it’s on your PATH, and add your auth token: `ngrok config add-authtoken <token>` (from [dashboard.ngrok.com](https://dashboard.ngrok.com)).

## App fails to start on the phone

1. **Public URL** – In [console.mentra.glass](https://console.mentra.glass), set the app’s Public URL to your ngrok **origin only**, e.g. `https://modifiable-presymphysial-alisia.ngrok-free.dev` (no path, no trailing slash). The cloud will send session webhooks to `https://your-url/webhook`.
2. **Reachability** – In a browser, open `https://your-ngrok-url/ping`. You should see JSON. If you see ngrok’s “Visit Site” page, the cloud may hit that too; use a static ngrok domain and auth token so the tunnel is direct.
3. **Terminal logs** – With `bun run dev` you get SDK logs. When you start the app on the phone, look for:
   - **“Received session request”** – Cloud reached your server.
   - **“Failed to connect”** – Your server could not open the WebSocket to the cloud (check outbound access to `api.mentra.glass` or `devapi.mentra.glass`).
4. **Package name & API key** – `.env` `MENTRAOS_PACKAGE_NAME` and `MENTRAOS_API_KEY` must match the app in the console.

## Usage

1. **Start the app on your Mentra Live glasses** (voice or app launcher).
2. **On your phone or computer**, open the app URL (e.g. `http://localhost:3010`, or this device’s IP like `http://192.168.1.x:3010` so the glasses can reach the receiver).
3. The stream URL is **pre-filled with the local receiver** (`rtmp://...:19350/live/mentra`). Use it as-is to stream to this device, or replace it with any other RTMP ingest URL.
4. Click **Start stream** to begin unmanaged streaming to that URL.
5. Open **Watch stream** (or `/watch.html`) in the browser to view the live feed from the edge receiver.
6. Click **Stop stream** when done.

The glasses must have an active session (app running) for start/stop to work. The SDK handles keep-alive so the stream stays up while the app is running.

## Project layout

- `src/index.ts` – MentraOS app server, session handling, start/stop stream API, and FLV proxy.
- `src/receiver.ts` – Edge RTMP receiver (node-media-server): ingest + HTTP-FLV playback.
- `public/index.html` – Stream URL input (pre-filled with local receiver) and Start/Stop.
- `public/watch.html` – Live viewer (HTTP-FLV via flv.js).
- `.env` – API key, package name, and optional receiver ports (not committed).

## MCP (MentraOS docs)

See [CURSOR_MCP_SETUP.md](./CURSOR_MCP_SETUP.md) for enabling the MentraOS docs MCP in this repo.
