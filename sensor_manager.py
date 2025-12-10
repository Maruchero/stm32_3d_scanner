import serial
import numpy as np

class SensorManager:
    def __init__(self, port='/dev/ttyACM0', baud=115200, simulation_mode=True):
        self.port = port
        self.baud = baud
        self.simulation_mode = simulation_mode
        self.ser = None
        self.sim_t = 0

        if not self.simulation_mode:
            try:
                self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
                print(f"Connected to {self.port}")
            except Exception as e:
                print(f"Serial Error: {e}")
                print("Switching to SIMULATION_MODE")
                self.simulation_mode = True

    def get_next_sample(self):
        """
        Returns a numpy array of 9 floats [ax, ay, az, gx, gy, gz, mx, my, mz]
        or None if no data is available (waiting for serial).
        """
        if self.simulation_mode:
            self.sim_t += 0.02 # Advance time slightly
            new_data = np.zeros(9)
            
            # Simulate Steady Board with Noise (Real-world scenario)
            # Acc: Gravity on Z (+9.81)
            noise_level_acc = 0.05
            new_data[0] = np.random.normal(0, noise_level_acc)      # Acc X
            new_data[1] = np.random.normal(0, noise_level_acc)      # Acc Y
            new_data[2] = 9.81 + np.random.normal(0, noise_level_acc) # Acc Z
            
            # Gyro: Near 0
            noise_level_gyro = 0.5
            new_data[3] = np.random.normal(0, noise_level_gyro) # Gyro X
            new_data[4] = np.random.normal(0, noise_level_gyro) # Gyro Y
            new_data[5] = np.random.normal(0, noise_level_gyro) # Gyro Z
            
            # Mag: Simulate pointing North (X-axis) with some Z component (dip)
            # Field strength ~0.5 Gauss (50 uT)
            noise_level_mag = 0.01
            new_data[6] = 0.5 + np.random.normal(0, noise_level_mag)  # Mag X (North)
            new_data[7] = np.random.normal(0, noise_level_mag)        # Mag Y (East/West)
            new_data[8] = -0.5 + np.random.normal(0, noise_level_mag) # Mag Z (Down)
            
            return new_data
        
        else:
            if self.ser and self.ser.in_waiting:
                try:
                    # Expecting CSV: "ax,ay,az,gx,gy,gz\n" or "ax,ay,az,gx,gy,gz,mx,my,mz\n"
                    line = self.ser.read_until(expected=b";$").decode().strip()
                    # print(line)
                    parts = line.replace("\x00", "").split(";$")[0].split(' ')
                    # print(parts)
                    if len(parts) == 6:
                        # Backward compatibility: 6-axis (Acc+Gyro), pad Mag with 0
                        data = [float(x) for x in parts]
                        data.extend([0.0, 0.0, 0.0]) # Mag X, Y, Z
                        return np.array(data)
                    elif len(parts) == 9:
                        # Full 9-axis (Acc+Gyro+Mag)
                        return np.array([float(x) for x in parts])
                    else:
                        # Malformed line
                        return None
                except Exception as e:
                    print(f"Serial Parse Error: {e}")
                    return None
            else:
                return None
