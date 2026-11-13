fork of ecowitt-baixar by marciordg

[ecowitt-baixar](https://github.com/marciordg/ecowitt-baixar)

# ecowitt-XLS-Downloader

Downloads data from an **Ecowitt** weather station using only the **share link** (no need to be the account owner).

Generates the same `.xlsx` files as the *Export* button on the ecowitt.net website, **one file per day**, in the units °C, hPa, m/s, mm, and W/m².

* Resolution: whatever the cloud still stores (5 min for the last ~90 days, 30 min before that).
* Time: the station's local time, as on the website.
* Only downloads days that do not already exist in the folder; never overwrites.
* Uses only the Python 3.9+ standard library (nothing to install).

## Usage

With a window (paste the link, choose the start date and the folder):

```bash
python ecowitt_baixar.py

```

The window has two tabs:

* **Download**: link, start date, and folder. The program remembers the last used link and folder (in `~/.ecowitt_baixar.json`, outside the repository). If the link changes, just paste the new one.
* **About**: station data (edit the `SOBRE` text at the beginning of the script) and the *Consult station via link* button, which shows what Ecowitt reports about the shared station.

If the start date is more than 90 days ago, the program warns that those days come with a 30 min resolution instead of 5 min.

Without a window (useful for Task Scheduler / cron):

```bash
python ecowitt_baixar.py "SHARE_LINK" 19/06/2026 [FOLDER]

```

If the folder is not specified, the files will go to `dados/` next to the script.

Quick test of the internal functions:

```bash
python ecowitt_baixar.py --teste

```

## Attention

Do not put your station's share link in the repository: anyone with the link can view the data.
