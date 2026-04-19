from websockets.sync.client import connect
<<<<<<< HEAD
from message import MessageWidget
import json

# import os
# print(os.system('ipconfig'))

remoteHost = "24.34.85.72"

def sendMessage(text, ip):
    try:
        print("IP: ", ip)
        if ip == None or ip == "": 
            raise Exception("Recipient IP is required")
        payload = {
            "headers": {"to_ip": ip, "from_ip": "N/A"},
            "body": text
        }

        with connect(f"ws://{remoteHost}:8260") as websocket:
            websocket.send(json.dumps(payload))
            # print(f"Message to IP {ip} sent through remote host {remoteHost}")
            message = websocket.recv()  
            print(f"Received: {message}")
            if payload == message:
                return True
                # print("Message recived successfully")
                # chatWindow.add_message(MessageWidget("You", text, is_self=True))
=======
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
>>>>>>> 26a2ae634dd4825259e8f3f2eaa235ae76ea5824
    except Exception as ex:
        return ex
        exmsg = "Could not send message for reason: \n " + str(ex)
        chatWindow.add_message(MessageWidget("Error ⚠️", exmsg, is_self=True, error=True))
