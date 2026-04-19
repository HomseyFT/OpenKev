from websockets.sync.client import connect
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
    except Exception as ex:
        return ex
        exmsg = "Could not send message for reason: \n " + str(ex)
        chatWindow.add_message(MessageWidget("Error ⚠️", exmsg, is_self=True, error=True))


    

# hello()