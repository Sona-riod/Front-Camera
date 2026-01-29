from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.properties import StringProperty, ColorProperty
import cv2
import numpy as np
import threading

# Modern Industrial Dark Palette with better contrast
# Professional Light Palette
COLORS = {
    'background': (0.94, 0.95, 0.97, 1),    # #F0F2F7 (Soft Blue-Gray)
    'surface': (1.0, 1.0, 1.0, 1),          # #FFFFFF (Pure White)
    'primary': (0.0, 0.48, 1.0, 1),         # #007AFF (Vibrant Blue)
    'primary_dark': (0.0, 0.38, 0.8, 1),    # Darker Blue
    'accent': (1.0, 0.58, 0.0, 1),          # #FF9500 (Orange)
    'success': (0.20, 0.78, 0.35, 1),       # #34C759 (Green)
    'warning': (1.0, 0.8, 0.0, 1),          # #FFCC00 (Yellow)
    'danger': (1.0, 0.23, 0.19, 1),         # #FF3B30 (Red)
    'neutral': (0.56, 0.56, 0.58, 1),       # #8E8E93 (Gray)
    'text_primary': (0.0, 0.0, 0.0, 0.87),  # High Emphasis Black
    'text_secondary': (0.0, 0.0, 0.0, 0.54),# Medium Emphasis Black
    'text_on_color': (1.0, 1.0, 1.0, 1),    # White text on colored buttons
    'divider': (0.85, 0.85, 0.85, 1),       # Light Divider
}

class StyledButton(Button):
    def __init__(self, text="", bg_color=COLORS['primary'], text_color=COLORS['text_on_color'], font_size='16sp', **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0,0,0,0)  # Transparent main bg, drawing manually
        self.bg_color_base = bg_color
        self.text = text
        self.color = text_color
        self.bold = True
        self.font_size = font_size
        self.size_hint_y = None
        self.height = 50
        
        with self.canvas.before:
            # Drop shadow simulation (only bottom offset)
            Color(0, 0, 0, 0.15)
            self.shadow = RoundedRectangle(pos=(self.x + 2, self.y - 2), size=self.size, radius=[8])
            
            self.rect_color = Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[8])
        
        self.bind(pos=self.update_rect, size=self.update_rect)
        self.bind(on_press=self.on_button_press, on_release=self.on_button_release)
        self.bind(disabled=self.on_disabled_change)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        self.shadow.pos = (self.x + 2, self.y - 3)
        self.shadow.size = self.size
    
    def on_button_press(self, *args):
        if self.disabled: return
        # Darken on press
        darker = tuple(max(0, c * 0.8) for c in self.bg_color_base[:3]) + (self.bg_color_base[3],)
        self.rect_color.rgba = darker
        # Push effect (move down slightly)
        self.rect.pos = (self.x, self.y - 1)

    def on_button_release(self, *args):
        if self.disabled: return
        self.rect_color.rgba = self.bg_color_base
        self.rect.pos = self.pos

    def on_disabled_change(self, instance, value):
        if value: # Disabled
            # Grayed out look
            self.rect_color.rgba = (0.8, 0.8, 0.8, 1)
            self.color = (0.5, 0.5, 0.5, 1) # Dim text
            self.shadow.size = (0,0) # Hide shadow
        else:
            self.rect_color.rgba = self.bg_color_base
            self.color = COLORS['text_on_color']
            self.shadow.size = self.size

class StatusCard(BoxLayout):
    def __init__(self, title="", value="", bg_color=COLORS['surface'], **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 20
        self.spacing = 5
        self.size_hint_y = None
        self.height = 130
        
        with self.canvas.before:
            # Card Shadow
            Color(0, 0, 0, 0.05)
            self.shadow = RoundedRectangle(pos=(self.x+2, self.y-2), size=self.size, radius=[12])
            
            Color(*bg_color)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
            
            # Subtle Border
            Color(*COLORS['divider'])
            self.border = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 12), width=1.2)
        
        self.bind(pos=self.update_graphics, size=self.update_graphics)
        
        self.title_label = Label(text=title, color=COLORS['text_secondary'], font_size='14sp', bold=True, size_hint_y=0.3, halign='left', valign='bottom')
        self.title_label.bind(size=self.title_label.setter('text_size'))
        
        self.value_label = Label(text=str(value), color=COLORS['primary'], font_size='36sp', bold=True, size_hint_y=0.7, halign='left', valign='top')
        self.value_label.bind(size=self.value_label.setter('text_size'))
        
        self.add_widget(self.title_label)
        self.add_widget(self.value_label)
    
    def update_graphics(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.shadow.pos = (self.x+3, self.y-3)
        self.shadow.size = self.size
        self.border.rounded_rectangle = (self.x, self.y, self.width, self.height, 12)
    
    def update_value(self, value):
        self.value_label.text = str(value)

class CameraPreview(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        with self.canvas.before:
            Color(*COLORS['surface'])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[15])
            Color(*COLORS['divider'])
            # Inset the border by 1 pixel to ensure it sits inside/on-top cleanly
            self.border = Line(rounded_rectangle=(self.x + 1, self.y + 1, self.width - 2, self.height - 2, 15), width=1.5)
        
        self.bind(pos=self.update_bg, size=self.update_bg)
        
        self.camera_img = Image()
        self.add_widget(self.camera_img)
        
        self.overlay = Label(text='Camera Initializing...', color=(1, 1, 1, 1), font_size='18sp', bold=True, size_hint=(None, None), size=(300, 50), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        with self.overlay.canvas.before:
            Color(0, 0, 0, 0.8)
            self.overlay_rect = RoundedRectangle(pos=self.overlay.pos, size=self.overlay.size, radius=[10])
        self.overlay.bind(pos=self.update_overlay, size=self.update_overlay)
        self.add_widget(self.overlay)
    
    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        # Update border with inset
        self.border.rounded_rectangle = (self.x + 1, self.y + 1, self.width - 2, self.height - 2, 15)
    
    def update_overlay(self, *args):
        self.overlay_rect.pos = self.overlay.pos
        self.overlay_rect.size = self.overlay.size
    
    def show_error(self, message):
        self.overlay.text = message
        self.overlay.opacity = 1
        
    def hide_error(self):
        if self.overlay.opacity > 0:
            Animation(opacity=0, duration=0.5).start(self.overlay)

    def update_frame(self, frame):
        try:
            buf = cv2.flip(frame, 0).tobytes()
            texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            self.camera_img.texture = texture
            
            if self.overlay.text == 'Camera Initializing...' and self.overlay.opacity > 0:
                 Animation(opacity=0, duration=0.5).start(self.overlay)
        except Exception:
            self.show_error('Camera Error')

class ZoneIndicator(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.padding = 15
        self.spacing = 20
        self.size_hint_y = None
        self.height = 100
        
        with self.canvas.before:
            Color(*COLORS['surface'])
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[15])
        
        self.bind(pos=self.update_bg, size=self.update_bg)
        
        self.indicator_layout = FloatLayout(size_hint_x=0.15)
        with self.indicator_layout.canvas:
            self.indicator_color = Color(*COLORS['primary'])
            self.indicator = RoundedRectangle(pos=(0, 0), size=(70, 70), radius=[35])
        self.indicator_layout.bind(pos=self.update_indicator, size=self.update_indicator)
        
        text_layout = BoxLayout(orientation='vertical', size_hint_x=0.30, padding=(0, 2))
        self.zone_label = Label(text='CURRENT ZONE', color=COLORS['text_secondary'], font_size='10sp', bold=True, size_hint_y=0.35, halign='left')
        self.zone_label.bind(size=self.zone_label.setter('text_size'))
        
        self.zone_value = Label(text='WAITING FOR LOCATION...', color=COLORS['text_primary'], font_size='15sp', bold=True, size_hint_y=0.65, halign='left')
        self.zone_value.bind(size=self.zone_value.setter('text_size'))
        
        text_layout.add_widget(self.zone_label)
        text_layout.add_widget(self.zone_value)
        
        self.add_widget(self.indicator_layout)
        self.add_widget(text_layout)
    
    def update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
    
    def update_indicator(self, *args):
        center_x = self.indicator_layout.x + self.indicator_layout.width / 2 - 35
        center_y = self.indicator_layout.y + self.indicator_layout.height / 2 - 35
        self.indicator.pos = (center_x, center_y)
    
    def set_zone(self, zone):
        zone_lower = zone.lower()
        
        if "storage" in zone_lower:
            color = COLORS['success']
            self.zone_value.text = "STORAGE AREA"
        elif "dispatch" in zone_lower:
            color = COLORS['accent']
            self.zone_value.text = "DISPATCH AREA"
        else:
            color = COLORS['primary']
            self.zone_value.text = "IN TRANSIT"
        
        Animation(rgba=color, duration=0.3).start(self.indicator_color)

class ForkliftUI(BoxLayout):
    def __init__(self, on_confirm, on_start_capture, on_stop_capture, mac_id="UNKNOWN", **kwargs):
        super().__init__(**kwargs)
        self.on_confirm = on_confirm
        self.on_start_capture = on_start_capture
        self.on_stop_capture = on_stop_capture
        self.mac_id = mac_id
        self.orientation = 'vertical'
        self.padding = 15
        self.spacing = 15
        self.current_count = 0
        self.current_qrs = []
        self.is_camera_connected = True
        self.customer_data = {}
        self.is_popup_open = False
        
        self.status_banner = Label(text="DISCONNECTED", color=(1, 1, 1, 1), bold=True, font_size='14sp', size_hint_y=None, height=30, opacity=1)
        with self.status_banner.canvas.before:
            self.status_bg_color = Color(*COLORS['danger'])
            self.status_bg = Rectangle(pos=self.status_banner.pos, size=self.status_banner.size)
        
        self.status_banner.bind(pos=self.update_status_bg, size=self.update_status_bg)
        self.add_widget(self.status_banner)

        with self.canvas.before:
            Color(*COLORS['background'])
            self.bg = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(pos=self.update_bg, size=self.update_bg)
        
        self.zone_indicator = ZoneIndicator()
        self.add_widget(self.zone_indicator)
        
        self.tabs = TabbedPanel(do_default_tab=False, tab_height=70)
        self.tabs.background_color = COLORS['background']
        
        self.tab_storage = TabbedPanelItem(text='STORAGE')
        self.tab_storage.background_normal = ''
        self.tab_storage.color = (1, 1, 1, 1) # Force white text
        self.tab_storage.background_color = COLORS['primary']
        self.tab_storage.content = self._build_storage_layout()
        self.tabs.add_widget(self.tab_storage)
        
        self.tab_dispatch = TabbedPanelItem(text='DISPATCH')
        self.tab_dispatch.background_normal = ''
        self.tab_dispatch.color = (1, 1, 1, 1) # Force white text
        self.tab_dispatch.background_color = COLORS['accent']
        self.tab_dispatch.content = self._build_dispatch_layout()
        self.tabs.add_widget(self.tab_dispatch)
        
        self.tabs.default_tab = self.tab_storage
        self.add_widget(self.tabs)
    
    def update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
    
    def _build_storage_layout(self):
        layout = BoxLayout(orientation='horizontal', padding=10, spacing=15)
        with layout.canvas.before:
            Color(*COLORS['background'])
            layout.bg = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=lambda *args: setattr(layout.bg, 'pos', layout.pos), size=lambda *args: setattr(layout.bg, 'size', layout.size))
        
        self.cam_prev_store = CameraPreview(size_hint_x=0.6)
        layout.add_widget(self.cam_prev_store)
        
        right = BoxLayout(orientation='vertical', size_hint_x=0.4, spacing=15)
        self.card_qr_count = StatusCard(title="PALLETS DETECTED", value="0", bg_color=COLORS['surface'])
        right.add_widget(self.card_qr_count)
        
        right.add_widget(BoxLayout(size_hint_y=0.2))
        
        # Button Row - Reorganized for better spacing and alignment
        btn_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=140, spacing=15)
        
        # Row 1: Operations
        ops_row = BoxLayout(orientation='horizontal', spacing=15, size_hint_y=None, height=55)
        
        self.btn_capture = StyledButton(text="CAPTURE", bg_color=COLORS['primary'], text_color=COLORS['text_on_color'])
        self.btn_capture.bind(on_release=self._on_capture_pressed)
        
        self.btn_stop = StyledButton(text="STOP", bg_color=COLORS['danger'], text_color=COLORS['text_on_color'])
        self.btn_stop.bind(on_release=self._on_stop_pressed)
        self.btn_stop.disabled = True
        
        self.btn_reset = StyledButton(text="RESET", bg_color=COLORS['warning'], text_color=COLORS['text_on_color'])
        self.btn_reset.bind(on_release=self._on_reset_pressed)
        
        ops_row.add_widget(self.btn_capture)
        ops_row.add_widget(self.btn_stop)
        ops_row.add_widget(self.btn_reset)
        
        # Row 2: Actions (Confirm) - Made prominent
        action_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=65)
        self.btn_manual_store = StyledButton(text="CONFIRM", bg_color=COLORS['success'], text_color=COLORS['text_on_color'], font_size='18sp')
        self.btn_manual_store.bind(on_release=lambda x: self.show_storage_popup(self.current_count))
        self.btn_manual_store.disabled = True
        action_row.add_widget(self.btn_manual_store)
        
        btn_layout.add_widget(ops_row)
        btn_layout.add_widget(action_row)
        
        right.add_widget(btn_layout)
        
        right.add_widget(BoxLayout(size_hint_y=0.02))
        
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        
        self.lbl_live_list_title = Label(text="LIVE DETECTIONS:", color=COLORS['text_secondary'], font_size='13sp', bold=True, size_hint_y=None, height=25, halign='left')
        self.lbl_live_list_title.bind(size=self.lbl_live_list_title.setter('text_size'))
        right.add_widget(self.lbl_live_list_title)
        
        scroll_live = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        with scroll_live.canvas.before:
             Color(0, 0, 0, 0.05) # Very subtle background for list
             RoundedRectangle(pos=scroll_live.pos, size=scroll_live.size, radius=[8])
             Color(*COLORS['divider'])
             Line(rounded_rectangle=(scroll_live.x, scroll_live.y, scroll_live.width, scroll_live.height, 8), width=1)
        
        self.live_list_layout = GridLayout(cols=1, spacing=5, size_hint_y=None, padding=8)
        self.live_list_layout.bind(minimum_height=self.live_list_layout.setter('height'))
        
        scroll_live.bind(pos=lambda *args: args, size=lambda *args: args) # Dummy bind to force update if needed, but usually strictly canvas
        
        scroll_live.add_widget(self.live_list_layout)
        right.add_widget(scroll_live)
        
        layout.add_widget(right)
        return layout
    
    def _on_capture_pressed(self, instance):
        if self.on_start_capture:
            self.on_start_capture()
        
        self.btn_capture.disabled = True
        self.btn_stop.disabled = False
        self.btn_manual_store.disabled = True
        self.btn_capture.opacity = 0.5
        self.btn_stop.opacity = 1
        
        self.show_operation_success("Detection Started")

    def _on_stop_pressed(self, instance):
        if self.on_stop_capture:
            self.on_stop_capture()
            
        self.btn_capture.disabled = False
        self.btn_stop.disabled = True
        self.btn_manual_store.disabled = False if self.current_count > 0 else True
        self.btn_capture.opacity = 1
        self.btn_stop.opacity = 0.5
        
        self.show_operation_success("Detection Stopped")

    def _on_reset_pressed(self, instance):
        from utils import ACCUMULATED_TRACKER
        ACCUMULATED_TRACKER.reset()
        self.current_count = 0
        self.current_qrs = []
        self.card_qr_count.update_value("0")
        
        # Reset button states to initial "Idle" state
        self.btn_capture.disabled = False
        self.btn_stop.disabled = True
        self.btn_manual_store.disabled = True
        
        # Visual reset
        self.btn_capture.opacity = 1
        self.btn_stop.opacity = 0.5
              
        self.show_operation_success("Counts Reset Successfully")
    
    def _build_dispatch_layout(self):
        layout = BoxLayout(orientation='horizontal', padding=10, spacing=15)
        with layout.canvas.before:
            Color(*COLORS['background'])
            layout.bg = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=lambda *args: setattr(layout.bg, 'pos', layout.pos), size=lambda *args: setattr(layout.bg, 'size', layout.size))
        
        self.cam_prev_disp = CameraPreview(size_hint_x=0.6)
        layout.add_widget(self.cam_prev_disp)
        
        right = BoxLayout(orientation='vertical', size_hint_x=0.4, spacing=20)
        self.card_disp_count = StatusCard(title="PALLETS READY", value="0", bg_color=COLORS['surface'])
        right.add_widget(self.card_disp_count)
        
        cust_layout = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None, height=150)
        
        # Header with Label and Refresh Button
        cust_header = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=10)
        cust_label = Label(text="SELECT CUSTOMER:", color=COLORS['text_primary'], font_size='18sp', bold=True, halign='left', valign='middle')
        cust_label.bind(size=cust_label.setter('text_size'))
        cust_header.add_widget(cust_label)
        
        self.btn_refresh_cust = StyledButton(text="REFRESH", bg_color=COLORS['neutral'], text_color=COLORS['text_on_color'], font_size='12sp')
        self.btn_refresh_cust.height = 35
        self.btn_refresh_cust.size_hint_x = 0.4
        self.btn_refresh_cust.bind(on_release=self._on_refresh_customers)
        cust_header.add_widget(self.btn_refresh_cust)
        
        cust_layout.add_widget(cust_header)
        
        self.spinner_cust = Spinner(text='WAITING FOR CUSTOMERS...', values=['WAITING FOR CUSTOMERS...'], size_hint_y=None, height=60, background_normal='', background_color=COLORS['surface'], color=COLORS['text_primary'], font_size='16sp', bold=True)
        cust_layout.add_widget(self.spinner_cust)
        right.add_widget(cust_layout)
        
        right.add_widget(BoxLayout(size_hint_y=0.3))
        
        # Dispatch Button - Made large and prominent
        self.btn_dispatch = StyledButton(text="CONFIRM DISPATCH", bg_color=COLORS['danger'], text_color=COLORS['text_on_color'], font_size='18sp')
        self.btn_dispatch.bind(on_release=self.confirm_dispatch)
        self.btn_dispatch.disabled = True
        self.btn_dispatch.height = 65
        self.btn_dispatch.size_hint_y = None
        right.add_widget(self.btn_dispatch)
        
        right.add_widget(BoxLayout(size_hint_y=0.05))
        
        self.lbl_live_list_disp_title = Label(text="LIVE DETECTIONS:", color=COLORS['text_secondary'], font_size='13sp', bold=True, size_hint_y=None, height=25, halign='left')
        self.lbl_live_list_disp_title.bind(size=self.lbl_live_list_disp_title.setter('text_size'))
        right.add_widget(self.lbl_live_list_disp_title)
        
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        
        scroll_live_disp = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        with scroll_live_disp.canvas.before:
             Color(0, 0, 0, 0.05)
             RoundedRectangle(pos=scroll_live_disp.pos, size=scroll_live_disp.size, radius=[8])
             Color(*COLORS['divider'])
             Line(rounded_rectangle=(scroll_live_disp.x, scroll_live_disp.y, scroll_live_disp.width, scroll_live_disp.height, 8), width=1)
        
        self.live_list_disp_layout = GridLayout(cols=1, spacing=5, size_hint_y=None, padding=8)
        self.live_list_disp_layout.bind(minimum_height=self.live_list_disp_layout.setter('height'))
        
        scroll_live_disp.add_widget(self.live_list_disp_layout)
        right.add_widget(scroll_live_disp)
        
        layout.add_widget(right)
        return layout
    
    def update_camera_feed(self, frame):
        if self.tabs.current_tab == self.tab_storage:
            self.cam_prev_store.update_frame(frame)
        elif self.tabs.current_tab == self.tab_dispatch:
            self.cam_prev_disp.update_frame(frame)
    
    def update_info(self, current_count, current_qrs, accumulated_count=None, accumulated_qrs=None):
        if accumulated_count is not None:
            self.current_count = accumulated_count
            self.current_qrs = accumulated_qrs or []
        else:
            self.current_count = current_count
            self.current_qrs = current_qrs
        
        self.card_disp_count.update_value(self.current_count)
        self.card_qr_count.update_value(f"{self.current_count} PALLETS")
        
        self.update_button_states()
        
        if hasattr(self, 'live_list_layout'):
            self.live_list_layout.clear_widgets()
            from utils import sort_pallet_data
            sorted_data = sort_pallet_data(self.current_qrs)
            for qr in sorted_data:
                pid = qr.get('pallet_id', 'UNKNOWN')
                # Use a small background for list items for readability
                item = BoxLayout(size_hint_y=None, height=35)
                with item.canvas.before:
                    Color(1, 1, 1, 1) # White bg for item
                    RoundedRectangle(pos=item.pos, size=item.size, radius=[4])
                # Note: modifying canvas in loop can be heavy if many items, but for <50 it's fine.
                # Actually, simpler is just black text on transparency since we have a light container.
                # Let's stick to clean text.
                lbl = Label(text=f"• {pid}", color=COLORS['text_primary'], font_size='15sp', size_hint_y=None, height=30, halign='left')
                lbl.bind(size=lbl.setter('text_size'))
                self.live_list_layout.add_widget(lbl)
        
        if hasattr(self, 'live_list_disp_layout'):
            self.live_list_disp_layout.clear_widgets()
            for qr in sorted_data:
                pid = qr.get('pallet_id', 'UNKNOWN')
                lbl = Label(text=f"• {pid}", color=COLORS['text_primary'], font_size='15sp', size_hint_y=None, height=30, halign='left')
                lbl.bind(size=lbl.setter('text_size'))
                self.live_list_disp_layout.add_widget(lbl)
    
    def update_zone_status(self, zone):
        self.zone_indicator.set_zone(zone)
        zone_lower = zone.lower()
        if "storage" in zone_lower:
            self.tabs.switch_to(self.tab_storage)
        elif "dispatch" in zone_lower:
            self.tabs.switch_to(self.tab_dispatch)
    
    def update_customer_list(self, customers):
        if customers:
            self.customer_data = {}
            customer_names = []
            for c in customers:
                if isinstance(c, dict):
                    name = c.get('name', '')
                    cust_id = c.get('_id', '')
                    if name:
                        self.customer_data[name] = cust_id
                        customer_names.append(name)
            self.spinner_cust.values = customer_names
            self.spinner_cust.text = "SELECT CUSTOMER"
            
    def _on_refresh_customers(self, instance):
        self.btn_refresh_cust.disabled = True
        self.btn_refresh_cust.text = "LOADING..."
        threading.Thread(target=self._fetch_and_update_customers, daemon=True).start()

    def _fetch_and_update_customers(self):
        from utils import fetch_customer_details
        customers = fetch_customer_details()
        Clock.schedule_once(lambda dt: self._post_refresh_ui_update(customers))

    def _post_refresh_ui_update(self, customers):
        self.update_customer_list(customers)
        self.btn_refresh_cust.disabled = False
        self.btn_refresh_cust.text = "REFRESH"
        self.show_operation_success("Customer List Refreshed")
            
    def update_connection_status(self, status):
        if status == "connected":
            self.status_banner.text = "CONNECTED TO CLOUD"
            self.status_bg_color.rgba = COLORS['success']
            Animation(opacity=0, duration=1).start(self.status_banner)
        elif status == "connecting":
            self.status_banner.text = "CONNECTING..."
            self.status_bg_color.rgba = COLORS['warning']
            self.status_banner.opacity = 1
        else:
            self.status_banner.text = "DISCONNECTED"
            self.status_bg_color.rgba = COLORS['danger']
            self.status_banner.opacity = 1
    
    def update_status_bg(self, *args):
        self.status_bg.pos = self.status_banner.pos
        self.status_bg.size = self.status_banner.size

    def set_camera_error(self, message):
        self.cam_prev_store.show_error(message)
        self.cam_prev_disp.show_error(message)
        self.is_camera_connected = False
        self.update_button_states()
        
    def clear_camera_error(self):
        self.cam_prev_store.hide_error()
        self.cam_prev_disp.hide_error()
        self.is_camera_connected = True
        self.update_button_states()

    def show_operation_error(self, message):
        original_text = self.status_banner.text
        original_color = self.status_bg_color.rgba
        original_opacity = self.status_banner.opacity
        
        self.status_banner.text = message
        self.status_bg_color.rgba = COLORS['danger']
        self.status_banner.opacity = 1
        
        def restore(dt):
            if self.status_banner.text == message:
                self.status_banner.text = original_text
                self.status_bg_color.rgba = original_color
                self.status_banner.opacity = original_opacity
        Clock.schedule_once(restore, 3)

    def show_operation_success(self, message):
        original_text = self.status_banner.text
        original_color = self.status_bg_color.rgba
        original_opacity = self.status_banner.opacity
        
        self.status_banner.text = message
        self.status_bg_color.rgba = COLORS['success']
        self.status_banner.opacity = 1
        
        def restore(dt):
            if self.status_banner.text == message:
                self.status_banner.text = original_text
                self.status_bg_color.rgba = original_color
                self.status_banner.opacity = original_opacity
        Clock.schedule_once(restore, 3)

    def update_button_states(self):
        # Determine strict state from UI controls
        # If Stop button is ENABLED, we are currently CAPTURING.
        is_capturing = not self.btn_stop.disabled
        
        # Confirm actions allowed ONLY if:
        # 1. Camera is connected
        # 2. We have detected items (count > 0)
        # 3. We are NOT currently capturing (Must Stop first)
        can_confirm = self.is_camera_connected and (self.current_count > 0) and not is_capturing
        
        if hasattr(self, 'btn_manual_store'):
            self.btn_manual_store.disabled = not can_confirm
            self.btn_manual_store.opacity = 1 if can_confirm else 0.5
            
        if hasattr(self, 'btn_dispatch'):
            self.btn_dispatch.disabled = not can_confirm
            self.btn_dispatch.opacity = 1 if can_confirm else 0.5
            
        if hasattr(self, 'btn_capture'):
             if not self.is_camera_connected:
                 self.btn_capture.disabled = True
                 self.btn_capture.opacity = 0.5
             else:
                 # If connected, ensure Capture is enabled if we are NOT capturing (Idle)
                 # This handles re-enabling after camera error or state reset
                 if not is_capturing:
                     self.btn_capture.disabled = False
                     self.btn_capture.opacity = 1
    
    def show_storage_popup(self, count, show_details=True):
        if self.is_popup_open:
            return
        self.is_popup_open = True
        
        from utils import sort_pallet_data
        sorted_qrs = sort_pallet_data(self.current_qrs)
        
        content = BoxLayout(orientation='vertical', padding=25, spacing=20)
        with content.canvas.before:
            Color(*COLORS['surface'])
            content.bg = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda *args: setattr(content.bg, 'pos', content.pos), size=lambda *args: setattr(content.bg, 'size', content.size))
        
        self.pending_sorted_qrs = sorted_qrs
        content.add_widget(Label(text='STORAGE CONFIRMATION', color=COLORS['primary'], font_size='24sp', bold=True, size_hint_y=None, height=20))
        
        self.popup_content_area = BoxLayout(orientation='vertical', spacing=10)
        self.loading_label = Label(text="Loading details...", font_size='20sp', color=COLORS['text_secondary'])
        self.popup_content_area.add_widget(self.loading_label)
        content.add_widget(self.popup_content_area)
        
        content.add_widget(BoxLayout(size_hint_y=0.1))
        
        btn_layout = BoxLayout(orientation='horizontal', spacing=20, size_hint_y=None, height=60)
        btn_cancel = StyledButton(text="CANCEL", bg_color=COLORS['neutral'], text_color=COLORS['text_on_color'])
        btn_cancel.bind(on_release=lambda x: self.popup.dismiss())
        
        self.btn_ok = StyledButton(text="CONFIRM STORAGE", bg_color=COLORS['success'], text_color=COLORS['text_on_color'])
        self.btn_ok.bind(on_release=self._do_store)
        self.btn_ok.disabled = True
        
        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(self.btn_ok)
        content.add_widget(btn_layout)
        
        self.popup = Popup(title='', content=content, size_hint=(0.85, 0.8), separator_height=0, background='', background_color=COLORS['surface'])
        self.popup.bind(on_dismiss=lambda x: setattr(self, 'is_popup_open', False))
        self.popup.open()
        
        threading.Thread(target=self._fetch_details_for_popup, args=(sorted_qrs,), daemon=True).start()

    def _fetch_details_for_popup(self, sorted_qrs):
        from utils import fetch_pallet_keg_counts
        pallet_ids = [q.get('pallet_id', 'UNKNOWN') for q in sorted_qrs]
        keg_counts = fetch_pallet_keg_counts(pallet_ids)
        Clock.schedule_once(lambda dt: self._update_popup_with_details(sorted_qrs, keg_counts))

    def _update_popup_with_details(self, sorted_qrs, keg_counts):
        if not hasattr(self, 'popup_content_area'): return
        self.popup_content_area.clear_widgets()
        
        self.popup_content_area.add_widget(Label(text=f"DETECTED: {len(sorted_qrs)} PALLETS", color=COLORS['text_primary'], font_size='22sp', bold=True, size_hint_y=None, height=40))
        
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        list_layout = GridLayout(cols=1, spacing=5, size_hint_y=None, padding=10)
        list_layout.bind(minimum_height=list_layout.setter('height'))
        
        for q in sorted_qrs:
            pid = q.get('pallet_id', 'UNKNOWN')
            raw_val = keg_counts.get(pid, 0)
            if isinstance(raw_val, list): k_count = len(raw_val)
            elif isinstance(raw_val, (int, float)): k_count = int(raw_val)
            else: k_count = 0
            
            row = BoxLayout(size_hint_y=None, height=40)
            lbl_id = Label(text=pid, size_hint_x=0.8, halign='left', color=COLORS['text_secondary'])
            lbl_id.bind(size=lbl_id.setter('text_size'))
            lbl_count = Label(text=f"{k_count} Kegs", size_hint_x=0.2, halign='right', color=COLORS['accent'], bold=True)
            lbl_count.bind(size=lbl_count.setter('text_size'))
            row.add_widget(lbl_id)
            row.add_widget(lbl_count)
            list_layout.add_widget(row)
            
        scroll.add_widget(list_layout)
        self.popup_content_area.add_widget(scroll)
        self.btn_ok.disabled = False

    def _do_store(self, instance):
        qrs_to_send = getattr(self, 'pending_sorted_qrs', self.current_qrs)
        pallet_ids = [qr.get('pallet_id', 'UNKNOWN') for qr in qrs_to_send]
        # Strict filtering: remove UNKNOWN or empty
        pallet_ids = [pid for pid in pallet_ids if pid and pid != "UNKNOWN"]
        
        from utils import send_camera_update_palette
        all_success = True
        
        for pallet_id in pallet_ids:
            response = send_camera_update_palette(pallet_id=pallet_id, area_name="Storage Area", customer_id="")
            if "error" in response: all_success = False
        
        if all_success:
            from utils import ACCUMULATED_TRACKER
            ACCUMULATED_TRACKER.reset()
            self.current_count = 0
            self.current_qrs = []
            self.card_qr_count.update_value("0")
            self.update_button_states()
            self.show_operation_success("Added to Storage")
            self.tabs.switch_to(self.tab_storage) # Ensure we stay/return to storage tab visually or just refresh
            self.popup.dismiss()
        else:
            self.show_operation_error("STORAGE CONFIRMATION FAILED")
    
    def confirm_dispatch(self, instance):
        if self.spinner_cust.text in ['WAITING FOR CUSTOMERS...', 'SELECT CUSTOMER']: return
        self.show_dispatch_popup(self.current_count, self.spinner_cust.text)

    def show_dispatch_popup(self, count, customer_name):
        if self.is_popup_open: return
        self.is_popup_open = True
        
        from utils import sort_pallet_data
        sorted_qrs = sort_pallet_data(self.current_qrs)
        
        content = BoxLayout(orientation='vertical', padding=25, spacing=20)
        with content.canvas.before:
            Color(*COLORS['surface'])
            content.bg = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda *args: setattr(content.bg, 'pos', content.pos), size=lambda *args: setattr(content.bg, 'size', content.size))
        
        self.pending_dispatch_customer = customer_name
        self.pending_sorted_qrs = sorted_qrs

        content.add_widget(Label(text='DISPATCH CONFIRMATION', color=COLORS['accent'], font_size='24sp', bold=True, size_hint_y=None, height=40))
        content.add_widget(Label(text=f"TO: {customer_name}", color=COLORS['text_primary'], font_size='20sp', bold=True, size_hint_y=None, height=30))
        
        self.popup_disp_content = BoxLayout(orientation='vertical', spacing=10)
        self.popup_disp_content.add_widget(Label(text="Loading details...", font_size='20sp', color=COLORS['text_secondary']))
        content.add_widget(self.popup_disp_content)
        
        content.add_widget(BoxLayout(size_hint_y=0.1))
        
        btn_layout = BoxLayout(orientation='horizontal', spacing=20, size_hint_y=None, height=60)
        btn_cancel = StyledButton(text="CANCEL", bg_color=COLORS['neutral'], text_color=COLORS['text_on_color'])
        btn_cancel.bind(on_release=lambda x: self.popup.dismiss())
        
        self.btn_final_dispatch = StyledButton(text="CONFIRM DISPATCH", bg_color=COLORS['danger'], text_color=COLORS['text_on_color'])
        self.btn_final_dispatch.bind(on_release=self._do_dispatch)
        self.btn_final_dispatch.disabled = True
        
        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(self.btn_final_dispatch)
        content.add_widget(btn_layout)
        
        self.popup = Popup(title='', content=content, size_hint=(0.85, 0.8), separator_height=0, background='', background_color=COLORS['surface'])
        self.popup.bind(on_dismiss=lambda x: setattr(self, 'is_popup_open', False))
        self.popup.open()
        
        threading.Thread(target=self._fetch_dispatch_details, args=(sorted_qrs,), daemon=True).start()

    def _fetch_dispatch_details(self, sorted_qrs):
        from utils import fetch_pallet_keg_counts
        pallet_ids = [q.get('pallet_id', 'UNKNOWN') for q in sorted_qrs]
        keg_counts = fetch_pallet_keg_counts(pallet_ids)
        Clock.schedule_once(lambda dt: self._update_dispatch_popup(sorted_qrs, keg_counts))

    def _update_dispatch_popup(self, sorted_qrs, keg_counts):
        if not hasattr(self, 'popup_disp_content'): return
        self.popup_disp_content.clear_widgets()
        
        self.popup_disp_content.add_widget(Label(text=f"DETECTED: {len(sorted_qrs)} PALLETS", color=COLORS['text_primary'], font_size='18sp', bold=True, size_hint_y=None, height=30))
        
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        list_layout = GridLayout(cols=1, spacing=5, size_hint_y=None, padding=10)
        list_layout.bind(minimum_height=list_layout.setter('height'))
        
        for q in sorted_qrs:
            pid = q.get('pallet_id', 'UNKNOWN')
            raw_val = keg_counts.get(pid, 0)
            if isinstance(raw_val, list): k_count = len(raw_val)
            elif isinstance(raw_val, (int, float)): k_count = int(raw_val)
            else: k_count = 0
            
            row = BoxLayout(size_hint_y=None, height=40)
            lbl_id = Label(text=pid, size_hint_x=0.8, halign='left', color=COLORS['text_secondary'])
            lbl_id.bind(size=lbl_id.setter('text_size'))
            lbl_count = Label(text=f"{k_count} Kegs", size_hint_x=0.2, halign='right', color=COLORS['accent'], bold=True)
            lbl_count.bind(size=lbl_count.setter('text_size'))
            row.add_widget(lbl_id)
            row.add_widget(lbl_count)
            list_layout.add_widget(row)
            
        scroll.add_widget(list_layout)
        self.popup_disp_content.add_widget(scroll)
        self.btn_final_dispatch.disabled = False

    def _do_dispatch(self, instance):
        qrs_to_send = getattr(self, 'pending_sorted_qrs', self.current_qrs)
        cust_name = getattr(self, 'pending_dispatch_customer', "UNKNOWN")
        customer_id = self.customer_data.get(cust_name, "")
        pallet_ids = [qr.get('pallet_id', 'UNKNOWN') for qr in qrs_to_send]
        # Strict filtering
        pallet_ids = [pid for pid in pallet_ids if pid and pid != "UNKNOWN"]
        
        from utils import send_camera_update_palette
        all_success = True
        
        for pallet_id in pallet_ids:
            response = send_camera_update_palette(pallet_id=pallet_id, area_name="Dispatch Area", customer_id=customer_id)
            if "error" in response: all_success = False
        
        if all_success:
            from utils import ACCUMULATED_TRACKER
            ACCUMULATED_TRACKER.reset()
            self.current_count = 0
            self.current_qrs = []
            self.card_disp_count.update_value("0")
            self.update_button_states()
            self.popup.dismiss()
            self.show_operation_success("Successfully Dispatched")
        else:
            self.show_operation_error("DISPATCH CONFIRMATION FAILED")

class ForkliftHMIApp(App):
    def __init__(self, on_confirm, on_start_capture, on_stop_capture, mac_id="UNKNOWN", **kwargs):
        super().__init__(**kwargs)
        self.on_confirm = on_confirm
        self.on_start_capture = on_start_capture
        self.on_stop_capture = on_stop_capture
        self.mac_id = mac_id
        self.root_widget = None
    
    def build(self):
        self.root_widget = ForkliftUI(self.on_confirm, self.on_start_capture, self.on_stop_capture, self.mac_id)
        return self.root_widget