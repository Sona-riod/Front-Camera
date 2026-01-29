CONFIG = {
    "camera": {
        # --- iCAM-540 Configuration ---
        'type': 'v4l2',
        'device': 10,   # /dev/video10
        'width': 1920,
        'height': 1080,
        'fps': 30,
        
        # --- Algorithm Settings (Required by main.py) ---
        "yolo_model_path": "best.pt",
        "yolo_conf_threshold": 0.5,
        "frame_delay": 0.1,
        "temporal_buffer_size": 5,
        "dynamic_roi_enabled": False,
    },
    
    "websocket": {
        # The main Cloud Server URL
        "url": "http://143.110.186.93:5001",
    },
    
    "api": {
        # Cloud API Endpoints
        "customer_api_url": "http://143.110.186.93:5001/api/kegs/customers-for-cam",
        "keg_count_api_url": "http://143.110.186.93:5001/api/pallette/get-kegs-for-multiple-palettes",
        "end_point_api_url": "http://143.110.186.93:5001/api/kegs/camera-update-palette",
        
        # Connection settings
        "api_timeout": 10,
    },
    
    "system": {
        "forklift_id": "FORK001",
        "mac_id": "3C:6D:66:01:5A:F0",  
        "log_level": "INFO",
        "location_sim_interval": 10,
        "recent_pallet_cache_size": 10,
        "test_mode": False,
    },
    
    "hmi": {
        "screen_width": 800,
        "screen_height": 600,
        "button_size": (200, 80),
    }
}