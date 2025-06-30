#!/usr/bin/env python3
import numpy as np
from rtlsdr import RtlSdr
import time
import socket
import json
from datetime import datetime

class TDOACollector:
    def __init__(self, station_id, center_freq=162.4e6, sample_rate=2.048e6):
        self.station_id = station_id
        self.sdr = RtlSdr()
        self.sdr.center_freq = center_freq
        self.sdr.sample_rate = sample_rate
        self.sdr.gain = 'auto'
        
    def collect_samples(self, duration=1.0):
        """Collect samples for specified duration"""
        num_samples = int(self.sdr.sample_rate * duration)
        timestamp = time.time()
        samples = self.sdr.read_samples(num_samples)
        
        return {
            'station_id': self.station_id,
            'timestamp': timestamp,
            'samples': samples,
            'sample_rate': self.sdr.sample_rate,
            'center_freq': self.sdr.center_freq
        }
    
    def save_samples(self, data, filename):
        """Save samples to file with metadata"""
        np.savez_compressed(filename,
                           samples=data['samples'],
                           timestamp=data['timestamp'],
                           station_id=data['station_id'],
                           sample_rate=data['sample_rate'],
                           center_freq=data['center_freq'])

if __name__ == "__main__":
    import sys
    station_id = sys.argv[1] if len(sys.argv) > 1 else "station1"
    
    collector = TDOACollector(station_id)
    print(f"Collecting samples at station {station_id}...")
    
    # Synchronize to next whole second
    time.sleep(1.0 - (time.time() % 1.0))
    
    data = collector.collect_samples(duration=2.0)
    filename = f"tdoa_{station_id}_{int(data['timestamp'])}.npz"
    collector.save_samples(data, filename)
    print(f"Saved to {filename}")

