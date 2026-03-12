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
  nms.on("prePublish", (id: string, streamPath: string, args: unknown) => {
    console.log("[receiver] Stream publishing:", streamPath, id);
  });
  nms.on("donePublish", (id: string, streamPath: string, args: unknown) => {
    console.log("[receiver] Stream ended:", streamPath);
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
