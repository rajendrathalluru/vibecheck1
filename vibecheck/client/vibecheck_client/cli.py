import asyncio
import json
import sys

import httpx
import websockets


async def run(port: int, server_url: str):
    async with websockets.connect(server_url) as ws:
        await ws.send(json.dumps({"type": "connect", "target_port": port}))
        response = json.loads(await ws.recv())

        if response.get("type") != "session_created":
            print(f"Error: {response}")
            return

        session_id = response["session_id"]
        print("Connected to VibeCheck API")
        print(f"Tunnel session: {session_id}")
        print(f"Proxying to localhost:{port}")
        print("Ready for robust scanning.\n")

        async with httpx.AsyncClient() as client:
            async for message in ws:
                data = json.loads(message)

                if data.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))

                elif data.get("type") == "http_request":
                    request_id = data["request_id"]
                    method = data["method"]
                    path = data["path"]
                    url = f"http://localhost:{port}{path}"

                    print(f"  -> {method} {path}")

                    try:
                        resp = await client.request(
                            method=method,
                            url=url,
                            headers=data.get("headers"),
                            content=data.get("body"),
                            timeout=10.0,
                        )
                        body = resp.text[:5000]
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "http_response",
                                    "request_id": request_id,
                                    "status_code": resp.status_code,
                                    "headers": dict(resp.headers),
                                    "body": body,
                                }
                            )
                        )
                        print(f"  <- {resp.status_code}")
                    except Exception as e:
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "http_response",
                                    "request_id": request_id,
                                    "status_code": 502,
                                    "headers": {},
                                    "body": f"Tunnel client error: {str(e)}",
                                }
                            )
                        )
                        print(f"  <- ERROR: {e}")


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "connect":
        print("Usage: vibecheck connect <port> [--server <ws_url>]")
        sys.exit(1)

    port = int(sys.argv[2])
    server = "ws://localhost:8000/v1/tunnel"
    if "--server" in sys.argv:
        idx = sys.argv.index("--server")
        if idx + 1 < len(sys.argv):
            server = sys.argv[idx + 1]

    print(f"Connecting to {server}...")
    asyncio.run(run(port, server))


if __name__ == "__main__":
    main()
