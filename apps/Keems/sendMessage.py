from websockets.sync.client import connect
from message import MessageWidget

def sendMessage(text, window):
    with connect("ws://localhost:8765") as websocket:
        websocket.send(text)
        message = websocket.recv()
        print(f"Received: {message}")
        if text == message:
            print("Message recived successfully")
            window.add_message(MessageWidget("You", text, is_self=True))

    

# hello()