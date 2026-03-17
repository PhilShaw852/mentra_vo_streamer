/**
 * Edge RTMP receiver for Mentra Live streams.
 * Receives RTMP on this device and serves HTTP-FLV for playback.
 */
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const NodeMediaServer = require("node-media-server");

const RTMP_PORT = parseInt(process.env.RTMP_PORT ?? "19350", 10);
const RTMP_HTTP_PORT = parseInt(process.env.RTMP_HTTP_PORT ?? "8010", 10);
const STREAM_APP = process.env.RTMP_APP ?? "live";
const STREAM_KEY = process.env.RTMP_STREAM_KEY ?? "mentra";

let nms: InstanceType<typeof NodeMediaServer> | null = null;

export function getRtmpUrl(host?: string): string {
  const h = host ?? "localhost";
  return `rtmp://${h}:${RTMP_PORT}/${STREAM_APP}/${STREAM_KEY}`;
}

/** HTTP-FLV playback URL for the same stream */
export function getPlaybackUrl(host?: string): string {
  const h = host ?? "localhost";
  return `http://${h}:${RTMP_HTTP_PORT}/${STREAM_APP}/${STREAM_KEY}.flv`;
}

export function startReceiver(): void {
  if (nms) return;
  const config = {
    rtmp: {
      port: RTMP_PORT,
      chunk_size: 60000,
      gop_cache: true,
      ping: 30,
      ping_timeout: 60,
    },
    http: {
      port: RTMP_HTTP_PORT,
      allow_origin: "*",
    },
  };
  nms = new NodeMediaServer(config);
  // When a new publisher connects, replace any existing one (avoids "already has a publisher" on restart/reconnect)
  nms.on("prePublish", (session: { id?: string; streamPath?: string; broadcast?: { publisher?: { socket?: { end: () => void } }; flvMetaData?: unknown; flvAudioHeader?: unknown; flvVideoHeader?: unknown; rtmpMetaData?: unknown; rtmpAudioHeader?: unknown; rtmpVideoHeader?: unknown; flvGopCache?: { clear: () => void }; rtmpGopCache?: { clear: () => void } } }) => {
    const b = session?.broadcast;
    if (b && b.publisher != null) {
      const old = b.publisher as { socket?: { end: () => void } };
      (b as { publisher: unknown }).publisher = null;
      b.flvMetaData = null;
      b.flvAudioHeader = null;
      b.flvVideoHeader = null;
      b.rtmpMetaData = null;
      b.rtmpAudioHeader = null;
      b.rtmpVideoHeader = null;
      b.flvGopCache?.clear();
      b.rtmpGopCache?.clear();
      if (old?.socket?.end) old.socket.end();
      console.log("[receiver] Replaced previous publisher for same stream path");
    }
    console.log("[receiver] Stream publishing:", session?.streamPath ?? "", session?.id ?? "");
  });
  nms.on("donePublish", (session: { streamPath?: string } | string) => {
    const path = typeof session === "object" ? session?.streamPath : session;
    console.log("[receiver] Stream ended:", path ?? "");
  });
  nms.run();
  console.log(
    `[receiver] RTMP ingest: rtmp://localhost:${RTMP_PORT}/${STREAM_APP}/${STREAM_KEY}`
  );
  console.log(
    `[receiver] HTTP-FLV playback: http://localhost:${RTMP_HTTP_PORT}/${STREAM_APP}/${STREAM_KEY}.flv`
  );
}

export function getReceiverPorts(): { rtmp: number; http: number } {
  return { rtmp: RTMP_PORT, http: RTMP_HTTP_PORT };
}
