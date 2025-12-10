import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout

class AccGyroView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.w_charts = pg.GraphicsLayoutWidget()
        self.layout.addWidget(self.w_charts)

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

    def update_view(self, new_data_6axis):
        """
        Updates the 6 plots with new accelerometer and gyroscope data.
        new_data_6axis: A numpy array of 6 floats (ax, ay, az, gx, gy, gz).
        """
        # Update Buffers
        # Roll buffer back
        self.data_buffer = np.roll(self.data_buffer, -1, axis=1)
        # Insert new data at the end
        self.data_buffer[:, -1] = new_data_6axis

        # Update Curves
        # Map: 0=AccX, 1=AccY, 2=AccZ, 3=GyroX, 4=GyroY, 5=GyroZ
        # Curve order in self.curves: AccX, GyroX, AccY, GyroY, AccZ, GyroZ
        mapping = [0, 3, 1, 4, 2, 5]
        
        for i, curve in enumerate(self.curves):
            data_index = mapping[i]
            curve.setData(self.data_buffer[data_index])
