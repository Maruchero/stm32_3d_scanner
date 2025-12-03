import serial
import numpy as np

class SensorManager:
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
        Returns a numpy array of 6 floats [ax, ay, az, gx, gy, gz]
        or None if no data is available (waiting for serial).
        """
        if self.simulation_mode:
            self.sim_t += 0.02 # Advance time slightly
            new_data = np.zeros(6)
            
            # Simulate Steady Board with Noise (Real-world scenario)
            # Acc: Gravity on Z (+9.81), others near 0
            # Note: Standard IMUs read +1g on Z when flat.
            noise_level_acc = 0.05 # m/s^2
            new_data[0] = np.random.normal(0, noise_level_acc)      # Acc X
            new_data[1] = np.random.normal(0, noise_level_acc)      # Acc Y
            new_data[2] = 9.81 + np.random.normal(0, noise_level_acc) # Acc Z (Positive gravity)
            
            # Gyro: Near 0 (stationary)
            noise_level_gyro = 0.5 # degrees/s
            new_data[3] = np.random.normal(0, noise_level_gyro) # Gyro X
            new_data[4] = np.random.normal(0, noise_level_gyro) # Gyro Y
            new_data[5] = np.random.normal(0, noise_level_gyro) # Gyro Z
            
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
                        
                        # If we have a start but it's AFTER the end (e.g. "...; $..."), 
                        # we must discard the garbage before the '$'
                        if start_idx != -1 and end_idx != -1 and start_idx > end_idx:
                            # Discard everything up to the ';' we found (it's an orphan end)
                            self.buffer = self.buffer[end_idx+1:]
                            continue

                        if start_idx != -1 and end_idx != -1:
                            # We have a potentially valid packet "$...;"
                            packet_str = self.buffer[start_idx+1 : end_idx]
                            
                            # Remove this packet from buffer
                            self.buffer = self.buffer[end_idx+1:]
                            
                            # Parse this packet
                            try:
                                parts = packet_str.split(' ')
                                parts = [p for p in parts if p] # Filter empty
                                if len(parts) == 6:
                                    last_valid_packet = np.array([float(x) for x in parts])
                            except ValueError:
                                pass # parsing failed, move to next
                        else:
                            # No complete packet found yet
                            break
                            
                    # If buffer gets too huge (no delimiters found), clear it to prevent memory leak
                    if len(self.buffer) > 1000:
                        self.buffer = ""
                        
                    return last_valid_packet

                except Exception as e:
                    print(f"Serial Read Error: {e}")
                    return None
            else:
                return None
