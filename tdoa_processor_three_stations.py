#!/usr/bin/env python3
"""
TDOA Processor for Three Station Data Collection
Processes synchronized data files from three RTL-SDR stations to locate NOAA transmitter
"""

import pdb
import numpy as np
from scipy import signal
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import folium
import glob
import os
from datetime import datetime
import json
import re

def get_station_id_from(filepath):
    match = re.search(r'tdoa_station(\d+)', filepath)
    if match:
        station_num = int(match.group(1))
        return f"station{station_num}"

class ThreeStationTDOA:
    def __init__(self, data_directory='nice_data'):
        self.c = 299792458  # Speed of light in m/s
        self.data_dir = data_directory

        # Define your actual station positions here (GPS coordinates)
        # UPDATE THESE WITH YOUR ACTUAL COORDINATES!
        self.station_positions = {
            'station1': {
                'name': 'West Omaha',
                'lat': 41.2565,
                'lon': -96.1969,
                'color': 'blue'
            },
            'station2': {
                'name': 'Bellevue',
                'lat': 41.1543,
                'lon': -95.9145,
                'color': 'red'
            },
            'station3': {
                'name': 'North Omaha',
                'lat': 41.3148,
                'lon': -95.9378,
                'color': 'green'
            }
        }

        # WXL68 actual position for comparison
        self.actual_tx = {
            'name': 'WXL68 NOAA',
            'lat': 41.2619,
            'lon': -96.0819,
            'freq': '162.400 MHz'
        }

        self.data_files = {}
        self.tdoa_results = {}


    def find_synchronized_files(self):
        """Find and group synchronized data files"""
        print(f"\nSearching for data files in '{self.data_dir}'...")

        npz_files = glob.glob(os.path.join(self.data_dir, 'tdoa_*.npz'))

        # breakpoint()

        if not npz_files:
            raise ValueError(f"No .npz files found in {self.data_dir}")

        # Group files by timestamp
        file_groups = {}

        for filepath in npz_files:
            try:
                data = np.load(filepath)
                timestamp = float(data['timestamp'])
                station_id = get_station_id_from(filepath)

                # Find if timestamp is within 1 second of any existing group
                found = False
                for existing_key in file_groups.keys():
                    if abs(timestamp - existing_key) <= 1:
                        time_key = existing_key
                        found = True
                        break

                if not found:
                    # Start a new group with this timestamp as key
                    time_key = timestamp

                if time_key not in file_groups:
                    file_groups[time_key] = {}

                print(f"{filepath} time_key={time_key} station_id={station_id}")
                file_groups[time_key][station_id] = filepath

            except Exception as e:
                print(f"Error reading {filepath}: {e}")

        # Find the best synchronized set (closest to 3 stations)
        best_group = None
        best_count = 0

        for time_key, stations in file_groups.items():
            if len(stations) > best_count:
                best_count = len(stations)
                best_group = time_key

        if best_group is None:
            raise ValueError("No valid data files found")

        self.data_files = file_groups[best_group]

        print(f"\nFound synchronized data set from {datetime.fromtimestamp(best_group)}:")
        for station, filepath in self.data_files.items():
            print(f"  {station}: {os.path.basename(filepath)}")

        if len(self.data_files) < 3:
            print(f"\nWARNING: Only {len(self.data_files)} stations found. Need 3 for accurate TDOA.")

        return len(self.data_files)

    def load_station_data(self):
        """Load data from all station files"""
        self.station_data = {}

        for station_id, filepath in self.data_files.items():
            data = np.load(filepath)

            self.station_data[station_id] = {
                'samples': data['samples'],
                'timestamp': float(data['timestamp']),
                'sample_rate': float(data['sample_rate']),
                'center_freq': float(data['center_freq'])
            }

            print(f"\n{station_id}:")
            print(f"  Samples: {len(data['samples'])}")
            print(f"  Sample rate: {data['sample_rate']/1e6:.3f} MHz")
            print(f"  Center freq: {data['center_freq']/1e6:.3f} MHz")

    def calculate_correlation(self, sig1, sig2, sample_rate):
        """Calculate cross-correlation between two signals"""
        # Use a reasonable correlation length (100ms of data)
        corr_length = int(0.1 * sample_rate)
        sig1_segment = sig1[:corr_length]
        sig2_segment = sig2[:corr_length]

        # Remove DC and normalize
        sig1_segment = sig1_segment - np.mean(sig1_segment)
        sig2_segment = sig2_segment - np.mean(sig2_segment)

        # Normalize power
        sig1_segment = sig1_segment / (np.std(sig1_segment) + 1e-10)
        sig2_segment = sig2_segment / (np.std(sig2_segment) + 1e-10)

        # Cross-correlation using FFT method for speed
        correlation = signal.correlate(sig1_segment, sig2_segment, mode='full', method='fft')
        lags = signal.correlation_lags(len(sig1_segment), len(sig2_segment), mode='full')

        # Find peak
        peak_idx = np.argmax(np.abs(correlation))
        peak_lag = lags[peak_idx]
        peak_value = np.abs(correlation[peak_idx])

        # Convert lag to time
        time_delay = peak_lag / sample_rate

        return time_delay, correlation, lags, peak_value

    def compute_all_tdoa(self):
        """Compute TDOA between all station pairs"""
        stations = list(self.station_data.keys())

        print("\n" + "="*50)
        print("Computing Time Differences of Arrival (TDOA)")
        print("="*50)

        self.tdoa_pairs = {}
        self.correlation_quality = {}

        # Calculate TDOA for each pair
        pair_count = 0
        for i in range(len(stations)):
            for j in range(i + 1, len(stations)):
                stat1, stat2 = stations[i], stations[j]

                data1 = self.station_data[stat1]
                data2 = self.station_data[stat2]

                # Calculate correlation
                time_delay, corr, lags, peak = self.calculate_correlation(
                    data1['samples'],
                    data2['samples'],
                    data1['sample_rate']
                )

                # Account for any GPS timestamp differences
                gps_diff = data1['timestamp'] - data2['timestamp']
                adjusted_delay = time_delay + gps_diff

                # Store results
                pair_key = f"{stat1}-{stat2}"
                self.tdoa_pairs[pair_key] = {
                    'stations': (stat1, stat2),
                    'tdoa': adjusted_delay,
                    'correlation': corr,
                    'lags': lags,
                    'peak_value': peak,
                    'sample_rate': data1['sample_rate']
                }

                self.correlation_quality[pair_key] = peak

                # Convert to distance difference
                distance_diff = adjusted_delay * self.c

                print(f"\n{pair_key}:")
                print(f"  Time delay: {adjusted_delay*1e6:+.2f} μs")
                print(f"  Distance difference: {distance_diff:+.1f} m")
                print(f"  Correlation peak: {peak:.3f}")

                pair_count += 1

        print(f"\nProcessed {pair_count} station pairs")

    def plot_correlations(self):
        """Plot correlation functions for all pairs"""
        n_pairs = len(self.tdoa_pairs)
        fig, axes = plt.subplots(n_pairs, 1, figsize=(12, 4*n_pairs))

        if n_pairs == 1:
            axes = [axes]

        for idx, (pair_key, data) in enumerate(self.tdoa_pairs.items()):
            ax = axes[idx]

            # Convert lags to microseconds
            time_lags = data['lags'] / data['sample_rate'] * 1e6

            # Plot correlation
            ax.plot(time_lags, np.abs(data['correlation']), 'b-', alpha=0.7)

            # Mark peak
            peak_time = data['tdoa'] * 1e6
            ax.axvline(x=peak_time, color='r', linestyle='--', linewidth=2,
                      label=f'Peak: {peak_time:.2f} μs')

            # Formatting
            ax.set_xlabel('Time Lag (μs)')
            ax.set_ylabel('Correlation')
            ax.set_title(f'Cross-Correlation: {pair_key} (Quality: {data["peak_value"]:.3f})')
            ax.grid(True, alpha=0.3)
            ax.legend()

            # Limit x-axis to ±200 microseconds
            ax.set_xlim(-200, 200)

        plt.tight_layout()
        output_file = os.path.join(self.data_dir, 'correlation_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"\nSaved correlation plots to: {output_file}")
        plt.close()

    def multilateration(self):
        """Perform TDOA multilateration to find transmitter position"""
        print("\n" + "="*50)
        print("Performing Multilateration")
        print("="*50)

        # Convert lat/lon to local XY coordinates (meters)
        def lat_lon_to_xy(lat, lon, ref_lat, ref_lon):
            meters_per_degree_lat = 111320.0
            meters_per_degree_lon = meters_per_degree_lat * np.cos(np.radians(ref_lat))

            x = (lon - ref_lon) * meters_per_degree_lon
            y = (lat - ref_lat) * meters_per_degree_lat
            return np.array([x, y])

        # Use center of stations as reference
        ref_lat = np.mean([pos['lat'] for pos in self.station_positions.values()])
        ref_lon = np.mean([pos['lon'] for pos in self.station_positions.values()])

        # Convert station positions to XY
        station_xy = {}
        for stat_id, pos in self.station_positions.items():
            if stat_id in self.station_data:
                station_xy[stat_id] = lat_lon_to_xy(pos['lat'], pos['lon'], ref_lat, ref_lon)

        # Objective function for optimization
        def tdoa_objective(tx_xy):
            error = 0
            for pair_key, data in self.tdoa_pairs.items():
                stat1, stat2 = data['stations']

                if stat1 in station_xy and stat2 in station_xy:
                    # Calculate distances
                    dist1 = np.linalg.norm(tx_xy - station_xy[stat1])
                    dist2 = np.linalg.norm(tx_xy - station_xy[stat2])

                    # Predicted TDOA
                    predicted_tdoa = (dist1 - dist2) / self.c

                    # Squared error
                    error += (predicted_tdoa - data['tdoa']) ** 2

            return error

        # Initial guess: centroid of stations
        initial_xy = np.mean(list(station_xy.values()), axis=0)

        # Optimize
        result = minimize(tdoa_objective, initial_xy, method='Nelder-Mead',
                         options={'maxiter': 10000})

        # Convert back to lat/lon
        est_x, est_y = result.x
        est_lat = ref_lat + est_y / 111320.0
        est_lon = ref_lon + est_x / (111320.0 * np.cos(np.radians(ref_lat)))

        self.estimated_position = {
            'lat': est_lat,
            'lon': est_lon,
            'optimization_error': result.fun,
            'success': result.success
        }

        # Calculate error from actual position
        actual_xy = lat_lon_to_xy(self.actual_tx['lat'], self.actual_tx['lon'], ref_lat, ref_lon)
        est_xy = np.array([est_x, est_y])
        position_error = np.linalg.norm(actual_xy - est_xy)

        self.estimated_position['error_meters'] = position_error

        print(f"\nEstimated transmitter position:")
        print(f"  Latitude:  {est_lat:.6f}°")
        print(f"  Longitude: {est_lon:.6f}°")
        print(f"\nActual WXL68 position:")
        print(f"  Latitude:  {self.actual_tx['lat']:.6f}°")
        print(f"  Longitude: {self.actual_tx['lon']:.6f}°")
        print(f"\nPosition error: {position_error:.1f} meters")
        print(f"Optimization successful: {result.success}")

    def create_map(self):
        """Create interactive Folium map"""
        # Center map on Omaha area
        map_center = [41.2565, -96.0244]
        tdoa_map = folium.Map(location=map_center, zoom_start=11)

        # Add station markers
        for stat_id in self.station_data.keys():
            if stat_id in self.station_positions:
                pos = self.station_positions[stat_id]
                folium.Marker(
                    location=[pos['lat'], pos['lon']],
                    popup=f"<b>{stat_id}</b><br>{pos['name']}<br>Lat: {pos['lat']:.6f}<br>Lon: {pos['lon']:.6f}",
                    icon=folium.Icon(color=pos['color'], icon='wifi', prefix='fa')
                ).add_to(tdoa_map)

        # Add estimated position
        folium.Marker(
            location=[self.estimated_position['lat'], self.estimated_position['lon']],
            popup=f"<b>Estimated Position</b><br>Lat: {self.estimated_position['lat']:.6f}<br>Lon: {self.estimated_position['lon']:.6f}<br>Error: {self.estimated_position['error_meters']:.1f}m",
            icon=folium.Icon(color='red', icon='star', prefix='fa')
        ).add_to(tdoa_map)

        # Add actual transmitter position
        folium.Marker(
            location=[self.actual_tx['lat'], self.actual_tx['lon']],
            popup=f"<b>{self.actual_tx['name']}</b><br>{self.actual_tx['freq']}<br>Lat: {self.actual_tx['lat']:.6f}<br>Lon: {self.actual_tx['lon']:.6f}",
            icon=folium.Icon(color='green', icon='broadcast-tower', prefix='fa')
        ).add_to(tdoa_map)

        # Add error circle
        folium.Circle(
            location=[self.estimated_position['lat'], self.estimated_position['lon']],
            radius=self.estimated_position['error_meters'],
            color='red',
            fill=True,
            fillColor='red',
            fillOpacity=0.1,
            popup=f"Error radius: {self.estimated_position['error_meters']:.1f} meters"
        ).add_to(tdoa_map)

        # Add TDOA hyperbolas (simplified - showing lines for now)
        for stat_id in self.station_data.keys():
            if stat_id in self.station_positions:
                pos = self.station_positions[stat_id]
                folium.PolyLine(
                    locations=[
                        [pos['lat'], pos['lon']],
                        [self.estimated_position['lat'], self.estimated_position['lon']]
                    ],
                    color='gray',
                    weight=1,
                    opacity=0.5,
                    dash_array='5'
                ).add_to(tdoa_map)

        # Save map
        output_file = os.path.join(self.data_dir, 'tdoa_interactive_map.html')
        tdoa_map.save(output_file)
        print(f"\nSaved interactive map to: {output_file}")

    def create_static_plot(self):
        """Create static visualization plot"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

        # Left plot: Geographic view
        ax1.set_title('TDOA Direction Finding Results\nGeographic View', fontsize=14, fontweight='bold')

        # Plot stations
        for stat_id in self.station_data.keys():
            if stat_id in self.station_positions:
                pos = self.station_positions[stat_id]
                ax1.scatter(pos['lon'], pos['lat'], s=200, c=pos['color'],
                          marker='^', edgecolor='black', linewidth=2, zorder=5,
                          label=f"{stat_id} ({pos['name']})")
                ax1.text(pos['lon'], pos['lat']-0.01, stat_id, ha='center', fontsize=8)

        # Plot estimated position
        ax1.scatter(self.estimated_position['lon'], self.estimated_position['lat'],
                   s=300, c='red', marker='*', edgecolor='black', linewidth=2,
                   zorder=6, label='Estimated Position')

        # Plot actual position
        ax1.scatter(self.actual_tx['lon'], self.actual_tx['lat'],
                   s=300, c='green', marker='o', edgecolor='black', linewidth=2,
                   zorder=6, label=f"Actual {self.actual_tx['name']}")

        # Draw connections
        for stat_id in self.station_data.keys():
            if stat_id in self.station_positions:
                pos = self.station_positions[stat_id]
                ax1.plot([pos['lon'], self.estimated_position['lon']],
                        [pos['lat'], self.estimated_position['lat']],
                        'gray', alpha=0.3, linestyle='--', linewidth=1)

        # Error line
        ax1.plot([self.estimated_position['lon'], self.actual_tx['lon']],
                [self.estimated_position['lat'], self.actual_tx['lat']],
                'red', linewidth=2, label=f"Error: {self.estimated_position['error_meters']:.1f}m")

        ax1.set_xlabel('Longitude')
        ax1.set_ylabel('Latitude')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='best')
        ax1.set_aspect(1/np.cos(np.radians(41.25)))

        # Right plot: TDOA measurements
        ax2.set_title('TDOA Measurements\nTime Differences', fontsize=14, fontweight='bold')

        pairs = list(self.tdoa_pairs.keys())
        tdoa_values = [data['tdoa'] * 1e6 for data in self.tdoa_pairs.values()]  # Convert to μs
        quality_values = [data['peak_value'] for data in self.tdoa_pairs.values()]

        # Create bar chart
        x = np.arange(len(pairs))
        bars = ax2.bar(x, tdoa_values, color=['blue', 'green', 'red'][:len(pairs)])

        # Add quality scores on bars
        for i, (bar, quality) in enumerate(zip(bars, quality_values)):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{quality:.2f}', ha='center', va='bottom' if height > 0 else 'top')

        ax2.set_xlabel('Station Pairs')
        ax2.set_ylabel('Time Difference (μs)')
        ax2.set_xticks(x)
        ax2.set_xticklabels(pairs, rotation=45)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.axhline(y=0, color='black', linewidth=0.5)

        # Add info text
        info_text = (
            f"Sample Rate: {list(self.station_data.values())[0]['sample_rate']/1e6:.3f} MHz\n"
            f"Center Freq: {list(self.station_data.values())[0]['center_freq']/1e6:.3f} MHz\n"
            f"Position Error: {self.estimated_position['error_meters']:.1f} meters"
        )
        ax2.text(0.02, 0.98, info_text, transform=ax2.transAxes,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                verticalalignment='top', fontsize=10)

        plt.tight_layout()

        # Save plot
        output_file = os.path.join(self.data_dir, 'tdoa_analysis_results.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved analysis plot to: {output_file}")
        plt.close()

    def save_results(self):
        """Save numerical results to JSON file"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'station_positions': self.station_positions,
            'actual_transmitter': self.actual_tx,
            'estimated_position': self.estimated_position,
            'tdoa_measurements': {
                pair: {
                    'tdoa_seconds': data['tdoa'],
                    'tdoa_microseconds': data['tdoa'] * 1e6,
                    'distance_difference_meters': data['tdoa'] * self.c,
                    'correlation_quality': data['peak_value']
                }
                for pair, data in self.tdoa_pairs.items()
            },
            'files_processed': {
                station: os.path.basename(filepath)
                for station, filepath in self.data_files.items()
            }
        }

        output_file = os.path.join(self.data_dir, 'tdoa_results.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"Saved numerical results to: {output_file}")

    def run_analysis(self):
        """Run complete TDOA analysis pipeline"""
        print("\n" + "="*60)
        print("THREE STATION TDOA PROCESSOR")
        print("Target: NOAA Weather Radio WXL68 - 162.400 MHz")
        print("="*60)

        try:
            # Step 1: Find data files
            n_stations = self.find_synchronized_files()

            if n_stations < 2:
                print("\nERROR: Need at least 2 stations for TDOA!")
                return

            # Step 2: Load data
            print("\n" + "-"*50)
            print("Loading station data...")
            self.load_station_data()

            # Step 3: Compute TDOA
            self.compute_all_tdoa()

            # Step 4: Create correlation plots
            print("\n" + "-"*50)
            print("Creating correlation analysis plots...")
            self.plot_correlations()

            # Step 5: Multilateration (if we have 3 stations)
            if n_stations >= 3:
                self.multilateration()

                # Step 6: Create visualizations
                print("\n" + "-"*50)
                print("Creating visualizations...")
                self.create_map()
                self.create_static_plot()

                # Step 7: Save results
                print("\n" + "-"*50)
                print("Saving results...")
                self.save_results()
            else:
                print("\nWARNING: Need 3 stations for position estimation!")
                print("Can only compute TDOA between 2 stations.")

            print("\n" + "="*60)
            print("ANALYSIS COMPLETE!")
            print("="*60)
            print(f"\nOutput files in '{self.data_dir}':")
            print("  - correlation_analysis.png    : Cross-correlation plots")
            if n_stations >= 3:
                print("  - tdoa_interactive_map.html   : Interactive map (open in browser)")
                print("  - tdoa_analysis_results.png   : Static analysis plots")
                print("  - tdoa_results.json          : Numerical results")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()


def main():
    import sys

    # Get data directory from command line or use default
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    else:
        data_dir = 'nice_data'

    # Create processor and run analysis
    processor = ThreeStationTDOA(data_directory=data_dir)
    processor.run_analysis()


if __name__ == "__main__":
    main()
