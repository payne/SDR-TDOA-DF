#!/usr/bin/env python3
import numpy as np
from scipy import signal
from scipy.optimize import minimize
import matplotlib.pyplot as plt

class TDOAProcessor:
    def __init__(self):
        self.c = 299792458  # Speed of light in m/s
        
    def load_samples(self, filename):
        """Load samples from NPZ file"""
        data = np.load(filename)
        return {
            'samples': data['samples'],
            'timestamp': float(data['timestamp']),
            'station_id': str(data['station_id']),
            'sample_rate': float(data['sample_rate']),
            'center_freq': float(data['center_freq'])
        }
    
    def correlate_signals(self, sig1, sig2, sample_rate):
        """Cross-correlate two signals to find time delay"""
        # Normalize signals
        sig1 = sig1 - np.mean(sig1)
        sig2 = sig2 - np.mean(sig2)
        
        # Cross-correlation
        correlation = signal.correlate(sig1, sig2, mode='full')
        lags = signal.correlation_lags(len(sig1), len(sig2), mode='full')
        
        # Find peak
        peak_idx = np.argmax(np.abs(correlation))
        time_delay = lags[peak_idx] / sample_rate
        
        return time_delay, correlation, lags
    
    def tdoa_multilateration(self, station_positions, time_differences):
        """Calculate transmitter position using TDOA"""
        def objective(tx_pos):
            """Minimize the error in TDOA equations"""
            error = 0
            for (i, j), tdoa in time_differences.items():
                dist_i = np.linalg.norm(tx_pos - station_positions[i])
                dist_j = np.linalg.norm(tx_pos - station_positions[j])
                predicted_tdoa = (dist_i - dist_j) / self.c
                error += (predicted_tdoa - tdoa) ** 2
            return error
        
        # Initial guess (center of stations)
        initial_guess = np.mean(list(station_positions.values()), axis=0)
        
        # Optimize
        result = minimize(objective, initial_guess, method='BFGS')
        return result.x
    
    def plot_results(self, station_positions, estimated_position):
        """Plot the results on a map"""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot stations
        for station_id, pos in station_positions.items():
            ax.scatter(pos[1], pos[0], s=100, c='blue', marker='^', 
                      label=f'{station_id}')
            ax.text(pos[1], pos[0], f'\n{station_id}', ha='center')
        
        # Plot estimated transmitter position
        ax.scatter(estimated_position[1], estimated_position[0], 
                  s=200, c='red', marker='*', label='Estimated TX')
        
        # Plot actual WXL68 position (if known)
        # WXL68 is located near 108th and West Dodge Road
        actual_pos = [41.2619, -96.0819]  # Approximate coordinates
        ax.scatter(actual_pos[1], actual_pos[0], 
                  s=200, c='green', marker='o', label='Actual TX')
        
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title('TDOA Direction Finding - WXL68 162.400 MHz')
        ax.legend()
        ax.grid(True)
        
        plt.tight_layout()
        plt.savefig('tdoa_results.png')
        plt.show()

# Example usage
if __name__ == "__main__":
    processor = TDOAProcessor()
    
    # Define station positions (latitude, longitude)
    # These are example positions - use actual GPS coordinates
    station_positions = {
        'station1': np.array([41.24668, -96.08368]),  # West Omaha - n3pay
        'station2': np.array([41.18669, -95.96059]),  # Bellevue - kx0u
        'station3': np.array([41.326720, -96.134780])   #   - KF0PGK
    }
    
    # Load data from each station
    # In practice, you would load the actual collected files
    print("TDOA Processing Example")
    processor.load_samples('station1')
    print("Configure with actual station positions and data files")

