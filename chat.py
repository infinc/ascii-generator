import asyncio
import json
import sys
import websockets
import ssl
import traceback


async def recive_messages(websocket, my_name):
    try:
        async for message in websocket:
            data = json.loads(message)

            if data.get("auth") == "OK":
                print("[System]Server authentication successful")
                continue

            msg = data.get("message")
            if msg:
                sender = data.get("id", "unknown")
                print(f"[{sender}]: {msg}")
                print(f"{my_name}: ", end="", flush=True)

    except websockets.exceptions.ConnectionClosed:
        print("[System]Connection defused")


async def send_messages(websocket, my_name, room_name):
    loop = asyncio.get_running_loop()

    while True:
        msg = await loop.run_in_executor(None, input, f"{my_name}: ")

        if msg.lower() in ['exit', 'quit']:
            print("[System]Disconnected")
            break

        payload = {
            "to": room_name,
            "id": my_name,
            "message": msg
        }
        await websocket.send(json.dumps(payload))


async def main():
    print("30000")
    room_name = input("Enter the ID of the room you want to join: ")
    my_name = input("Enter your name: ")

    uri = f"wss://cloud.achex.ca/chat"

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1
    try:
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=0')
    except Exception:
        pass

    try:
        print(f"[System]Connecting to {uri}...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Origin": "https://cloud.achex.ca"
        }

        async with websockets.connect(uri, ssl=ssl_context, additional_headers=headers) as websocket:
            auth_data = {
                "auth": "ChatAPIHome",
                "password": "48862303286"
            }
            await websocket.send(json.dumps(auth_data))
            await websocket.send(json.dumps({"to": "ChatAPIHome", "id": my_name, "message": "person joined"}))

            print("[System]Connected. To leave the chat, type exit")
            receive_task = asyncio.create_task(recive_messages(websocket, my_name))
            send_task = asyncio.create_task(send_messages(websocket, my_name, room_name))

            await send_task
            receive_task.cancel()

    except Exception as e:
        print(f"[System]Error was occurred: {e}")
        traceback.print_exc()


def start():
    if sys.platform == 'win32':
        print("1000")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        print("2000")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[System]Error was occurred")


