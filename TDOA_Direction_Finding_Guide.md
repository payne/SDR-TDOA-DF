# TDOA Direction Finding Guide for NOAA Weather Radio on DragonOS Noble

This guide outlines the steps to implement Time Difference of Arrival (TDOA) direction finding to locate a NOAA Weather Radio transmitter at 162.400 MHz (WXL68, Omaha, Nebraska) using two or three RTL-SDR stations in the Omaha metropolitan area. Synchronization is achieved using either a USB GPS receiver or the ATSC TV pilot carrier from KETV Channel 7 at 174.309 MHz. Each station uses a single RTL-SDR dongle with the `librtlsdr-2freq` library for capturing both target and reference signals when GPS is unavailable.

## Prerequisites
- **Hardware** (per station):
  - RTL-SDR dongle (e.g., RTL-SDR Blog V3 or V4).
  - Raspberry Pi 4 or similar device running DragonOS Noble (Ubuntu-based SDR distribution).
  - USB GPS receiver (e.g., u-blox 7 or 8) for GPS synchronization, if used.
  - Antenna suitable for 162.400 MHz and 174.309 MHz (e.g., discone or V-dipole).
  - Stable power supply and internet connection for data transfer.
- **Software** (pre-installed on DragonOS Noble or to be installed):
  - `librtlsdr-2freq` (modified librtlsdr for seamless frequency switching).
  - GNU Radio for signal processing.
  - MATLAB or Python (NumPy, SciPy) for TDOA calculations.
  - GPSD for GPS time synchronization, if used.
  - NTP or PTP for network time synchronization as a fallback.
- **Setup**:
  - Stations should be placed 5–10 km apart in the Omaha metropolitan area for optimal geometry (e.g., triangular arrangement for three stations).
  - Known coordinates for each station (latitude, longitude) using GPS or precise mapping.
  - Line-of-sight to the NOAA transmitter and KETV signal, if possible.

## Step 1: Hardware Setup
1. **Position the Stations**:
   - Deploy 2 or 3 RTL-SDR stations across the Omaha metropolitan area, ideally 5–10 km apart to ensure measurable time differences. For three stations, arrange in a triangular pattern to improve localization accuracy via multilateration.
   - Record precise coordinates (latitude, longitude) for each station using a GPS receiver or a mapping tool like Google Maps.

2. **Connect Hardware**:
   - Attach the RTL-SDR dongle to the Raspberry Pi via USB.
   - Connect a suitable antenna (e.g., discone or V-dipole tuned for 162–174 MHz) to the RTL-SDR.
   - If using GPS synchronization, connect a USB GPS receiver to each Raspberry Pi.
   - Ensure stable power and internet connectivity (Ethernet or Wi-Fi) for data transfer.

3. **Antenna Considerations**:
   - Use a broadband antenna (e.g., discone) to capture both 162.400 MHz (NOAA) and 174.309 MHz (KETV ATSC pilot).
   - Position antennas with clear line-of-sight to maximize signal strength. Elevate antennas if possible to reduce obstructions.

## Step 2: Software Installation and Configuration
1. **Verify DragonOS Noble Setup**:
   - DragonOS Noble includes many SDR tools pre-installed (e.g., GNU Radio, rtl-sdr). Verify by running:
     ```bash
     rtl_test
     ```
     If `rtl_test` fails, install `rtl-sdr`:
     ```bash
     sudo apt update
     sudo apt install rtl-sdr
     ```

2. **Install librtlsdr-2freq**:
   - The `librtlsdr-2freq` library enables seamless frequency switching for capturing both the NOAA signal and the KETV reference signal. Install it as follows:
     ```bash
     git clone https://github.com/DC9ST/librtlsdr-2freq.git
     cd librtlsdr-2freq
     mkdir build && cd build
     cmake ..
     make
     sudo make install
     sudo ldconfig
     ```
   - Verify installation:
     ```bash
     rtl_sdr -h
     ```
     [Ensure the `librtlsdr-2freq` fork (`async-rearrangements`) is used to avoid sample loss during frequency switching.](https://panoradio-sdr.de/tdoa-transmitter-localization-with-rtl-sdrs/)
       - Discuss(N3PAY): `git checkout librtlsdr-2freq`  # showed no such branch in DC9ST's copy of the repo.

3. **Install GPSD (if using GPS synchronization)**:
   - Install and configure GPSD for precise timing:
     ```bash
     sudo apt install gpsd gpsd-clients
     ```
   - Configure GPSD to use the USB GPS receiver:
     ```bash
     sudo nano /etc/default/gpsd
     ```
     Set:
     ```
     DEVICES="/dev/ttyACM0"
     GPSD_OPTIONS="-n"
     ```
     Start GPSD:
     ```bash
     sudo systemctl start gpsd
     sudo systemctl enable gpsd
     ```
     Verify GPS lock:
     ```bash
     cgps -s
     ```

4. **Install Signal Processing Tools**:
   - Ensure GNU Radio is installed (pre-installed on DragonOS Noble):
     ```bash
     gnuradio-companion
     ```
   - Install Python dependencies for TDOA calculations:
     ```bash
     sudo apt install python3-numpy python3-scipy python3-matplotlib
     ```
   - Optionally, install MATLAB if preferred for post-processing.

## Step 3: Synchronization Setup
Choose one of the following synchronization methods:

### Option 1: GPS Synchronization
- **Setup**:
  - Ensure each station’s GPS receiver has a clear view of the sky to acquire a lock.
  - Use GPSD to obtain precise timestamps (1 PPS signal) with nanosecond accuracy.
- **Configuration**:
  - Modify your GNU Radio flowgraph (see Step 4) to timestamp samples using GPSD’s 1 PPS signal. The `rtl_sdr` command with `librtlsdr-2freq` supports GPS-timestamped data when configured.
  - Ensure all stations are synchronized to within 10 ns for ~3-meter accuracy.[](https://www.reddit.com/r/RTLSDR/comments/1b7vm4j/tdoa_in_short_range/)

### Option 2: Reference Signal Synchronization (KETV ATSC Pilot at 174.309 MHz)
- **Setup**:
  - Use the ATSC TV pilot carrier from KETV Channel 7 at 174.309 MHz as a common reference signal.
  - Configure `librtlsdr-2freq` to switch between 162.400 MHz (NOAA) and 174.309 MHz (KETV) seamlessly without sample loss.
- **Configuration**:
  - Use the `rtl_sdr` command with `librtlsdr-2freq` to capture both frequencies:
    ```bash
    rtl_sdr -f 162400000,174309000 -s 2048000 output.bin
    ```
    This captures interleaved samples from both frequencies at a 2.048 MS/s sampling rate.
  - Process the reference signal to align timestamps by correlating the ATSC pilot’s known structure (e.g., using cross-correlation in GNU Radio or Python).

## Step 4: Signal Capture
1. **Create a GNU Radio Flowgraph**:
   - Open GNU Radio Companion (`gnuradio-companion`).
   - Create a flowgraph to capture signals from the RTL-SDR:
     - **Source**: `RTL-SDR Source` block.
       - Set `Sample Rate` to 2.048 MHz.
       - Set `Center Frequency` to 162.400 MHz (NOAA) or use `librtlsdr-2freq` to alternate between 162.400 MHz and 174.309 MHz.
     - **Output**: `File Sink` to save raw IQ samples (e.g., `noaa_station1.bin`).
     - If using GPS, add a block to timestamp samples using GPSD’s 1 PPS signal.
     - If using the reference signal, alternate frequencies and save interleaved samples.
   - Save the flowgraph as `tdoa_capture.grc`.

2. **Capture Signals**:
   - Run the flowgraph on each station simultaneously:
     ```bash
     python3 tdoa_capture.py
     ```
   - Ensure all stations capture data for at least 10–30 seconds to gather sufficient samples.
   - If using the reference signal, ensure the KETV signal at 174.309 MHz is strong enough for reliable correlation.

3. **Transfer Data**:
   - Transfer the captured `.bin` files to a central computer for processing using `scp` or a shared network drive:
     ```bash
     scp noaa_station1.bin user@central-pc:/path/to/data/
     ```

## Step 5: TDOA Processing
1. **Preprocess Signals**:
   - If using the reference signal, separate the interleaved NOAA (162.400 MHz) and KETV (174.309 MHz) samples.
   - Perform cross-correlation on the KETV signal to align timestamps across stations:
     ```python
     import numpy as np
     from scipy.signal import correlate

     # Load IQ samples
     data1 = np.fromfile('noaa_station1.bin', dtype=np.complex64)
     data2 = np.fromfile('noaa_station2.bin', dtype=np.complex64)

     # Extract reference signal (KETV) portions
     ref1 = data1[::2]  # Assuming interleaved samples
     ref2 = data2[::2]

     # Cross-correlate reference signals
     corr = correlate(ref1, ref2, mode='full')
     time_offset = (np.argmax(np.abs(corr)) - len(ref1)) / 2048000  # Time offset in seconds
     ```
   - If using GPS, timestamps are already aligned.

2. **Calculate TDOA**:
   - Cross-correlate the NOAA signal (162.400 MHz) between stations to find time differences:
     ```python
     noaa1 = data1[1::2]  # NOAA signal samples
     noaa2 = data2[1::2]
     corr_noaa = correlate(noaa1, noaa2, mode='full')
     tdoa = (np.argmax(np.abs(corr_noaa)) - len(noaa1)) / 2048000  # TDOA in seconds
     ```
   - Repeat for all station pairs (e.g., Station 1–2, Station 1–3, Station 2–3 for three stations).

3. **Multilateration**:
   - Convert TDOA values to distance differences using the speed of light (\(c = 299792458 \, \text{m/s}\)):
     ```python
     c = 299792458  # Speed of light (m/s)
     distance_diff = tdoa * c  # Distance difference in meters
     ```
   - Solve the multilateration equations using known station coordinates. For two stations, this defines a hyperbola; for three, the intersection of hyperbolas gives the transmitter’s coordinates.
   - Use a Python library like `scipy.optimize` to solve:
     ```python
     from scipy.optimize import minimize

     def tdoa_error(x, stations, tdoas):
         # x = [lat, lon] of estimated transmitter
         # stations = list of [lat, lon] for each station
         # tdoas = measured time differences
         error = 0
         for i, (s1, s2, tdoa) in enumerate(zip(stations[:-1], stations[1:], tdoas)):
             d1 = great_circle_distance(x, s1)
             d2 = great_circle_distance(x, s2)
             error += (d1 - d2 - tdoa * c) ** 2
         return error

     # Define great_circle_distance function using haversine formula
     from math import radians, sin, cos, sqrt, atan2
     def great_circle_distance(p1, p2):
         lat1, lon1 = map(radians, p1)
         lat2, lon2 = map(radians, p2)
         dlat = lat2 - lat1
         dlon = lon2 - lon1
         a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
         return 2 * 6371000 * atan2(sqrt(a), sqrt(1-a))  # Earth radius in meters

     # Example station coordinates (Omaha area, in degrees)
     stations = [[41.2565, -95.9345], [41.3088, -96.0568], [41.2000, -96.0000]]
     tdoas = [tdoa12, tdoa13, tdoa23]  # From cross-correlation
     result = minimize(tdoa_error, x0=[41.25, -95.95], args=(stations, tdoas))
     transmitter_location = result.x  # [latitude, longitude]
     ```

## Step 6: Visualize Results
- Plot the estimated transmitter location on a map using Python’s `matplotlib` and `cartopy`:
  ```python
  import matplotlib.pyplot as plt
  import cartopy.crs as ccrs

  plt.figure(figsize=(10, 10))
  ax = plt.axes(projection=ccrs.PlateCarree())
  ax.stock_img()
  ax.scatter([s[1] for s in stations], [s[0] for s in stations], c='blue', label='Stations')
  ax.scatter(transmitter_location[1], transmitter_location[0], c='red', label='Transmitter')
  ax.legend()
  ax.set_extent([-96.2, -95.8, 41.1, 41.4])  # Omaha area
  plt.show()
  ```

## Step 7: Validation and Optimization
- **Validate**:
  - Compare the estimated location to the known WXL68 coordinates (near Omaha, approximately 41.3111, -95.8997).
  - Accuracy depends on station geometry, synchronization precision, and signal quality. Three stations typically yield better results than two due to multiple hyperbola intersections.[](https://www.inpixon.com/technology/standards/time-difference-of-arrival)
- **Optimize**:
  - Increase sampling rate (e.g., 2.4 MS/s) for better correlation accuracy, if RTL-SDR supports it.
  - Use a low-noise amplifier (LNA) to improve signal quality, especially for the KETV reference signal.[](https://forums.radioreference.com/threads/receiving-signals-from-noaa-weather-satellites-using-malachite-sdr.477152/)
  - For GPS, ensure a strong satellite lock to minimize timing errors.
  - For reference signal, verify the ATSC pilot at 174.309 MHz is stable and strong at all stations.

## Troubleshooting
- **No Signal on 162.400 MHz**: Check antenna alignment, increase RF gain in GNU Radio, or verify NOAA WXL68 is active (use `n2yo.com` for satellite schedules if confused with APT signals).
- **Poor Synchronization**: For GPS, ensure clear sky view; for KETV reference, confirm strong signal reception and correct frequency switching with `librtlsdr-2freq`.
- **Inaccurate Localization**: Ensure precise station coordinates, verify TDOA calculations, and consider adding a third station for better multilateration.

## Notes
- The NOAA Weather Radio at 162.400 MHz is a terrestrial signal, not a satellite APT signal (137 MHz). Ensure your setup targets the ground-based WXL68 transmitter.
- The `librtlsdr-2freq` library is critical for reference signal synchronization to avoid sample loss.[](https://panoradio-sdr.de/tdoa-transmitter-localization-with-rtl-sdrs/)
- For advanced users, consider using a KrakenSDR for phase-based direction finding, though it’s more expensive.[](https://www.reddit.com/r/RTLSDR/comments/1b7vm4j/tdoa_in_short_range/)
- MATLAB code for TDOA is available from Stefan Scholl’s GitHub for reference.[](https://www.rtl-sdr.com/localizing-transmitters-to-within-a-few-meters-with-tdoa-and-rtl-sdr-dongles/)
