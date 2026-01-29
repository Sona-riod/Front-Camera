import cv2
import time
import threading
from typing import Dict, Any
from kivy.clock import Clock

# --- STRICT IMPORTS (No Mocks) ---
from utils import CONFIG, ForkliftLogger, RECENT_CACHE, ACCUMULATED_TRACKER, fetch_customer_details
from qr_detector import QRDetector
from websocket_client import CloudWebSocket
from camera import CameraManager
from hmi import ForkliftHMIApp

class ForkliftFrontSystem:
    def __init__(self):
        self.config = CONFIG
        self.logger = ForkliftLogger.setup(self.config['system']['log_level'])
        
        # Initialize Camera
        self.camera_manager = CameraManager(self.config, self.logger)
        
        # Initialize QR Detector
        try:
            self.qr_detector = QRDetector(self.config)
        except Exception as e:
            self.logger.critical(f"Failed to initialize QR detector: {e}")
            raise e
        
        self.last_qrs = []
        self.last_count = 0
        self.current_location = "neutral"
        self.detection_active = False # Default to False (Manual Mode)
        self.hmi = None
        self.running = True
        
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0
        
        # --- CAPTURE CONTROL CALLBACKS ---
        def start_capture_session():
            self.logger.info("Starting Capture Session")
            ACCUMULATED_TRACKER.reset()
            self.detection_active = True
            
        def stop_capture_session():
            self.logger.info("Stopping Capture Session")
            self.detection_active = False
            
        # --- WEBSOCKET HANDLERS ---
        def ws_response(data: Dict[str, Any]):
            """Handle messages FROM Cloud"""
            try:
                self.logger.info(f"Cloud message: {data}")
                
                # --- TYPE 1: LOCATION UPDATE ---
                if data.get("type") == "location_update":
                    new_loc = data.get("location", "neutral")
                    old_loc = self.current_location
                    
                    self.current_location = new_loc
                    
                    if self.hmi and self.hmi.root_widget:
                        # Update Zone Indicator
                        Clock.schedule_once(lambda dt: self.hmi.root_widget.update_zone_status(new_loc))
                        
                        # LOGIC: Storage Popup (Only if location CHANGED)
                        if new_loc == "Storage Area" and old_loc != "Storage Area":
                            self.logger.info("Entering Storage - Triggering Auto-Popup")
                            Clock.schedule_once(lambda dt: self.hmi.root_widget.show_storage_popup(self.last_count, show_details=False))
                        
                        # LOGIC: Dispatch Popup (Only if location CHANGED)
                        elif new_loc == "Dispatch Area" and old_loc != "Dispatch Area":
                            self.logger.info("Entering Dispatch - Triggering Auto-Popup")
                            self._fetch_and_update_customers()
                            Clock.schedule_once(lambda dt: self.hmi.root_widget.confirm_dispatch(None))

                # --- TYPE 2: FORCED CONFIRMATION ---
                elif data.get("type") == "confirmation_request":
                    zone = data.get("zone", "storage")
                    if zone == "storage" or zone == "Storage Area":
                        Clock.schedule_once(lambda dt: self.hmi.root_widget.show_storage_popup(self.last_count))
                    elif zone == "dispatch":
                        self._fetch_and_update_customers()
                        Clock.schedule_once(lambda dt: self.hmi.root_widget.confirm_dispatch(None))
                
                # --- TYPE 3: STATUS ---
                elif data.get("status"):
                    self.logger.info(f"Server response: {data['status']}")
                    
            except Exception as e:
                self.logger.error(f"Error processing WebSocket response: {e}")
        
        def ws_confirm(data: Dict[str, Any]):
            """Handle 'Submit' button click"""
            try:
                # Cache QRs to prevent immediate re-detection
                for qr in self.last_qrs:
                    RECENT_CACHE.add(qr.get('pallet_id'))
                
                from utils import get_mac_address
                data["mac_id"] = get_mac_address()
                data["forklift_id"] = self.config['system']['forklift_id']
                data["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
                data["location"] = self.current_location
                
                if self.ws.send_pallet_data(data):
                    self.logger.info("Confirmation sent to cloud")
                    return True
                else:
                    self.logger.warning("Failed to send confirmation")
                    return False
            except Exception as e:
                self.logger.error(f"Error sending confirmation: {e}")
                return False
        
        def ws_status(status):
            if self.hmi and self.hmi.root_widget:
                Clock.schedule_once(lambda dt: self.hmi.root_widget.update_connection_status(status))

        # Initialize WebSocket
        try:
            self.ws = CloudWebSocket(self.config, ws_response, ws_status)
        except Exception as e:
            self.logger.error(f"Failed to initialize WebSocket: {e}")
            self.ws = None
        
        # Initialize HMI
        mac_id = self.config['system'].get('mac_id', 'UNKNOWN')
        self.hmi = ForkliftHMIApp(ws_confirm, start_capture_session, stop_capture_session, mac_id)
        
        # Fetch customers on startup
        Clock.schedule_once(lambda dt: self._fetch_and_update_customers(), 2)
    
    def _fetch_and_update_customers(self):
        def fetch_thread():
            try:
                customers = fetch_customer_details()
                if self.hmi and self.hmi.root_widget:
                    Clock.schedule_once(lambda dt: self.hmi.root_widget.update_customer_list(customers))
            except Exception as e:
                self.logger.error(f"Error fetching customers: {e}")
        threading.Thread(target=fetch_thread, daemon=True).start()
    
    def calculate_fps(self):
        self.fps_counter += 1
        elapsed = time.time() - self.fps_start_time
        if elapsed >= 1.0:
            self.current_fps = self.fps_counter / elapsed
            self.logger.debug(f"FPS: {self.current_fps:.1f}")
            self.fps_counter = 0
            self.fps_start_time = time.time()
    
    def run_camera_loop(self):
        self.logger.info("Starting Camera Loop")
        consecutive_failures = 0
        
        while self.running:
            try:
                # 1. READ FRAME
                ret, frame = self.camera_manager.read_frame()
                
                if not ret:
                    consecutive_failures += 1
                    if self.hmi and self.hmi.root_widget:
                         Clock.schedule_once(lambda dt: self.hmi.root_widget.set_camera_error("CAMERA NOT INITIALIZED"))
                    time.sleep(0.1)
                    continue
                
                consecutive_failures = 0
                
                # 2. DETECT QR
                qrs, count = [], 0
                if self.qr_detector and self.detection_active:
                    try:
                        qrs, count, _ = self.qr_detector.detect_and_filter_qrs(frame)
                        self.last_qrs = qrs
                        self.last_count = count
                        for qr in qrs:
                            ACCUMULATED_TRACKER.add_detection(qr)
                    except Exception as e:
                        self.logger.warning(f"Detection Error: {e}")
                
                # 3. UPDATE HMI
                accumulated_count = ACCUMULATED_TRACKER.get_count()
                accumulated_qrs = ACCUMULATED_TRACKER.get_all_qrs()
                
                if self.hmi and self.hmi.root_widget:
                    # Resize for UI preview performance
                    preview_frame = cv2.resize(frame, (320, 240))
                    Clock.schedule_once(lambda dt: self.hmi.root_widget.update_camera_feed(preview_frame))
                    
                    if not self.camera_manager.is_opened:
                        Clock.schedule_once(lambda dt: self.hmi.root_widget.set_camera_error("CAMERA CONNECTION FAILED"))
                    else:
                        Clock.schedule_once(lambda dt: self.hmi.root_widget.clear_camera_error())

                    Clock.schedule_once(lambda dt, c=count, q=qrs, ac=accumulated_count, aq=accumulated_qrs: 
                                       self.hmi.root_widget.update_info(c, q, ac, aq))
                
                self.calculate_fps()
                time.sleep(0.05)
                
            except Exception as e:
                self.logger.error(f"Error in camera loop: {e}")
                time.sleep(0.5)
        
        self.logger.info("Camera loop stopped")
    
    def start(self):
        try:
            self.logger.info("Starting System...")
            cam_thread = threading.Thread(target=self.run_camera_loop, daemon=True)
            cam_thread.start()
            self.hmi.run()
        except KeyboardInterrupt:
            self.shutdown()
        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            self.shutdown()
    
    def shutdown(self):
        self.logger.info("Shutting down...")
        self.running = False
        if self.camera_manager:
            self.camera_manager.release()

if __name__ == "__main__":
    system = ForkliftFrontSystem()
    system.start()