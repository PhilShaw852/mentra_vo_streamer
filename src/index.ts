import { AppServer, AppSession } from "@mentra/sdk";
import express from "express";
import {
  startReceiver,
  getRtmpUrl,
  getPlaybackUrl,
  getReceiverPorts,
} from "./receiver";

// Store the active session so the web UI can trigger stream start/stop
let currentSession: AppSession | null = null;

class StreamAppServer extends AppServer {
  protected async onSession(
    session: AppSession,
    sessionId: string,
    userId: string
  ): Promise<void> {
    currentSession = session;
    console.log(`Session started: ${sessionId} for user ${userId}`);

    // Don't block webhook response: run display in background.
    // The cloud expects a fast reply; slow onSession can cause the app to close.
    setImmediate(async () => {
      try {
        await session.layouts.showTextWall("Stream app ready.");
      } catch (e) {
        console.error("Failed to show layout:", e);
      }
    });

    session.camera.onStreamStatus((status) => {
      console.log("Stream status:", String(status));
    });

    session.events.onDisconnected(() => {
      console.log("Session disconnected:", sessionId);
      if (currentSession === session) currentSession = null;
    });
  }

  protected async onStop(
    sessionId: string,
    _userId: string,
    reason: string
  ): Promise<void> {
    currentSession = null;
    console.log(`Session stopped: ${sessionId}, reason: ${reason}`);
  }
}

const packageName = process.env.MENTRAOS_PACKAGE_NAME ?? "com.mentra.streamapp";
const apiKey = process.env.MENTRAOS_API_KEY ?? "";
const port = parseInt(process.env.PORT ?? "3010", 10);

// Start edge RTMP receiver on this device (ingest + HTTP-FLV playback)
startReceiver();

const server = new StreamAppServer({
  packageName,
  apiKey,
  port,
  publicDir: "./public",
  healthCheck: true,
});

const app = server.getExpressApp();

// Log webhook requests so you can correlate with ngrok (502 = request didn't reach app or timed out)
app.use((req, res, next) => {
  if (req.method === "POST" && req.path === "/webhook") {
    const t = new Date().toISOString();
    console.log(`Webhook received at ${t}`);
  }
  next();
});

// Reachability check: open https://your-ngrok-url/ping to verify tunnel + server
app.get("/ping", (_req, res) => {
  res.json({
    ok: true,
    message: "Server is reachable. Use this URL (without /ping) as Public URL in console.mentra.glass.",
    webhookPath: "/webhook",
  });
});

// Parse JSON body for API routes
app.use(express.json());

// Start unmanaged RTMP stream to the given receiver URL
app.post("/api/start-stream", async (req, res) => {
  const rtmpUrl = typeof req.body?.rtmpUrl === "string" ? req.body.rtmpUrl.trim() : null;
  if (!rtmpUrl) {
    res.status(400).json({ ok: false, error: "Missing or invalid rtmpUrl" });
    return;
  }
  if (!rtmpUrl.startsWith("rtmp://") && !rtmpUrl.startsWith("rtmps://")) {
    res.status(400).json({
      ok: false,
      error: "URL must start with rtmp:// or rtmps://",
    });
    return;
  }
  if (!currentSession) {
    res.status(503).json({
      ok: false,
      error: "No active session. Start the app on your glasses first.",
    });
    return;
  }
  try {
    const result = (await currentSession.camera.startStream({ rtmpUrl })) as unknown as { success?: boolean; streamId?: string; error?: string };
    if (result?.success) {
      res.json({ ok: true, streamId: result.streamId });
    } else {
      res.status(500).json({ ok: false, error: result?.error ?? "Start stream failed" });
    }
  } catch (err) {
    console.error("startStream error:", err);
    res.status(500).json({
      ok: false,
      error: err instanceof Error ? err.message : "Start stream failed",
    });
  }
});

// Stop the current RTMP stream
app.post("/api/stop-stream", async (_req, res) => {
  if (!currentSession) {
    res.status(503).json({
      ok: false,
      error: "No active session.",
    });
    return;
  }
  try {
    await currentSession.camera.stopStream();
    res.json({ ok: true });
  } catch (err) {
    console.error("stopStream error:", err);
    res.status(500).json({
      ok: false,
      error: err instanceof Error ? err.message : "Stop stream failed",
    });
  }
});

// Stream status for the UI
app.get("/api/stream-status", (_req, res) => {
  res.json({
    hasSession: !!currentSession,
  });
});

// Local receiver info (RTMP URL for glasses, playback URL for browser)
app.get("/api/receiver-info", (req, res) => {
  const { rtmp, http } = getReceiverPorts();
  const host =
    (req.headers["x-forwarded-host"] as string) ||
    req.headers.host?.split(":")[0] ||
    "localhost";
  const appHost = req.headers.host ?? `localhost:${port}`;
  const rtmpHost = host === "localhost" ? "localhost" : host;
  res.json({
    rtmpUrl: getRtmpUrl(rtmpHost),
    playbackUrl: `${req.protocol === "https" ? "https" : "http"}://${appHost}/receiver/flv`,
    rtmpPort: rtmp,
    httpPort: http,
  });
});

// Proxy HTTP-FLV playback through app so watch page is same-origin
app.get("/receiver/flv", async (req, res) => {
  const { http: httpPort } = getReceiverPorts();
  const appName = process.env.RTMP_APP ?? "live";
  const streamKey = process.env.RTMP_STREAM_KEY ?? "mentra";
  const upstream = `http://127.0.0.1:${httpPort}/${appName}/${streamKey}.flv`;
  try {
    const upRes = await fetch(upstream);
    if (!upRes.ok) {
      res.status(upRes.status).send("Stream not available");
      return;
    }
    res.setHeader("Content-Type", "video/x-flv");
    res.setHeader("Cache-Control", "no-store");
    if (upRes.body) {
      const reader = upRes.body.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        res.write(Buffer.from(value));
      }
    }
    res.end();
  } catch {
    res.status(503).send("Receiver not available");
  }
});

server.start().then(() => {
  console.log(`Stream app server running at http://localhost:${port}`);
  console.log(`Local receiver RTMP URL: ${getRtmpUrl()}`);
  console.log(`Open the app URL to set the stream URL or watch the stream.`);
  console.log("");
  console.log("If the app fails to start on the phone:");
  console.log("  1. Set Public URL in console.mentra.glass to your ngrok URL (e.g. https://modifiable-presymphysial-alisia.ngrok-free.dev) with no path.");
  console.log("  2. Test reachability: open https://your-ngrok-url/ping in a browser.");
  console.log("  3. Watch this terminal for 'Received session request' (cloud reached us) or 'Failed to connect' (WebSocket to cloud failed).");
});
