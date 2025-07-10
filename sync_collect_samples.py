#!/usr/bin/env python3
import numpy as np
import time
import socket
import json
from datetime import datetime
from scipy import signal
import threading
from sdr_device_manager import SDRDeviceManager

import SoapySDR
from SoapySDR import *

SYNC_FREQ=506.31e6

class TDOACollector:
    def __init__(self, station_id, center_freq=162.4e6, sample_rate=2.048e6,
                 ref_freq=SYNC_FREQ, device_type="auto", device_index=0):
        self.station_id = station_id
        self.center_freq = center_freq
        self.sample_rate = sample_rate
        self.ref_freq = ref_freq

        # Initialize SDR device manager
        self.sdr_manager = SDRDeviceManager(device_type, device_index)

        # Initialize device
        if not self.sdr_manager.initialize_device():
            raise Exception("Failed to initialize SDR device")

        # Configure device
        self.sdr_manager.configure_device(sample_rate, center_freq, gain="auto")
        self.sdr_manager.create_rx_stream()

        # Reference signal parameters (unchanged)
        self.ref_lock = False
        self.ref_phase = 0
        self.ref_timestamp = None

    def read_samples(self, num_samples: int) -> np.ndarray:
        """Read samples using SoapySDR"""
        return self.sdr_manager.read_samples(num_samples)

    def set_center_frequency(self, freq: float):
        """Set center frequency for frequency hopping"""
        self.sdr_manager.set_center_frequency(freq)

    @property
    def sample_rate_prop(self):
        """Get current sample rate from device"""
        return self.sdr_manager.get_sample_rate()

    def cleanup(self):
        """Clean up device resources"""
        self.sdr_manager.cleanup()

    def acquire_reference_lock(self, timeout=10.0):
        """Acquire lock on reference frequency for synchronization"""
        print(f"Acquiring reference lock on {self.ref_freq/1e6:.3f} MHz...")

        # Temporarily tune to reference frequency
        original_freq = self.center_freq
        self.set_center_frequency(self.ref_freq)

        start_time = time.time()
        samples_per_read = int(self.sample_rate * 0.1)  # 100ms chunks

        while (time.time() - start_time) < timeout:
            # Read samples using new interface
            samples = self.read_samples(samples_per_read)

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
        self.set_center_frequency(original_freq)

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

        num_samples = int(self.sample_rate * duration)
        hop_duration = 0.01  # 10ms per hop
        samples_per_hop = int(self.sample_rate * hop_duration)

        target_samples = []
        ref_samples = []
        timestamps = []

        start_time = time.time()

        while len(target_samples) < num_samples:
            # Collect target frequency
            self.set_center_frequency(self.center_freq)
            t1 = time.time()
            samples = self.read_samples(samples_per_hop)
            target_samples.extend(samples)

            # Collect reference frequency
            self.set_center_frequency(self.ref_freq)
            t2 = time.time()
            samples = self.read_samples(samples_per_hop)
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
            'sample_rate': self.sample_rate,
            'center_freq': self.center_freq,
            'ref_freq': self.ref_freq
        }

    def collect_samples(self, duration=1.0, use_reference=True):
        """Main collection method"""
        if use_reference and self.ref_lock:
            return self.collect_samples_with_reference(duration)
        else:
            # Standard collection without reference
            self.set_center_frequency(self.center_freq)
            num_samples = int(self.sample_rate * duration)
            timestamp = time.time()
            samples = self.read_samples(num_samples)

            return {
                'station_id': self.station_id,
                'timestamp': timestamp,
                'samples': samples,
                'sample_rate': self.sample_rate,
                'center_freq': self.center_freq,
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
    import argparse

    parser = argparse.ArgumentParser(description='TDOA Sample Collector')
    parser.add_argument('station_id', nargs='?', default='station1',
                       help='Station identifier')
    parser.add_argument('--device', choices=['auto', 'rtlsdr', 'hackrf'],
                       default='auto', help='SDR device type')
    parser.add_argument('--device-index', type=int, default=0,
                       help='Device index (if multiple devices of same type)')
    parser.add_argument('--list-devices', action='store_true',
                       help='List available devices and exit')

    args = parser.parse_args()

    if args.list_devices:
        # List available devices
        manager = SDRDeviceManager()
        devices = manager.enumerate_devices()
        print("Available SoapySDR devices:")
        from sdr_device_manager import _get_device_attr
        for i, device in enumerate(devices):
            driver = _get_device_attr(device, 'driver', 'unknown')
            label = _get_device_attr(device, 'label', 'N/A')
            print(f"  {i}: {driver} - {label}")
        return

    # Initialize collector with specified device
    collector = TDOACollector(args.station_id, device_type=args.device,
                             device_index=args.device_index, ref_freq=SYNC_FREQ)

    print(f"Station {args.station_id} TDOA Collector")
    print(f"Target: 162.400 MHz (NOAA WXL68)")
    print(f"Reference: 506.31 MHz")
    print(f"Device: {collector.sdr_manager.device_info.get('driver', 'unknown')}")

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
    filename = f"nice_data/tdoa_{args.station_id}_{int(data['timestamp'])}.npz"
    collector.save_samples(data, filename)
    print(f"Saved to {filename}")

    # Print phase info if using reference
    if 'ref_phase' in data:
        print(f"Reference phase: {data['ref_phase']:.3f} radians")

    # Clean up
    collector.cleanup()

if __name__ == "__main__":
    main()
