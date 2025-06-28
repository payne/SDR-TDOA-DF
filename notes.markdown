
```
[ 2524.903762] usb 1-2: new high-speed USB device number 7 using xhci_hcd
[ 2525.045569] usb 1-2: New USB device found, idVendor=0bda, idProduct=2838, bcdDevice= 1.00
[ 2525.045592] usb 1-2: New USB device strings: Mfr=1, Product=2, SerialNumber=3
[ 2525.045600] usb 1-2: Product: Blog V4
[ 2525.045605] usb 1-2: Manufacturer: RTLSDRBlog
[ 2525.045610] usb 1-2: SerialNumber: 00000001
root@dragon1:~# 
```

My output from `rtl_test`

Found 1 device(s):
  0:  RTLSDRBlog, Blog V4, SN: 00000001

Using device 0: Generic RTL2832U OEM
Found Rafael Micro R828D tuner
RTL-SDR Blog V4 Detected
Supported gain values (29): 0.0 0.9 1.4 2.7 3.7 7.7 8.7 12.5 14.4 15.7 16.6 19.7 20.7 22.9 25.4 28.0 29.7 32.8 33.8 36.4 37.2 38.6 40.2 42.1 43.4 43.9 44.5 48.0 49.6 
Sampling at 2048000 S/s.

Info: This tool will continuously read from the device, and report if
samples get lost. If you observe no further output, everything is fine.

Reading samples in async mode...
Allocating 15 zero-copy buffers
lost at least 220 bytes

