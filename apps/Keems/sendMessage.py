from websockets.sync.client import connect
from message import MessageWidget

def sendMessage(text, KeemsWindow, chatWindow):
    try:
        ip = KeemsWindow.ip_bar.getText
        print("IP: ", ip)
        if ip == None or ip == "": 
            raise Exception("Recipient IP is required")
        with connect(f"ws://{ip}:8765") as websocket:
            websocket.send(text)
            message = websocket.recv()  
            print(f"Received: {message}")
            if text == message:
                print("Message recived s    uccessfully")
                chatWindow.add_message(MessageWidget("You", text, is_self=True))
    except Exception as ex:
        exmsg = "Could not send message for reason: \n " + str(ex)
        chatWindow.add_message(MessageWidget("Error ⚠️", exmsg, is_self=True, error=True))


    

# hello()