import sys
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer
import serial

# --- CONFIGURATION ---
SIMULATION_MODE = True  # Set to False to use real Serial
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200
# ---------------------

class Dashboard(QMainWindow):
    def __init__(self):
        global SIMULATION_MODE
        super().__init__()
        self.setWindowTitle("6-Axis Sensor Dashboard")
        self.resize(1200, 800)

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
        # Place 3D dock first
        self.area.addDock(self.d_3d, 'left')
        # Place Controls under 3D
        self.area.addDock(self.d_controls, 'bottom', self.d_3d)
        # Place Charts to the right of the 3D/Control column
        self.area.addDock(self.d_charts, 'right', self.d_3d)

        # --- LEFT PANEL CONTENT ---
        
        # 3D View (Empty for now)
        self.w_3d = gl.GLViewWidget()
        self.w_3d.setCameraPosition(distance=20)
        # Add a grid just so it's not pitch black and we know it's working
        grid = gl.GLGridItem()
        self.w_3d.addItem(grid)
        self.d_3d.addWidget(self.w_3d)

        # Controls (Empty for now)
        self.w_controls = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Controls Section (Placeholder)"))
        layout.addStretch()
        self.w_controls.setLayout(layout)
        self.d_controls.addWidget(self.w_controls)

        # --- RIGHT PANEL CONTENT (6 CHARTS) ---
        self.w_charts = pg.GraphicsLayoutWidget()
        self.d_charts.addWidget(self.w_charts)

        # Create 6 plots in a 2-column x 3-row grid
        # Col 1: Accelerometer, Col 2: Gyroscope
        self.plots = []
        self.curves = []
        
        # Titles
        titles = [
            ("Acc X", "Acc Y", "Acc Z"),
            ("Gyro X", "Gyro Y", "Gyro Z")
        ]
        
        # We want:
        # Acc X | Gyro X
        # Acc Y | Gyro Y
        # Acc Z | Gyro Z
        
        for row in range(3):
            row_plots = []
            for col in range(2):
                title = titles[col][row]
                # Add plot to layout
                p = self.w_charts.addPlot(row=row, col=col, title=title)
                p.showGrid(x=True, y=True)
                # Create a curve
                c = p.plot(pen=(col+1, 3)) # Different color for Acc vs Gyro
                
                self.plots.append(p)
                self.curves.append(c)
            
        # Data buffers for 6 channels
        self.history_length = 200
        self.data_buffer = np.zeros((6, self.history_length))

        # --- DATA STREAM SETUP ---
        if not SIMULATION_MODE:
            try:
                self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
                print(f"Connected to {SERIAL_PORT}")
            except Exception as e:
                print(f"Serial Error: {e}")
                print("Switching to SIMULATION_MODE")
                SIMULATION_MODE = True

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(20) # 50 Hz update rate
        
        self.sim_t = 0

    def update(self):
        new_data = np.zeros(6)

        if SIMULATION_MODE:
            self.sim_t += 0.1
            # Simulate Acc (X, Y, Z) - sinusoidal
            new_data[0] = np.sin(self.sim_t)      # Acc X
            new_data[1] = np.cos(self.sim_t)      # Acc Y
            new_data[2] = np.sin(self.sim_t*0.5)  # Acc Z
            
            # Simulate Gyro (X, Y, Z) - noisy
            new_data[3] = np.random.normal(0, 0.5) # Gyro X
            new_data[4] = np.random.normal(0, 0.5) # Gyro Y
            new_data[5] = np.random.normal(0, 0.5) # Gyro Z
            
        else:
            if self.ser.in_waiting:
                try:
                    # Expecting CSV: "ax,ay,az,gx,gy,gz\n"
                    line = self.ser.readline().decode().strip()
                    parts = line.split(',')
                    if len(parts) == 6:
                        new_data = np.array([float(x) for x in parts])
                    else:
                        # Malformed line
                        return 
                except Exception as e:
                    print(f"Parse Error: {e}")
                    return
            else:
                return # No new data

        # Update Buffers
        # Roll buffer back
        self.data_buffer = np.roll(self.data_buffer, -1, axis=1)
        # Insert new data at the end
        self.data_buffer[:, -1] = new_data

        # Update Curves
        # We stored curves in a flattened list: 
        # [AccX, GyroX, AccY, GyroY, AccZ, GyroZ] due to the loop order?
        # Wait, loop was:
        # for row:
        #   for col:
        #     append
        # So list is: [Row0Col0, Row0Col1, Row1Col0, Row1Col1, Row2Col0, Row2Col1]
        # Which corresponds to: [AccX, GyroX, AccY, GyroY, AccZ, GyroZ]
        
        # Our data buffer is 0..5. 
        # Let's map them correctly:
        # Buffer Indices: 0=AccX, 1=AccY, 2=AccZ, 3=GyroX, 4=GyroY, 5=GyroZ
        
        # Curve List Indices:
        # 0: AccX (Row0, Col0) -> Data 0
        # 1: GyroX (Row0, Col1) -> Data 3
        # 2: AccY (Row1, Col0) -> Data 1
        # 3: GyroY (Row1, Col1) -> Data 4
        # 4: AccZ (Row2, Col0) -> Data 2
        # 5: GyroZ (Row2, Col1) -> Data 5
        
        mapping = [0, 3, 1, 4, 2, 5]
        
        for i, curve in enumerate(self.curves):
            data_index = mapping[i]
            curve.setData(self.data_buffer[data_index])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dash = Dashboard()
    dash.show()
    sys.exit(app.exec_())
