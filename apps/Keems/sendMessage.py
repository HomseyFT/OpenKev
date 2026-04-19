from websockets.sync.client import connect
from apps.Keems.message import MessageWidget

def sendMessage(text, ip, chatWindow):
    try:
        if ip is None or ip == "":
            raise Exception("Recipient IP is required")
        with connect(f"ws://{ip}:8765") as websocket:
            websocket.send(text)
            message = websocket.recv()
            if text == message:
                chatWindow.add_message(MessageWidget("You", text, is_self=True))
    except Exception as ex:
        exmsg = "Could not send message for reason: \n " + str(ex)
        chatWindow.add_message(MessageWidget("Error ⚠️", exmsg, is_self=True, error=True))
