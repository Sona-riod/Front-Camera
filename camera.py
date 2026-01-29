import cv2
import logging

class CameraManager:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger if logger else logging.getLogger("CameraManager")
        self.cap = None
        self.is_opened = False
        self.frame_count = 0
        
        self._initialize_camera()
    
    def _initialize_camera(self):
        # Get the camera dictionary from config
        cam_conf = self.config.get('camera', {})
        
        # 1. READ YOUR SPECIFIC KEYS
        device_index = cam_conf.get('device', 10)  # Default to 10 if missing
        backend_type = cam_conf.get('type', 'v4l2')
        width = cam_conf.get('width', 1920)
        height = cam_conf.get('height', 1080)
        fps = cam_conf.get('fps', 30)
        
        self.logger.info(f"Opening camera {device_index} (Type: {backend_type})...")
        
        # 2. SELECT BACKEND
        # If config says 'v4l2', force the V4L2 backend
        backend = cv2.CAP_V4L2 if backend_type.lower() == 'v4l2' else cv2.CAP_ANY
        
        self.cap = cv2.VideoCapture(device_index, backend)
        
        if self.cap.isOpened():
            # 3. APPLY SETTINGS
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            
            self.is_opened = True
            
            # Optional: Log to verify actual settings
            real_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            real_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            self.logger.info(f"Camera opened successfully: {int(real_w)}x{int(real_h)} @ {fps}FPS")
        else:
            self.logger.error(f"Camera initialization failed! Device {device_index} not found.")
            self.is_opened = False
    
    def read_frame(self):
        if self.is_opened and self.cap:
            ret, frame = self.cap.read()
            if ret:
                self.frame_count += 1
                return True, frame
            else:
                self.logger.warning("Failed to read frame from camera")
                return False, None
        
        return False, None
    
    def release(self):
        if self.cap:
            self.cap.release()
            self.logger.info("Camera released")