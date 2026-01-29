
import socketio
import json
import threading
import time
from typing import Callable, Optional, Dict, Any
from utils import ForkliftLogger, CONFIG, get_mac_address

class WebSocketError(Exception):
    pass

class CloudWebSocket:
    def __init__(self, config: Dict[str, Any], on_response: Callable[[Dict[str, Any]], None], on_connection_change: Optional[Callable[[str], None]] = None):
        self.config = config
        self.sio = socketio.Client(logger=True, engineio_logger=True)
        self.url = config['websocket']['url'] # Keep http/https, socketio handles it
        self.on_response = on_response
        self.on_connection_change = on_connection_change
        self.logger = ForkliftLogger.setup(config['system']['log_level'])
        self.is_connected = False
        
        self._setup_callbacks()
        self._start_connection_thread()
    
    def _setup_callbacks(self):
        @self.sio.event
        def connect():
            self.logger.info(f"Connected to server at {self.url}")
            self.is_connected = True
            if self.on_connection_change:
                self.on_connection_change("connected")
            
            self._register()
            
        @self.sio.event
        def disconnect():
            self.logger.warning("Disconnected from server")
            self.is_connected = False
            if self.on_connection_change:
                self.on_connection_change("disconnected")
        
        @self.sio.event
        def connect_error(data):
            self.logger.error(f"Connection error: {data}")
            self.is_connected = False
            if self.on_connection_change:
                self.on_connection_change("disconnected")

        @self.sio.on('message')
        def on_message(data):
            self.logger.debug(f"Received message: {data}")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    pass
            self.on_response(data)
            
        @self.sio.on('response') # Handle specific event if server uses it
        def on_response_event(data):
            on_message(data)

        # Listen to personal channel (MAC address)
        mac_address = get_mac_address()
        @self.sio.on(mac_address)
        def on_personal_message(data):
            self.logger.info(f"Received personal message on {mac_address}: {data}")
            # Normalize string messages (like "Storage Area") to location updates
            if isinstance(data, str):
                normalized = {
                    "type": "location_update",
                    "location": data
                }
                self.on_response(normalized)
            else:
                self.on_response(data)

    def _register(self):
        mac_address = get_mac_address()
        forklift_id = self.config['system']['forklift_id']
        
        register_payload = {
            "type": "register",
            "forklift_id": forklift_id,
            "mac_id": mac_address,
            "device_type": "forklift_camera"
        }
        # Send as 'message' event which is standard for send()
        self.sio.send(register_payload)
        self.logger.info(f"Registered as {forklift_id}")

    def _start_connection_thread(self):
        def run():
            while True:
                if not self.is_connected:
                    try:
                        if self.on_connection_change:
                            self.on_connection_change("connecting")
                        self.sio.connect(self.url, transports=['websocket'])
                        self.sio.wait()
                    except Exception as e:
                        self.logger.error(f"Connection failed: {e}")
                        if self.on_connection_change:
                            self.on_connection_change("disconnected")
                        self.sio.disconnect()
                        time.sleep(5) # Reconnect delay
                else:
                    time.sleep(1)
                    
        t = threading.Thread(target=run, daemon=True)
        t.start()
    
    def send_pallet_data(self, data: Dict[str, Any]) -> bool:
        if not self.is_connected:
            self.logger.warning("WebSocket not connected")
            return False
        
        try:
            if "timestamp" not in data:
                import time
                data["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Send as message event
            self.sio.send(data)
            self.logger.info(f"Sent pallet data: {data.get('action', 'unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"Send failed: {e}")
            # Force reconnection on send failure to prevent zombie state
            self.logger.warning("Triggering reconnection due to send failure")
            self.is_connected = False
            self.sio.disconnect()
            return False

if __name__ == "__main__":
    config = CONFIG
    def mock_response(data):
        print(f"Mock response: {data}")
    
    ws = CloudWebSocket(config, mock_response)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
