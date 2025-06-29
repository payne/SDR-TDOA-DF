# Data collection powered by Vibe coding 

Claude.ai [answers](https://claude.ai/chat/95272d44-fe82-42d9-b211-f742d8231157) to the prompt: 
  Provide a start-to-finish guide for implementing Time Difference of Arrival (TDOA) direction finding on DragonOS Noble, targeting a NOAA Weather Radio signal at 162.400 MHz (WXL68 in Omaha, Nebraska) using two or three local RTL-SDR stations in the same metropolitan area.

Includes the script `collect_samples.py`.  Here's how I ran it on my dragonOS instance:

1. `python3 -m venv ./venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python collect_samples.py`


```
total 11168
-rw-rw-r-- 1 mpayne mpayne     1836 Jun 29 11:55 collect_samples.py
-rw-rw-r-- 1 mpayne mpayne     3875 Jun 29 12:08 process_tdoa.py
-rw-rw-r-- 1 mpayne mpayne        0 Jun 29 12:43 README.md
-rw-rw-r-- 1 mpayne mpayne      460 Jun 29 12:42 requirements.txt
-rw-rw-r-- 1 mpayne mpayne 11423255 Jun 29 12:03 tdoa_station1_1751216619.npz
```
