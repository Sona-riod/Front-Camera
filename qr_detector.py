
import cv2
import numpy as np
import json
from typing import Tuple, List, Dict, Any
from pyzbar import pyzbar
from utils import ForkliftLogger, CONFIG, TRACKER, RECENT_CACHE

class QRDetectorError(Exception):
    pass

class QRDetector:
    def __init__(self, config: Dict[str, Any] = CONFIG):
        self.config = config
        self.logger = ForkliftLogger.setup(config['system']['log_level'])
        self.logger.info("Initialized QRDetector with standard pyzbar")

    def detect_and_filter_qrs(self, frame: np.ndarray) -> Tuple[List[Dict[str, Any]], int, np.ndarray]:
        try:
            detected_qrs = []
            candidate_ids = set()
            
            # Convert to grayscale for robust detection and to avoid numpy shape issues
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Decode QRs using pyzbar
            decoded_objects = pyzbar.decode(gray)
            
            for obj in decoded_objects:
                # Extract data
                try:
                    data_str = obj.data.decode('utf-8')
                    # Try to parse JSON if applicable, otherwise use raw string
                    try:
                        data = json.loads(data_str)
                        pallet_id = data.get('pallet_id', 'UNKNOWN')
                        kegs = data.get('kegs', [])
                    except json.JSONDecodeError:
                        pallet_id = data_str
                        kegs = []
                except Exception:
                    pallet_id = "UNKNOWN"
                    kegs = []
                
                # Get coordinates and ensure they are standard integers
                rect = obj.rect
                x1 = int(rect.left)
                y1 = int(rect.top)
                x2 = int(rect.left + rect.width)
                y2 = int(rect.top + rect.height)
                
                # Filter small invalid detections
                if (x2 - x1) < 10 or (y2 - y1) < 10:
                    continue

                candidate_ids.add(pallet_id)
                
                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Draw ID text
                text = f"{pallet_id[:15]}"
                cv2.putText(frame, text, (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                detected_qrs.append({
                    'pallet_id': pallet_id,
                    'kegs': kegs,
                    'position': (x1, y1),
                    'confidence': 1.0,
                    'bbox': (x1, y1, x2, y2)
                })

            # Stability tracking
            stable_ids = TRACKER.is_stable(candidate_ids)
            final_count = len(stable_ids)
            
            # Draw total count on frame
            cv2.putText(frame, f"QRs: {len(detected_qrs)}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.putText(frame, f"Stable: {final_count}", (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            if final_count > 0:
                self.logger.debug(f"Stable Count: {final_count} | IDs: {stable_ids}")
            
            return detected_qrs, final_count, frame
            
        except Exception as e:
            self.logger.error(f"Detection Error: {e}")
            # Draw error message on frame
            cv2.putText(frame, f"Detection Error", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            return [], 0, frame
