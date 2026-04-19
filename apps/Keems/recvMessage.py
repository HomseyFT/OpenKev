#!/usr/bin/env python
import asyncio
from PySide6.QtCore import QObject, Signal
from websockets.asyncio.server import serve
import json

class MessageReceiver(QObject):
    message_received = Signal(str, str)

    def __init__(self):
        super().__init__()

    def run(self) -> None:
        asyncio.run(self.main())

    async def handleRecv(self, websocket, path=None):
        clientinfo = websocket.remote_address
        data = json.loads(message)
        headers = data.get("headers", {})
        body = data.get("body", "")

        to_ip = headers.get('to_ip', 'Not provided')  # Default to 'Not provided' if missing
        from_ip = headers.get('from_ip', 'Not provided')  # Default to 'Not provided' if missing


        async for message in websocket:
            # ip = str(clientinfo[0]) if clientinfo else "unknown"
            self.message_received.emit(from_ip, message)
            await websocket.send(message)

    async def main(self) -> None:
        print("Waiting for messages...")
        async with serve(self.handleRecv, "0.0.0.0", 8260):
            await asyncio.Future()  # run forever
        # async with serve(self.handleRecv, "localhost", 8765) as server:
        #     await server.serve_forever()


if __name__ == "__main__":
    receiver = MessageReceiver()
    receiver.run()