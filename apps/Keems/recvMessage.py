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
        async for message in websocket:
            try:
                data = json.loads(message)
                headers = data.get("headers", {})
                body = data.get("body", "")
                from_ip = headers.get("from_ip", "unknown")
                self.message_received.emit(from_ip, body)
                await websocket.send(message)
            except (json.JSONDecodeError, KeyError):
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
