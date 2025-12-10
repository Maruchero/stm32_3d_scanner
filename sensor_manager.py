import serial
import numpy as np

class SensorManager:
    # Conversion Constants
    MG_TO_MS2 = 9.80665 / 1000.0
    MDPS_TO_DPS = 1.0 / 1000.0

    def __init__(self, port='/dev/ttyACM0', baud=115200, simulation_mode=True):
        self.port = port
        self.baud = baud
        self.simulation_mode = simulation_mode
        self.ser = None
        self.sim_t = 0
        self.buffer = "" # Persistent buffer for serial data

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
        Returns a numpy array of 9 floats in SI units:
        [ax (m/s^2), ay (m/s^2), az (m/s^2),
         gx (deg/s), gy (deg/s), gz (deg/s),
         mx (Gauss), my (Gauss), mz (Gauss)]
        
        Input data (Sim or Real) is assumed to be in mg, mdps, Gauss.
        """
        if self.simulation_mode:
            self.sim_t += 0.02 # Advance time slightly
            new_data = np.zeros(9)
            
            # Simulate Steady Board with Noise
            # Acc: Gravity on Z (+1000 mg), others near 0
            noise_acc_mg = 10.0 # mg (Reduced from 50.0)
            new_data[0] = np.random.normal(0, noise_acc_mg)        # Acc X (mg)
            new_data[1] = np.random.normal(0, noise_acc_mg)        # Acc Y (mg)
            new_data[2] = 1000.0 + np.random.normal(0, noise_acc_mg) # Acc Z (mg)
            
            # Gyro: Near 0
            noise_gyro_mdps = 50.0 # mdps (Reduced from 500.0)
            new_data[3] = np.random.normal(0, noise_gyro_mdps) # Gyro X (mdps)
            new_data[4] = np.random.normal(0, noise_gyro_mdps) # Gyro Y (mdps)
            new_data[5] = np.random.normal(0, noise_gyro_mdps) # Gyro Z (mdps)
            
            # Mag: Simulate pointing North (~0.5 Gauss)
            noise_mag = 0.01
            new_data[6] = 0.5 + np.random.normal(0, noise_mag)  # Mag X
            new_data[7] = np.random.normal(0, noise_mag)        # Mag Y
            new_data[8] = -0.5 + np.random.normal(0, noise_mag) # Mag Z
            
            # Convert to SI Units
            new_data[0:3] *= self.MG_TO_MS2
            new_data[3:6] *= self.MDPS_TO_DPS
            
            return new_data
        
        else:
            if self.ser and self.ser.in_waiting:
                try:
                    # Read everything currently in the hardware buffer
                    raw_data = self.ser.read(self.ser.in_waiting)
                    text_data = raw_data.decode('utf-8', errors='ignore')
                    self.buffer += text_data
                    
                    # Process packets in the buffer
                    last_valid_packet = None
                    
                    while True:
                        # Find next delimiter pair
                        start_idx = self.buffer.find('$')
                        end_idx = self.buffer.find(';')
                        
                        if start_idx != -1 and end_idx != -1 and start_idx > end_idx:
                            self.buffer = self.buffer[end_idx+1:]
                            continue

                        if start_idx != -1 and end_idx != -1:
                            packet_str = self.buffer[start_idx+1 : end_idx]
                            self.buffer = self.buffer[end_idx+1:]
                            
                            try:
                                parts = packet_str.split(' ')
                                parts = [p for p in parts if p] # Filter empty
                                
                                packet_data = None
                                if len(parts) == 6:
                                    # Backward compatibility: 6-axis
                                    data = [float(x) for x in parts]
                                    data.extend([0.0, 0.0, 0.0])
                                    packet_data = np.array(data)
                                elif len(parts) == 9:
                                    packet_data = np.array([float(x) for x in parts])
                                
                                if packet_data is not None:
                                    # Convert Raw (mg, mdps) to SI (m/s^2, deg/s)
                                    packet_data[0:3] *= self.MG_TO_MS2
                                    packet_data[3:6] *= self.MDPS_TO_DPS
                                    last_valid_packet = packet_data
                                    
                            except ValueError:
                                pass 
                        else:
                            break
                            
                    if len(self.buffer) > 1000:
                        self.buffer = ""
                        
                    return last_valid_packet

                except Exception as e:
                    print(f"Serial Read Error: {e}")
                    return None
            else:
                return None
