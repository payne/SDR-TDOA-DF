import subprocess
import re
import argparse

def calibrate_rtlsdr(dongle_index, band="GSM850", gain=40):
    """Calibrate RTL-SDR dongle and return PPM offset."""
    cmd = f"kalibrate-rtl -i {dongle_index} -s {band} -g {gain}"
    try:
        output = subprocess.check_output(cmd, shell=True, text=True)
        ppm_match = re.search(r"average absolute error: (\d+\.\d+) ppm", output)
        if ppm_match:
            ppm = float(ppm_match.group(1))
            print(f"Dongle {dongle_index} PPM offset: {ppm}")
            return ppm
        else:
            raise ValueError("PPM offset not found in kalibrate-rtl output")
    except subprocess.CalledProcessError as e:
        print(f"Calibration failed for dongle {dongle_index}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Calibrate RTL-SDR dongle")
    parser.add_argument("--dongle_index", type=int, default=0, help="RTL-SDR dongle index")
    parser.add_argument("--band", type=str, default="GSM850", help="GSM band for calibration")
    parser.add_argument("--gain", type=int, default=40, help="Receiver gain")
    parser.add_argument("--output", type=str, default="ppm_offset.txt", help="Output file for PPM")
    args = parser.parse_args()

    ppm = calibrate_rtlsdr(args.dongle_index, args.band, args.gain)
    if ppm is not None:
        with open(args.output, "w") as f:
            f.write(str(ppm))
        print(f"PPM offset saved to {args.output}")

if __name__ == "__main__":
    main()