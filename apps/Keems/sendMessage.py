from websockets.sync.client import connect
import json

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
            message = websocket.recv()  
            print(f"Received: {message}")
            if payload == message:
                return True
    except Exception as ex:
        return ex
