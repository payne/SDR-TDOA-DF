#!/usr/bin/env python3
import pdb
import numpy as np
from scipy import signal
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import glob
import os
from datetime import datetime
import folium

class TDOAProcessor:
    def __init__(self):
        self.c = 299792458  # Speed of light in m/s
        self.station_positions = {
            'station1': np.array([41.24668, -96.08368]),  # West Omaha - n3pay
            'station2': np.array([41.18669, -95.96059]),  # Bellevue - kx0u
            'station3': np.array([41.326720, -96.134780])   #   - KF0PGK
            }
        sample_rate = 1.024e6
        self.station_data = {
           'station1': { 'samples': 42, 'timestamp': 1751236060, 'sample_rate': sample_rate },
           'station2': { 'samples': 42, 'timestamp': 1751236060, 'sample_rate': 60e6 }, 
           'station3': { 'samples': 42, 'timestamp': 1751236060, 'sample_rate': 60e6 }, 
         }

        
    def load_all_samples(self, directory='.'):
        """Load all .npz files from directory"""
        npz_files = glob.glob(os.path.join(directory, 'tdoa_*.npz'))
        
        if not npz_files:
            raise ValueError(f"No .npz files found in {directory}")
        
        # Group files by timestamp (assuming files from same collection have similar timestamps)
        timestamp_groups = {}
        
        for file in npz_files:
            data = np.load(file)
            timestamp = float(data['timestamp'])
            station_id = str(data['station_id'])
            
            # Round timestamp to nearest second to group synchronized collections
            rounded_timestamp = round(timestamp)
            
            if rounded_timestamp not in timestamp_groups:
                timestamp_groups[rounded_timestamp] = {}
            
            timestamp_groups[rounded_timestamp][station_id] = {
                'samples': data['samples'],
                'timestamp': timestamp,
                'sample_rate': float(data['sample_rate']),
                'center_freq': float(data['center_freq']),
                'filename': file
            }
            
        # Find the most recent complete set (has all stations)
        for timestamp in sorted(timestamp_groups.keys(), reverse=True):
            if len(timestamp_groups[timestamp]) >= 3:
                self.station_data = timestamp_groups[timestamp]
                print(f"Using data from timestamp {timestamp} ({datetime.fromtimestamp(timestamp)})")
                for station, data in self.station_data.items():
                    print(f"  {station}: {data['filename']}")
                return True
                
        print("YOLO! Make an image anyway.")
        return True
        print("Warning: No complete set of synchronized samples found")
        # Use the most recent timestamp even if incomplete
        latest_timestamp = max(timestamp_groups.keys())
        self.station_data = timestamp_groups[latest_timestamp]
        return False
        
    def correlate_signals(self, sig1, sig2, sample_rate):
        """Cross-correlate two signals to find time delay"""
        # Limit correlation length for efficiency
        debugger
        max_correlation_samples = min(len(sig1), len(sig2), int(0.1 * sample_rate))
        sig1 = sig1[:max_correlation_samples]
        sig2 = sig2[:max_correlation_samples]
        
        # Normalize signals
        sig1 = sig1 - np.mean(sig1)
        sig2 = sig2 - np.mean(sig2)
        sig1 = sig1 / (np.std(sig1) + 1e-10)
        sig2 = sig2 / (np.std(sig2) + 1e-10)
        
        # Cross-correlation
        correlation = signal.correlate(sig1, sig2, mode='full', method='fft')
        lags = signal.correlation_lags(len(sig1), len(sig2), mode='full')
        
        # Find peak
        peak_idx = np.argmax(np.abs(correlation))
        time_delay = lags[peak_idx] / sample_rate
        peak_value = np.abs(correlation[peak_idx])
        
        return time_delay, correlation, lags, peak_value
    
    def calculate_tdoa_pairs(self):
        """Calculate TDOA for all station pairs"""
        station_ids = list(self.station_data.keys())
        time_differences = {}
        correlation_quality = {}
        
        for i in range(len(station_ids)):
            for j in range(i + 1, len(station_ids)):
                station1 = station_ids[i]
                station2 = station_ids[j]
                
                data1 = self.station_data[station1]
                data2 = self.station_data[station2]
                
                breakpoint()
                # Check sample rates match
                if data1['sample_rate'] != data2['sample_rate']:
                    print(f"Warning: Sample rates don't match for {station1} and {station2}")
                    continue
                
                # Calculate correlation
                time_delay, corr, lags, peak_value = self.correlate_signals(
                    data1['samples'], 
                    data2['samples'], 
                    data1['sample_rate']
                )
                
                # Account for any timestamp differences
                timestamp_diff = data1['timestamp'] - data2['timestamp']
                adjusted_delay = time_delay + timestamp_diff
                
                time_differences[(station1, station2)] = adjusted_delay
                correlation_quality[(station1, station2)] = peak_value
                
                print(f"TDOA {station1}-{station2}: {adjusted_delay*1e6:.2f} μs (correlation peak: {peak_value:.3f})")
        
        return time_differences, correlation_quality
    
    def convert_lat_lon_to_meters(self, lat_lon_positions):
        """Convert lat/lon to local XY coordinates in meters"""
        # Use the center as reference
        center_lat = np.mean([pos[0] for pos in lat_lon_positions.values()])
        center_lon = np.mean([pos[1] for pos in lat_lon_positions.values()])
        
        meters_per_degree_lat = 111320.0
        meters_per_degree_lon = meters_per_degree_lat * np.cos(np.radians(center_lat))
        
        xy_positions = {}
        for station, pos in lat_lon_positions.items():
            x = (pos[1] - center_lon) * meters_per_degree_lon
            y = (pos[0] - center_lat) * meters_per_degree_lat
            xy_positions[station] = np.array([x, y])
            
        return xy_positions, (center_lat, center_lon)
    
    def tdoa_multilateration(self, station_positions, time_differences):
        """Calculate transmitter position using TDOA"""
        # Convert to XY coordinates
        xy_positions, center = self.convert_lat_lon_to_meters(station_positions)
        
        def objective(tx_pos):
            """Minimize the error in TDOA equations"""
            error = 0
            for (stat1, stat2), measured_tdoa in time_differences.items():
                if stat1 in xy_positions and stat2 in xy_positions:
                    dist1 = np.linalg.norm(tx_pos - xy_positions[stat1])
                    dist2 = np.linalg.norm(tx_pos - xy_positions[stat2])
                    predicted_tdoa = (dist1 - dist2) / self.c
                    error += (predicted_tdoa - measured_tdoa) ** 2
            return error
        
        # Initial guess (center of stations)
        initial_guess = np.mean(list(xy_positions.values()), axis=0)
        
        # Optimize
        result = minimize(objective, initial_guess, method='BFGS')
        
        # Convert back to lat/lon
        x, y = result.x
        lat = center[0] + y / 111320.0
        lon = center[1] + x / (111320.0 * np.cos(np.radians(center[0])))
        
        return np.array([lat, lon]), result.fun
    
    def plot_correlation(self, time_differences, correlation_quality):
        """Plot correlation results"""
        fig, axes = plt.subplots(len(time_differences), 1, figsize=(10, 4*len(time_differences)))
        if len(time_differences) == 1:
            axes = [axes]
        
        for idx, ((stat1, stat2), tdoa) in enumerate(time_differences.items()):
            data1 = self.station_data[stat1]
            data2 = self.station_data[stat2]
            
            # Recalculate correlation for plotting
            _, correlation, lags, _ = self.correlate_signals(
                data1['samples'][:10000],  # Limit samples for plotting
                data2['samples'][:10000], 
                data1['sample_rate']
            )
            
            time_lags = lags / data1['sample_rate'] * 1e6  # Convert to microseconds
            
            axes[idx].plot(time_lags, np.abs(correlation))
            axes[idx].axvline(x=tdoa*1e6, color='r', linestyle='--', 
                            label=f'Peak: {tdoa*1e6:.2f} μs')
            axes[idx].set_xlabel('Time Lag (μs)')
            axes[idx].set_ylabel('Correlation')
            axes[idx].set_title(f'Cross-correlation: {stat1} vs {stat2} (Quality: {correlation_quality[(stat1, stat2)]:.3f})')
            axes[idx].legend()
            axes[idx].grid(True)
            axes[idx].set_xlim(-100, 100)  # Limit view to ±100 μs
        
        plt.tight_layout()
        plt.savefig('tdoa_correlations.png', dpi=150)
        print("Saved correlation plots to tdoa_correlations.png")
    
    def create_map(self, estimated_position, error_estimate):
        """Create an interactive map with results"""
        # Center map on Omaha
        map_center = [41.2565, -96.0244]
        tdoa_map = folium.Map(location=map_center, zoom_start=11)
        
        # Add stations
        for station_id in self.station_data.keys():
            if station_id in self.station_positions:
                pos = self.station_positions[station_id]
                folium.Marker(
                    [pos[0], pos[1]],
                    popup=f"{station_id}<br>Lat: {pos[0]:.6f}<br>Lon: {pos[1]:.6f}",
                    icon=folium.Icon(color='blue', icon='wifi')
                ).add_to(tdoa_map)
        
        # Add estimated position
        folium.Marker(
            [estimated_position[0], estimated_position[1]],
            popup=f"Estimated Transmitter<br>Lat: {estimated_position[0]:.6f}<br>Lon: {estimated_position[1]:.6f}<br>Error metric: {error_estimate:.6f}",
            icon=folium.Icon(color='red', icon='star')
        ).add_to(tdoa_map)
        
        # Add actual WXL68 position
        actual_pos = [41.2619, -96.0819]
        folium.Marker(
            actual_pos,
            popup="WXL68 Actual Location<br>NOAA Weather Radio<br>162.400 MHz",
            icon=folium.Icon(color='green', icon='radio', prefix='fa')
        ).add_to(tdoa_map)
        
        # Calculate and display error
        distance_error = np.linalg.norm(
            (estimated_position - np.array(actual_pos)) * 
            np.array([111320, 111320 * np.cos(np.radians(actual_pos[0]))])
        )
        
        # Add error circle
        folium.Circle(
            location=[estimated_position[0], estimated_position[1]],
            radius=distance_error,
            color='red',
            fill=False,
            popup=f'Error: {distance_error:.1f} meters'
        ).add_to(tdoa_map)
        
        # Add lines between stations
        for station_id in self.station_data.keys():
            if station_id in self.station_positions:
                pos = self.station_positions[station_id]
                folium.PolyLine(
                    [[pos[0], pos[1]], [estimated_position[0], estimated_position[1]]],
                    color='gray',
                    weight=1,
                    opacity=0.5
                ).add_to(tdoa_map)
        
        tdoa_map.save('tdoa_results_map.html')
        print(f"Saved interactive map to tdoa_results_map.html")
        print(f"Position error: {distance_error:.1f} meters")
        
        return distance_error
    
    def plot_results(self, estimated_position, actual_position=[41.2619, -96.0819]):
        """Create a static plot of results"""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot stations
        for station_id in self.station_data.keys():
            if station_id in self.station_positions:
                pos = self.station_positions[station_id]
                ax.scatter(pos[1], pos[0], s=100, c='blue', marker='^', zorder=5)
                ax.text(pos[1], pos[0], f'\n{station_id}', ha='center', fontsize=8)
        
        # Plot estimated position
        ax.scatter(estimated_position[1], estimated_position[0], 
                  s=200, c='red', marker='*', label='Estimated TX', zorder=5)
        
        # Plot actual position
        ax.scatter(actual_position[1], actual_position[0], 
                  s=200, c='green', marker='o', label='Actual TX (WXL68)', zorder=5)
        
        # Draw lines
        for station_id in self.station_data.keys():
            if station_id in self.station_positions:
                pos = self.station_positions[station_id]
                ax.plot([pos[1], estimated_position[1]], 
                       [pos[0], estimated_position[0]], 
                       'gray', alpha=0.3, linestyle='--')
        
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title('TDOA Direction Finding Results - WXL68 162.400 MHz')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Set aspect ratio for map
        ax.set_aspect(1/np.cos(np.radians(41.25)))
        
        plt.tight_layout()
        plt.savefig('tdoa_results_plot.png', dpi=150)
        
        print("Saved static plot to tdoa_results_plot.png")
    
    def run_analysis(self, data_directory='.'):
        """Run complete TDOA analysis"""
        print("="*50)
        print("TDOA Processing for NOAA Weather Radio WXL68")
        print("="*50)
        
        # Load data
        print("\n1. Loading sample files...")
        complete_set = self.load_all_samples(data_directory)
        
        if len(self.station_data.keys()) < 2:
            print("Error: Need at least 2 stations for TDOA")
            return
        
        # Calculate TDOA
        print("\n2. Calculating time differences...")
        time_differences, correlation_quality = self.calculate_tdoa_pairs()
        
        if not time_differences:
            print("Error: Could not calculate any time differences")
            return
        
        # Plot correlations
        print("\n3. Plotting correlations...")
        self.plot_correlation(time_differences, correlation_quality)
        
        # Only attempt multilateration with 3+ stations
        if len(self.station_data) >= 3 and complete_set:
            print("\n4. Performing multilateration...")
            # Filter to only use station positions we have
            available_positions = {
                station: pos for station, pos in self.station_positions.items() 
                if station in self.station_data
            }
            estimated_position, error = self.tdoa_multilateration(
                available_positions, time_differences
            )
            
            print(f"\nEstimated transmitter position:")
            print(f"  Latitude:  {estimated_position[0]:.6f}")
            print(f"  Longitude: {estimated_position[1]:.6f}")
            print(f"  Optimization error: {error:.9f}")
            
            # Create visualizations
            print("\n5. Creating visualizations...")
            distance_error = self.create_map(estimated_position, error)
            self.plot_results(estimated_position)
            
            print("\n" + "="*50)
            print("Analysis complete!")
            print(f"Results saved to:")
            print(f"  - tdoa_correlations.png")
            print(f"  - tdoa_results_map.html")
            print(f"  - tdoa_results_plot.png")
            print(f"\nPosition error: {distance_error:.1f} meters")
            
        else:
            print("\nInsufficient stations for multilateration")
            print("Need at least 3 synchronized stations")
            print(f"Currently have: {list(self.station_data.keys())}")

if __name__ == "__main__":
    import sys
    
    # Get directory from command line or use current directory
    data_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    
    processor = TDOAProcessor()
    processor.run_analysis(data_dir)

