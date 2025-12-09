import sys
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt
from sensor_manager import SensorManager # Refactored data source
from views.acc_gyro_view import AccGyroView # New view for 2D plots
from views.magnetometer_view import MagnetometerView # New view for Mag
import math 
import time

# --- CONFIGURATION ---
SIMULATION_MODE = True  # Set to False to use real Serial
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200
ENABLE_POSITION_DAMPING = False # Set to True to prevent position drift (resets velocity)
ACCELERATION_DEADZONE = 50 # Set a threshold for linear acceleration to reduce drift. 0.0 to disable.
G = 9.81  # Gravity constant in mm/s²
# ---------------------

class Dashboard(QMainWindow):
    def __init__(self):
        global SIMULATION_MODE
        super().__init__()
        self.setWindowTitle("6-Axis Sensor Dashboard")
        self.resize(1200, 800)

        # Initialize sensor fusion variables
        self.current_yaw = 0.0
        self.last_update_time = time.time()
        
        # Physics State (Velocity and Position)
        self.vx, self.vy, self.vz = 0.0, 0.0, 0.0
        self.px, self.py, self.pz = 0.0, 0.0, 0.0

        # 1. Setup DockArea
        self.area = DockArea()
        self.setCentralWidget(self.area)

        # 2. Define Docks
        # Left side (approx 1/3 width implied by size ratio vs right dock)
        self.d_3d = Dock("3D Representation", size=(400, 400))
        self.d_controls = Dock("Controls", size=(400, 200))
        
        # Right side (approx 2/3 width)
        self.d_charts = Dock("Sensor Data (Acc & Gyro)", size=(800, 600))

        # 3. Layout Docks
        # Strategy: Place the main right-side content first, then carve out the left side.
        self.area.addDock(self.d_charts, 'right')     # Occupy full screen initially
        self.area.addDock(self.d_3d, 'left', self.d_charts) # Split: Left(3D) | Right(Charts)
        self.area.addDock(self.d_controls, 'bottom', self.d_3d) # Split Left: Top(3D) / Bottom(Controls)

        # --- LEFT PANEL CONTENT ---
        
        # 3D View
        self.w_3d = gl.GLViewWidget()
        self.w_3d.setCameraPosition(distance=20)
        
        # Add a grid
        grid = gl.GLGridItem()
        grid.setSize(x=20, y=20, z=20)
        grid.setSpacing(x=1, y=1, z=1)
        self.w_3d.addItem(grid)
        
        # OPTION 2: Coordinate Axes (using GLLinePlotItem for custom thickness)
        line_thickness = 3 # Adjust as needed
        axis_length = 1    # Length 1 as requested

        self.axes_items = []

        # X-axis (Red)
        self.x_axis = gl.GLLinePlotItem(pos=np.array([[0,0,0], [axis_length,0,0]]), color=(1,0,0,1), width=line_thickness)
        self.w_3d.addItem(self.x_axis)
        self.axes_items.append(self.x_axis)

        # Y-axis (Green)
        self.y_axis = gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,axis_length,0]]), color=(0,1,0,1), width=line_thickness)
        self.w_3d.addItem(self.y_axis)
        self.axes_items.append(self.y_axis)

        # Z-axis (Blue)
        self.z_axis = gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,0,axis_length]]), color=(0,0,1,1), width=line_thickness)
        self.w_3d.addItem(self.z_axis)
        self.axes_items.append(self.z_axis)
        
        self.d_3d.addWidget(self.w_3d)

        # Controls (Empty for now)
        self.w_controls = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Controls"))
        layout.addStretch()
        self.w_controls.setLayout(layout)
        self.d_controls.addWidget(self.w_controls)

        # --- RIGHT PANEL CONTENT (DOCKS) ---
        # Dock 1: Acc/Gyro
        self.d_acc_gyro = Dock("Acc & Gyro", size=(800, 600))
        self.acc_gyro_view = AccGyroView(self)
        self.d_acc_gyro.addWidget(self.acc_gyro_view)
        
        # Dock 2: Magnetometer
        self.d_magnetometer = Dock("Magnetometer", size=(800, 600))
        self.magnetometer_view = MagnetometerView(self)
        self.d_magnetometer.addWidget(self.magnetometer_view)

        # Layout Docks:
        # 1. Add Acc/Gyro to the right of 3D view
        self.area.addDock(self.d_acc_gyro, 'right', self.d_3d)
        
        # 2. Add Magnetometer. 
        # By adding it 'above' the Acc/Gyro dock, we split the right panel vertically.
        # Users can drag the title bar of one onto the other to create tabs if they prefer.
        self.area.addDock(self.d_magnetometer, 'above', self.d_acc_gyro)

        # --- DATA STREAM SETUP ---
        # Initialize Sensor Manager using global config
        self.sensor_manager = SensorManager(SERIAL_PORT, BAUD_RATE, SIMULATION_MODE)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(20) # 50 Hz update rate
        
        self.sim_t = 0

    def update(self):
        # --- 1. GET NEW SENSOR DATA ---
        new_data = self.sensor_manager.get_next_sample()
        
        if new_data is None:
            return # No data available
            
        # Handle 9-axis data (Acc, Gyro, Mag)
        # Acc/Gyro = indices 0-5
        # Mag = indices 6-8
        
        # --- 2. UPDATE PLOTS ---
        # Update Acc/Gyro View
        self.acc_gyro_view.update_view(new_data[:6])
        
        # Update Magnetometer View (if data available)
        if len(new_data) >= 9:
            self.magnetometer_view.update_view(new_data[6:9])

        # --- 3. CALCULATE ORIENTATION (Pitch, Roll, Yaw) ---
        ax, ay, az = new_data[0], new_data[1], new_data[2]
        gx, gy, gz = new_data[3], new_data[4], new_data[5]

        # Calculate dt for integration
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # --- Pitch & Roll (Accelerometer) ---
        # Calculate magnitude of acceleration in YZ plane
        acc_magnitude_yz = math.sqrt(ay*ay + az*az)
        
        pitch_rad = math.atan2(-ax, acc_magnitude_yz) if acc_magnitude_yz != 0 else 0
        roll_rad  = math.atan2(ay, az) if az != 0 else 0
        
        pitch = math.degrees(pitch_rad)
        roll  = math.degrees(roll_rad)

        # --- Yaw (Gyro Integration) ---
        self.current_yaw += gz * dt
        yaw = self.current_yaw
        yaw_rad = math.radians(yaw)

        # --- 4. POSITION PHYSICS (Double Integration) ---
        # Rotation Matrix construction (Yaw-Pitch-Roll sequence)
        
        # Precompute sines and cosines
        c_y, s_y = math.cos(yaw_rad), math.sin(yaw_rad)
        c_p, s_p = math.cos(pitch_rad), math.sin(pitch_rad)
        c_r, s_r = math.cos(roll_rad), math.sin(roll_rad)
        
        # X_World
        ax_w = (c_y*c_p) * ax + \
               (c_y*s_p*s_r - s_y*c_r) * ay + \
               (c_y*s_p*c_r + s_y*s_r) * az

        # Y_World
        ay_w = (s_y*c_p) * ax + \
               (s_y*s_p*s_r + c_y*c_r) * ay + \
               (s_y*s_p*c_r - c_y*s_r) * az
               
        # Z_World
        az_w = (-s_p) * ax + \
               (c_p*s_r) * ay + \
               (c_p*c_r) * az
               
        # Remove Gravity (assuming World Z is Up, and Gravity is -9.81 relative to that)
        az_w_linear = az_w - G
        
        # Deadzone (Noise Reduction)
        if abs(ax_w) < ACCELERATION_DEADZONE: ax_w = 0
        if abs(ay_w) < ACCELERATION_DEADZONE: ay_w = 0
        if abs(az_w_linear) < ACCELERATION_DEADZONE: az_w_linear = 0

        # Integrate Acceleration -> Velocity
        self.vx += ax_w * dt
        self.vy += ay_w * dt
        self.vz += az_w_linear * dt
        
        # Damping/Friction (CRITICAL to stop it flying away infinitely due to noise)
        if ENABLE_POSITION_DAMPING:
            damping_factor = 0.95
            self.vx *= damping_factor
            self.vy *= damping_factor
            self.vz *= damping_factor
        
        # Integrate Velocity -> Position
        self.px += self.vx * dt
        self.py += self.vy * dt
        self.pz += self.vz * dt
        
        # Use the Physics Integrated values for display
        px, py, pz = self.px, self.py, self.pz

        for axis_item in self.axes_items:
            axis_item.resetTransform()
            axis_item.translate(px, py, pz) # Move the object
            axis_item.rotate(yaw,   0, 0, 1) # Rotate around Z
            axis_item.rotate(pitch, 0, 1, 0) # Rotate around Y
            axis_item.rotate(roll,  1, 0, 0) # Rotate around X

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # --- DARK PALETTE SETUP ---
    from PyQt5.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    # --------------------------

    dash = Dashboard()
    dash.show()
    sys.exit(app.exec_())
