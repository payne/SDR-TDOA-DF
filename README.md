# TDOA DF

Experiments in learning about TDoA (Time Difference of Arrival) radio direction finding.

## First results are less than 4 miles off!

1. https://payne.github.io/SDR-TDOA-DF/ClaudeOpus4/nice_data/tdoa_interactive_map.html
2. https://github.com/payne/SDR-TDOA-DF/blob/main/ClaudeOpus4/nice_data/correlation_analysis.png
3. https://github.com/payne/SDR-TDOA-DF/blob/main/ClaudeOpus4/nice_data/tdoa_analysis_results.png


## Links
1. https://www.reddit.com/r/RTLSDR/comments/1b7vm4j/tdoa_in_short_range/
2. https://panoradio-sdr.de/set-up-a-tdoa-system/
3. https://en.wikipedia.org/wiki/Direction_of_arrival
4. https://www.rtl-sdr.com/tag/time-difference-of-arrival/
5. https://www.rtl-sdr.com/aeda-crowd-sourced-rtl-sdr-spectrum-analysis-and-tdoa-direction-finding-platform/


# Data collection powered by Vibe coding 

Claude.ai [answers](https://claude.ai/share/e9b6884b-1b7e-4dcb-9325-e056f46d50c6) to the prompt: 
  Provide a start-to-finish guide for implementing Time Difference of Arrival (TDOA) direction finding on DragonOS Noble, targeting a NOAA Weather Radio signal at 162.400 MHz (WXL68 in Omaha, Nebraska) using two or three local RTL-SDR stations in the same metropolitan area.

Includes the script `collect_samples.py`.  Here's how I ran it on my dragonOS instance:

1. `python3 -m venv ./venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python collect_samples.py`

## Example output

```
(venv) mpayne@dragon1:~/git/SDR-TDOA-DF/ClaudeOpus4$ python collect_samples.py 
/home/mpayne/git/SDR-TDOA-DF/ClaudeOpus4/venv/lib/python3.12/site-packages/rtlsdr/__init__.py:19: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
  import pkg_resources
Found Rafael Micro R828D tuner
RTL-SDR Blog V4 Detected
Collecting samples at station station1...
Saved to tdoa_station1_1751219334.npz
(venv) mpayne@dragon1:~/git/SDR-TDOA-DF/ClaudeOpus4$ echo $?
0
(venv) mpayne@dragon1:~/git/SDR-TDOA-DF/ClaudeOpus4$ ls -lth
total 22M
-rw-rw-r-- 1 mpayne mpayne  11M Jun 29 12:48 tdoa_station1_1751219334.npz
drwxrwxr-x 6 mpayne mpayne 4.0K Jun 29 12:47 venv
-rw-rw-r-- 1 mpayne mpayne  989 Jun 29 12:46 README.md
-rw-rw-r-- 1 mpayne mpayne  460 Jun 29 12:42 requirements.txt
-rw-rw-r-- 1 mpayne mpayne 3.8K Jun 29 12:08 process_tdoa.py
-rw-rw-r-- 1 mpayne mpayne  11M Jun 29 12:03 tdoa_station1_1751216619.npz
-rw-rw-r-- 1 mpayne mpayne 1.8K Jun 29 11:55 collect_samples.py
(venv) mpayne@dragon1:~/git/SDR-TDOA-DF/ClaudeOpus4$ 
```


### files after first run
```
total 11168
-rw-rw-r-- 1 mpayne mpayne     1836 Jun 29 11:55 collect_samples.py
-rw-rw-r-- 1 mpayne mpayne     3875 Jun 29 12:08 process_tdoa.py
-rw-rw-r-- 1 mpayne mpayne        0 Jun 29 12:43 README.md
-rw-rw-r-- 1 mpayne mpayne      460 Jun 29 12:42 requirements.txt
-rw-rw-r-- 1 mpayne mpayne 11423255 Jun 29 12:03 tdoa_station1_1751216619.npz
```

## May the `at` be with you

To run at the same time this might help.

1. One time setup: `sudo apt install at`
2. `echo /home/mpayne/git/SDR-TDOA-DF/ClaudeOpus4/sync_collect_samples.py  | at 18:56`
3. `echo $(pwd)/sync_collect_samples.py  | at 18:56`  # more portable syntax

