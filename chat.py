import asyncio
import json
import sys
import websockets
import ssl
import traceback
import os
import properties

save = None


async def receive_messages(websocket, my_name, room_name):
    global save
    try:
        async for message in websocket:
            data = json.loads(message)

            if data.get("auth") == "OK":
                print("\r[System]Server authentication successful")
                continue
            msg = data.get("message")
            if msg:
                sender = data.get("id", "unknown")
                if sender == my_name:
                    continue
                if msg.startswith("/sync_save\n"):
                    save = msg.split("\n", 1)[1]
                    continue
                if msg.startswith("/opfiledm "):
                    parts = msg.split("\n", 1)
                    target_user = parts[0].replace("/opfiledm ", "").strip()
                    if my_name == target_user:
                        content = parts[1] if len(parts) > 1 else ""
                        save = content
                        print(f"\r[{sender} (latest file)]:\n{content}")
                        print(f"{my_name}: ", end="", flush=True)

                    continue
                print(f"\r{sender}: {msg}")
                print(f"{my_name}: ", end="", flush=True)

                if msg.strip() == "/show" and sender != my_name and save is not None:
                    payload = {
                        "to": room_name,
                        "id": my_name,
                        "message": f"/opfiledm {sender}\n{save}"
                    }
                    await websocket.send(json.dumps(payload))
    except websockets.exceptions.ConnectionClosed:
        print("\r[System]Connection defused")


async def send_messages(websocket, my_name, room_name):
    global save
    loop = asyncio.get_running_loop()

    while True:
        msg = await loop.run_in_executor(None, input, f"{my_name}: ")
        if msg.lower() in ['exit', 'quit']:
            print(f"\r[System]Disconnected")
            break

        elif msg.startswith("/help"):
            properties.help()

        elif msg.startswith("/cmd"):
            properties.command_list()

        elif msg.startswith("/download"):
            if save is not None:
                cmd_parts = msg.strip().split(maxsplit=1)
                filename = cmd_parts[1] if len(cmd_parts) > 1 else "downloaded.txt"
                if not filename.endswith(".txt"):
                    filename += ".txt"

                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(save)
                    print(f"\r[Helper]Successfully saved as '{filename}'.")
                except Exception as e:
                    print(f"\r[Helper]Failed to save the file: {e}")
            else:
                print(f"\r[Helper]No history found to download.")
            continue

        elif msg.startswith("/file "):
            file = msg[6:].strip()

            if os.path.exists(file):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        file_content = f.read()
                        list = [msg,
                                "-----------------------------",
                                f"{my_name} uploaded {file}.",
                                f"To show {file}, type /show",
                                f"To download {file}, type /download",
                                "-----------------------------"]
                        for i in range(len(list)):
                            payload = {
                                "to": room_name,
                                "id": my_name,
                                "message": list[i]
                            }
                            if i != 0:
                                print(f"\r{my_name}: {list[i]}")
                            await websocket.send(json.dumps(payload))
                            await asyncio.sleep(0.1)

                        sync_payload = {
                            "to": room_name,
                            "id": my_name,
                            "message": f"/sync_save\n{file_content}"
                        }
                        await websocket.send(json.dumps(sync_payload))

                    save = file_content
                except Exception:
                    print(f"\r[Helper]Failed to load {file}.")
                    continue
            else:
                print(f"\r[Helper]{file} doesn't exist.")

        elif msg.startswith("/show"):
            if save is not None:
                print(f"\r{save}")
            else:
                try:
                    payload = {
                        "to": room_name,
                        "id": my_name,
                        "message": msg
                    }
                    await websocket.send(json.dumps(payload))

                except Exception:
                    print(f"\r[Helper]No history found.")
        else:
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
        print(f"\r[System]Connecting to {uri}...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Origin": "https://cloud.achex.ca"
        }

        async with websockets.connect(uri, ssl=ssl_context, additional_headers=headers) as websocket:
            auth_data = {
                "auth": room_name,
                "password": "password110"
            }
            await websocket.send(json.dumps(auth_data))
            await websocket.send(json.dumps({"to": room_name, "id": "[System]", "message": f"{my_name} joined"}))
            print(f"\r[System]Connected. To leave the chat, type exit")
            print(f"\r[System]To show all commands. type /cmd")
            receive_task = asyncio.create_task(receive_messages(websocket, my_name, room_name))
            send_task = asyncio.create_task(send_messages(websocket, my_name, room_name))

            await send_task
            receive_task.cancel()

    except Exception as e:
        print(f"\r[System]Error was occurred: {e}")
        traceback.print_exc()


def start():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\r[System]Error was occurred")


