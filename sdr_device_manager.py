#!/usr/bin/env python3
"""
SDR Device Manager - Unified interface for RTL-SDR, HackRF, and other SoapySDR devices
"""

import SoapySDR
import numpy as np
import time
from typing import Optional, Dict, List, Tuple

def _get_device_attr(device, key, default=''):
    """Helper function to get attribute from device object (handles both dict and SoapySDRKwargs)"""
    if hasattr(device, 'get'):
        return device.get(key, default)
    else:
        # SoapySDRKwargs access
        try:
            return device[key] if key in device else default
        except:
            return default

class SDRDeviceManager:
    """Unified SDR device manager supporting RTL-SDR, HackRF, and other SoapySDR devices"""

    def __init__(self, device_type: str = "auto", device_index: int = 0):
        self.device_type = device_type
        self.device_index = device_index
        self.sdr = None
        self.rx_stream = None
        self.device_info = {}

        # Device-specific parameters
        self.supported_sample_rates = []
        self.frequency_range = (0, 0)
        self.gain_range = (0, 0)
        self.supported_gains = []

    def enumerate_devices(self) -> List:
        """Enumerate all available SoapySDR devices"""
        devices = SoapySDR.Device.enumerate()
        return devices

    def auto_select_device(self) -> Optional:
        """Auto-select best available device"""
        devices = self.enumerate_devices()

        # Priority order: HackRF, RTL-SDR, others
        priority_drivers = ['hackrf', 'rtlsdr']

        for driver in priority_drivers:
            for device in devices:
                device_driver = _get_device_attr(device, 'driver', '')
                if device_driver.lower() == driver:
                    return device

        # Fallback to first available device
        return devices[0] if devices else None

    def initialize_device(self, device_args: Optional = None) -> bool:
        """Initialize the selected SDR device"""
        try:
            if device_args is None:
                if self.device_type == "auto":
                    selected_device = self.auto_select_device()
                    if not selected_device:
                        raise Exception("No SoapySDR devices found")
                    device_args = selected_device
                else:
                    # Manual device selection
                    devices = self.enumerate_devices()
                    matching_devices = []
                    for d in devices:
                        if _get_device_attr(d, 'driver', '').lower() == self.device_type.lower():
                            matching_devices.append(d)

                    if not matching_devices:
                        raise Exception(f"No {self.device_type} devices found")
                    device_args = matching_devices[self.device_index]

            # Create device
            self.sdr = SoapySDR.Device(device_args)

            # Store device info as dictionary for easy access
            self.device_info = {
                'driver': _get_device_attr(device_args, 'driver', 'unknown'),
                'label': _get_device_attr(device_args, 'label', 'N/A'),
                'serial': _get_device_attr(device_args, 'serial', 'N/A')
            }

            # Query device capabilities
            self._query_device_capabilities()

            print(f"Initialized {self.device_info['driver']} device")
            return True

        except Exception as e:
            print(f"Failed to initialize device: {e}")
            return False

    def _query_device_capabilities(self):
        """Query device-specific capabilities"""
        if not self.sdr:
            return

        # Get frequency range
        try:
            freq_range = self.sdr.getFrequencyRange(SoapySDR.SOAPY_SDR_RX, 0)
            if freq_range:
                self.frequency_range = (freq_range[0].minimum(), freq_range[0].maximum())
        except:
            self.frequency_range = (0, 6e9)  # Default wide range

        # Get sample rate range
        try:
            rate_range = self.sdr.getSampleRateRange(SoapySDR.SOAPY_SDR_RX, 0)
            if rate_range:
                self.sample_rate_range = (rate_range[0].minimum(), rate_range[0].maximum())
        except:
            self.sample_rate_range = (1e6, 20e6)  # Default range

        # Get gain range
        try:
            gain_range = self.sdr.getGainRange(SoapySDR.SOAPY_SDR_RX, 0)
            if gain_range:
                self.gain_range = (gain_range.minimum(), gain_range.maximum())
        except:
            self.gain_range = (0, 50)  # Default range

        # Get supported gains (for devices with discrete gain values)
        try:
            self.supported_gains = self.sdr.listGains(SoapySDR.SOAPY_SDR_RX, 0)
        except:
            self.supported_gains = []

    def configure_device(self, sample_rate: float, center_freq: float, gain: str = "auto"):
        """Configure device parameters with device-specific optimizations"""
        if not self.sdr:
            raise Exception("Device not initialized")

        # Set sample rate
        self.sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, sample_rate)
        actual_rate = self.sdr.getSampleRate(SoapySDR.SOAPY_SDR_RX, 0)
        print(f"Set sample rate: {actual_rate/1e6:.3f} MHz")

        # Set center frequency
        self.sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, center_freq)
        actual_freq = self.sdr.getFrequency(SoapySDR.SOAPY_SDR_RX, 0)
        print(f"Set center frequency: {actual_freq/1e6:.3f} MHz")

        # Set gain
        self._set_gain(gain)

        # Device-specific optimizations
        driver = self.device_info.get('driver', '').lower()
        if driver == 'rtlsdr':
            self._configure_rtlsdr()
        elif driver == 'hackrf':
            self._configure_hackrf()

    def _set_gain(self, gain):
        """Set gain with device-specific handling"""
        driver = self.device_info.get('driver', '').lower()

        if gain == "auto":
            if driver == 'rtlsdr':
                # RTL-SDR auto gain
                self.sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, True)
            elif driver == 'hackrf':
                # HackRF doesn't have auto gain, use a reasonable default
                self.sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, 32)  # Middle range for HackRF
                print(f"Set HackRF gain to 32 dB")
        else:
            # Manual gain
            self.sdr.setGainMode(SoapySDR.SOAPY_SDR_RX, 0, False)
            self.sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, float(gain))
            print(f"Set gain to {gain} dB")

    def _configure_rtlsdr(self):
        """RTL-SDR specific configuration"""
        # Enable bias tee if available
        try:
            self.sdr.writeSetting("biastee", "false")
        except:
            pass

    def _configure_hackrf(self):
        """HackRF specific configuration"""
        # Set reasonable defaults for HackRF
        try:
            # HackRF has separate LNA and VGA gain controls
            self.sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, "LNA", 16)  # LNA gain
            self.sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, "VGA", 16)  # VGA gain
            print(f"Set HackRF LNA gain to 16 dB, VGA gain to 16 dB")
        except Exception as e:
            print(f"Note: Could not set individual HackRF gains: {e}")

    def create_rx_stream(self, buffer_size: int = 1024):
        """Create RX stream for reading samples"""
        if not self.sdr:
            raise Exception("Device not initialized")

        self.rx_stream = self.sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
        self.sdr.activateStream(self.rx_stream)
        self.buffer_size = buffer_size

    def read_samples(self, num_samples: int) -> np.ndarray:
        """Read samples from the device"""
        if not self.rx_stream:
            raise Exception("RX stream not created")

        # Allocate buffer
        buffer = np.zeros(num_samples, dtype=np.complex64)

        # Read samples
        samples_read = 0
        while samples_read < num_samples:
            remaining = num_samples - samples_read
            chunk_size = min(remaining, self.buffer_size)

            chunk_buffer = np.zeros(chunk_size, dtype=np.complex64)
            sr = self.sdr.readStream(self.rx_stream, [chunk_buffer], chunk_size)

            if sr.ret > 0:
                buffer[samples_read:samples_read + sr.ret] = chunk_buffer[:sr.ret]
                samples_read += sr.ret
            else:
                time.sleep(0.001)  # Brief pause on error

        return buffer

    def set_center_frequency(self, freq: float):
        """Set center frequency (for frequency hopping)"""
        if not self.sdr:
            raise Exception("Device not initialized")

        self.sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, freq)

        # Add settling time for frequency changes
        driver = self.device_info.get('driver', '').lower()
        if driver == 'hackrf':
            time.sleep(0.002)  # HackRF needs more settling time
        else:
            time.sleep(0.001)  # RTL-SDR settling time

    def get_sample_rate(self) -> float:
        """Get current sample rate"""
        if not self.sdr:
            return 0
        return self.sdr.getSampleRate(SoapySDR.SOAPY_SDR_RX, 0)

    def get_center_frequency(self) -> float:
        """Get current center frequency"""
        if not self.sdr:
            return 0
        return self.sdr.getFrequency(SoapySDR.SOAPY_SDR_RX, 0)

    def cleanup(self):
        """Clean up device resources"""
        if self.rx_stream and self.sdr:
            self.sdr.deactivateStream(self.rx_stream)
            self.sdr.closeStream(self.rx_stream)
        if self.sdr:
            del self.sdr
        self.sdr = None
        self.rx_stream = None

# Test/demo code
if __name__ == "__main__":
    manager = SDRDeviceManager()
    devices = manager.enumerate_devices()

    print("Available SoapySDR devices:")
    for i, device in enumerate(devices):
        driver = _get_device_attr(device, 'driver', 'unknown')
        label = _get_device_attr(device, 'label', 'N/A')
        print(f"  {i}: {driver} - {label}")

    if devices:
        print(f"\nTesting device auto-selection...")
        if manager.initialize_device():
            print("Device initialized successfully!")
            manager.cleanup()
        else:
            print("Failed to initialize device")
    else:
        print("No SoapySDR devices found")