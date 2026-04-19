#!/usr/bin/env python
import asyncio
#from PySide6.QtCore import QObject, Signal
#from websockets.asyncio.server import serve
from websockets import serve
from sendMessage import sendMessage
import json


class MessageReceiver():
    #message_received = Signal(str, str)

    def __init__(self):
        super().__init__()

    def run(self) -> None:
        asyncio.run(self.main())

    async def handleRecv(self, websocket, path=None):
        try: 
            print("Client connected:", websocket.remote_address)

            async for message in websocket:
                try:
                    print("RAW:", message)

                    data = json.loads(message)
                    headers = data.get("headers", {})
                    body = data.get("body", "")

                    to_ip = headers.get("to_ip", "Not provided")
                    from_ip = headers.get("from_ip", "Not provided")

                    print(f"Routing {from_ip} → {to_ip}")

                    result = await sendMessage(body, to_ip, headers)
                    print("sendMessage result:", result)

                except Exception as e:
                    import traceback
                    traceback.print_exc()

                    await websocket.send(f"ERROR: {repr(e)}")
        except Exception as ex:
            print("FATAL ERROR OCCURED: ", ex)


    async def main(self) -> None:
        print("Waiting for messages...")
        async with serve(self.handleRecv, "0.0.0.0", 8260):
            await asyncio.Future()  # run forever
        # async with serve(self.handleRecv, "localhost", 8765) as server:
        #     await server.serve_forever()


if __name__ == "__main__":
    receiver = MessageReceiver()
    receiver.run()