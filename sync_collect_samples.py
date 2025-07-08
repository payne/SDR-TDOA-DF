#!/usr/bin/env python3
import numpy as np
from rtlsdr import RtlSdr
import time
import socket
import json
from datetime import datetime
from scipy import signal
import threading

SYNC_FREQ=506.31e6

class TDOACollector:
    def __init__(self, station_id, center_freq=162.4e6, sample_rate=2.048e6, ref_freq=SYNC_FREQ):
        self.station_id = station_id
        self.center_freq = center_freq
        self.sample_rate = sample_rate
        self.ref_freq = ref_freq
        self.sdr = RtlSdr()
        self.sdr.sample_rate = sample_rate
        self.sdr.gain = 'auto'

        # Reference signal parameters
        self.ref_lock = False
        self.ref_phase = 0
        self.ref_timestamp = None

    def acquire_reference_lock(self, timeout=10.0):
        """Acquire lock on reference frequency for synchronization"""
        print(f"Acquiring reference lock on {self.ref_freq/1e6:.3f} MHz...")

        # Temporarily tune to reference frequency
        original_freq = self.center_freq
        self.sdr.center_freq = self.ref_freq

        start_time = time.time()
        samples_per_read = int(self.sample_rate * 0.1)  # 100ms chunks

        while (time.time() - start_time) < timeout:
            # Read samples
            samples = self.sdr.read_samples(samples_per_read)

            # Compute FFT to find reference signal
            fft_data = np.fft.fftshift(np.fft.fft(samples))
            freqs = np.fft.fftshift(np.fft.fftfreq(len(samples), 1/self.sample_rate))

            # Find peak near DC (reference should be strong)
            power = np.abs(fft_data)**2
            peak_idx = np.argmax(power)
            peak_freq = freqs[peak_idx]
            peak_power = power[peak_idx]

            # Check if we have a strong signal
            avg_power = np.mean(power)
            snr = 10 * np.log10(peak_power / avg_power)

            if snr > 20:  # 20 dB SNR threshold
                # Extract phase of reference signal
                ref_bin = peak_idx
                self.ref_phase = np.angle(fft_data[ref_bin])
                self.ref_timestamp = time.time()
                self.ref_lock = True
                print(f"Reference locked! SNR: {snr:.1f} dB, Offset: {peak_freq:.1f} Hz")
                break

        # Return to original frequency
        self.sdr.center_freq = original_freq

        if not self.ref_lock:
            print("Failed to acquire reference lock")

        return self.ref_lock

    def synchronize_to_reference(self):
        """Synchronize collection to reference signal phase"""
        if not self.ref_lock:
            print("No reference lock - using system time")
            # Fall back to system time sync
            time.sleep(1.0 - (time.time() % 1.0))
            return

        # Calculate when next reference cycle starts
        # Assuming reference is a stable carrier, we sync to its zero-crossing
        ref_period = 1.0 / (self.ref_freq % 1e6)  # Period of the reference tone

        # Wait for specific phase alignment
        current_time = time.time()
        elapsed = current_time - self.ref_timestamp

        # Calculate number of cycles elapsed
        cycles_elapsed = elapsed / ref_period
        phase_offset = (cycles_elapsed % 1.0) * 2 * np.pi

        # Wait until we're at zero phase
        wait_time = ref_period * (1.0 - (phase_offset / (2 * np.pi)))
        if wait_time < 0.001:  # Too close, wait for next cycle
            wait_time += ref_period

        time.sleep(wait_time)

    def collect_samples_with_reference(self, duration=1.0):
        """Collect samples with reference signal for time alignment"""
        # Simultaneously collect from both target and reference frequencies
        # Using frequency hopping approach

        num_samples = int(self.sdr.sample_rate * duration)
        hop_duration = 0.01  # 10ms per hop
        samples_per_hop = int(self.sdr.sample_rate * hop_duration)

        target_samples = []
        ref_samples = []
        timestamps = []

        start_time = time.time()

        while len(target_samples) < num_samples:
            # Collect target frequency
            self.sdr.center_freq = self.center_freq
            time.sleep(0.001)  # Settling time
            t1 = time.time()
            samples = self.sdr.read_samples(samples_per_hop)
            target_samples.extend(samples)

            # Collect reference frequency
            self.sdr.center_freq = self.ref_freq
            time.sleep(0.001)  # Settling time
            t2 = time.time()
            samples = self.sdr.read_samples(samples_per_hop)
            ref_samples.extend(samples)

            timestamps.append((t1, t2))

        # Trim to exact length
        target_samples = np.array(target_samples[:num_samples])
        ref_samples = np.array(ref_samples[:num_samples])

        # Extract reference phase for fine time alignment
        ref_fft = np.fft.fft(ref_samples[:1024])
        ref_phase = np.angle(ref_fft[np.argmax(np.abs(ref_fft))])

        return {
            'station_id': self.station_id,
            'timestamp': start_time,
            'samples': target_samples,
            'ref_samples': ref_samples,
            'ref_phase': ref_phase,
            'sample_rate': self.sdr.sample_rate,
            'center_freq': self.center_freq,
            'ref_freq': self.ref_freq
        }

    def collect_samples(self, duration=1.0, use_reference=True):
        """Main collection method"""
        if use_reference and self.ref_lock:
            return self.collect_samples_with_reference(duration)
        else:
            # Standard collection without reference
            self.sdr.center_freq = self.center_freq
            num_samples = int(self.sdr.sample_rate * duration)
            timestamp = time.time()
            samples = self.sdr.read_samples(num_samples)

            return {
                'station_id': self.station_id,
                'timestamp': timestamp,
                'samples': samples,
                'sample_rate': self.sdr.sample_rate,
                'center_freq': self.sdr.center_freq,
                'ref_freq': None
            }

    def save_samples(self, data, filename):
        """Save samples to file with metadata"""
        save_dict = {
            'samples': data['samples'],
            'timestamp': data['timestamp'],
            'station_id': data['station_id'],
            'sample_rate': data['sample_rate'],
            'center_freq': data['center_freq'],
            'ref_freq': data.get('ref_freq', None)
        }

        # Add reference data if available
        if 'ref_samples' in data:
            save_dict['ref_samples'] = data['ref_samples']
            save_dict['ref_phase'] = data['ref_phase']

        np.savez_compressed(filename, **save_dict)

def main():
    import sys
    station_id = sys.argv[1] if len(sys.argv) > 1 else "station1"

    # Initialize collector with reference frequency
    # 174.309 MHz could be a local FM station or other stable signal
    collector = TDOACollector(station_id, ref_freq=SYNC_FREQ)

    print(f"Station {station_id} TDOA Collector")
    print(f"Target: 162.400 MHz (NOAA WXL68)")
    print(f"Reference: 174.309 MHz")

    # Try to acquire reference lock
    if collector.acquire_reference_lock():
        print("Using reference-based synchronization")

        # Wait for synchronization point
        print("Waiting for sync point...")
        collector.synchronize_to_reference()
    else:
        print("Using time-based synchronization")
        # Fall back to time sync
        time.sleep(1.0 - (time.time() % 1.0))

    # Collect samples
    print("Collecting samples...")
    data = collector.collect_samples(duration=2.0)

    # Save data
    filename = f"nice_data/tdoa_{station_id}_{int(data['timestamp'])}.npz"
    collector.save_samples(data, filename)
    print(f"Saved to {filename}")

    # Print phase info if using reference
    if 'ref_phase' in data:
        print(f"Reference phase: {data['ref_phase']:.3f} radians")

if __name__ == "__main__":
    main()
