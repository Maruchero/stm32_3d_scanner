import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout

class MagnetometerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.w_charts = pg.GraphicsLayoutWidget()
        self.layout.addWidget(self.w_charts)

        # Create 3 plots in a vertical stack (1 column, 3 rows)
        self.plots = []
        self.curves = []
        
        titles = ["Mag X (North)", "Mag Y (East)", "Mag Z (Down)"]
        
        for row in range(3):
            title = titles[row]
            # Add plot to layout
            p = self.w_charts.addPlot(row=row, col=0, title=title)
            p.showGrid(x=True, y=True)
            p.setLabel('left', 'Field', units='Gauss')
            
            # Create a curve (Cyan color)
            c = p.plot(pen='c') 
            
            self.plots.append(p)
            self.curves.append(c)
            
        # Data buffers for 3 channels
        self.history_length = 200
        self.data_buffer = np.zeros((3, self.history_length))

    def update_view(self, mag_data):
        """
        Updates the 3 plots with new magnetometer data.
        mag_data: A numpy array of 3 floats (mx, my, mz).
        """
        # Update Buffers
        # Roll buffer back
        self.data_buffer = np.roll(self.data_buffer, -1, axis=1)
        # Insert new data at the end
        self.data_buffer[:, -1] = mag_data

        for i, curve in enumerate(self.curves):
            curve.setData(self.data_buffer[i])
