import sys
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt
from sensor_manager import SensorManager # Refactored data source
from sensor_fusion import SensorFusion # Refactored math engine
from views.acc_gyro_view import AccGyroView # New view for 2D plots
from views.magnetometer_view import MagnetometerView # New view for Mag
import math 
import time

# --- CONFIGURATION ---
SIMULATION_MODE = False  # Set to False to use real Serial
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200
ENABLE_POSITION_DAMPING = False # Set to True to prevent position drift (resets velocity)
ACCELERATION_DEADZONE = 0.0 # Set a threshold for linear acceleration to reduce drift. 0.0 to disable.
G = 9.81  # Gravity constant in mm/s²
# ---------------------

class Dashboard(QMainWindow):
    def __init__(self):
        global SIMULATION_MODE  # DO NOT REMOVE THIS LINE, it's necessary
        super().__init__()
        self.setWindowTitle("6-Axis Sensor Dashboard")
        self.resize(1200, 800)

        # Initialize sensor fusion engine
        self.sensor_fusion = SensorFusion(damping=ENABLE_POSITION_DAMPING, deadzone=ACCELERATION_DEADZONE)
        self.last_update_time = time.time()
        
        # 1. Setup DockArea
        self.area = DockArea()
        self.setCentralWidget(self.area)

        # 2. Define Docks
        # Left side (approx 1/3 width implied by size ratio vs right dock)
        self.d_3d = Dock("3D Representation", size=(400, 400))
        self.d_controls = Dock("Controls", size=(400, 200))
        
        # Right side (approx 2/3 width)
        self.d_acc_gyro = Dock("Acc & Gyro", size=(800, 600))
        self.d_magnetometer = Dock("Magnetometer", size=(800, 600))
        
        # 3. Layout Docks
        # Strategy: Place the main right-side content first, then carve out the left side.
        
        # Add Acc/Gyro to the right, which will form the main right panel
        self.area.addDock(self.d_acc_gyro, 'right') 
        
        # Add Magnetometer above Acc/Gyro (splits right panel vertically)
        self.area.addDock(self.d_magnetometer, 'above', self.d_acc_gyro)
        
        # Add 3D view to the left of the Acc/Gyro block
        self.area.addDock(self.d_3d, 'left', self.d_acc_gyro) 
        
        # Add Controls under 3D
        self.area.addDock(self.d_controls, 'bottom', self.d_3d)

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

        # --- RIGHT PANEL CONTENT (VIEW WIDGETS) ---
        # View 1: Acc/Gyro
        self.acc_gyro_view = AccGyroView(self)
        self.d_acc_gyro.addWidget(self.acc_gyro_view)
        
        # View 2: Magnetometer
        self.magnetometer_view = MagnetometerView(self)
        self.d_magnetometer.addWidget(self.magnetometer_view)

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

        # --- 3. CALCULATE ORIENTATION & PHYSICS ---
        ax, ay, az = new_data[0], new_data[1], new_data[2]
        gx, gy, gz = new_data[3], new_data[4], new_data[5]

        # Calculate dt
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Update Physics Engine
        pitch, roll, yaw, px, py, pz = self.sensor_fusion.update(ax, ay, az, gx, gy, gz, dt)
        
        # If in simulation mode, we OVERRIDE this physics position with the figure-8 for demo purposes
        if self.sensor_manager.simulation_mode:
            # px, py, pz are already set at the top of update()
            pass
        else:
            # Real Mode: Use the Physics Integrated values
            pass

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
