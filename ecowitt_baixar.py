"""
Ecowitt data downloader via SHARE LINK (no need to be the account owner).
by marciordg
https://github.com/marciordg/ecowitt-baixar
translated in english

Generates the same .xlsx as the "Export" button on the website, one file per day, in °C, hPa, m/s,
mm and W/m², with the same name as the website, e.g.:
    EasyWeatherPro-8D9C1E(202607140000-202607142359).xlsx

- Resolution: whatever the cloud still has (5 min in the last ~90 days, 30 min before).
- Time: the station's local time, as on the website.
- Only downloads days that do not already exist in the folder; never overwrites.
- The window remembers the last link and last folder used (in ~/.ecowitt_download.json,
  outside the repository).

Usage:
    python ecowitt_download.py                                    # opens the window
    python ecowitt_download.py LINK 19/06/2026 [FOLDER]           # no window (scheduler)

Only uses the Python 3.9+ standard library.
"""

import json
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

# Edit this text with your station data; it appears in the "About" tab.
ABOUT = """Ecowitt Data Downloader

Station: Ecowitt (model: model of your station)
Location: (city)
Responsible: (name)
"""

HIGH_RESOLUTION_DAYS = 90
WARNING_90 = (f"The Ecowitt cloud only stores data every 5 min for the last ~{HIGH_RESOLUTION_DAYS} days. "
              "Older days come with a 30 min resolution.")

SITE = "https://www.ecowitt.net"
# Units: temperature °C (1), pressure hPa (3), wind m/s (6), rain mm (12), radiation W/m² (16)
COOKIE = "; ".join(
    f"ousaite_unit_cookie_{k}={v}" for k, v in {1: 1, 2: 3, 3: 6, 4: 12, 5: 16}.items()
)
HEADERS = {"Cookie": COOKIE, "User-Agent": "Mozilla/5.0"}
CONFIG = Path.home() / ".ecowitt_download.json"


def post(path, data):
    req = urllib.request.Request(
        SITE + path, data=urllib.parse.urlencode(data).encode(),
        headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def read_date(text):
    """dd/mm/yyyy (also accepts dd-mm-yyyy and dd.mm.yyyy)."""
    t = text.strip().replace("-", "/").replace(".", "/")
    return datetime.strptime(t, "%d/%m/%Y").date()


def link_code(link):
    """Accepts the whole link (…share?authorize=ABC123…) or just the code."""
    link = link.strip()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    return q["authorize"][0] if "authorize" in q else link


def is_old(day):
    """True if the day has already left the cloud's high-resolution window."""
    return day < date.today() - timedelta(days=HIGH_RESOLUTION_DAYS)


def devices(authorize):
    """Raw data of the stations shared by this link (as the site returns)."""
    lst = post("/index/get_device_list", {"authorize": authorize}).get("list") or []
    if not lst:
        raise RuntimeError("Invalid link or no stations. Check the share link.")
    return lst


def stations(authorize):
    """List [(device_id, name)] of the stations shared by this link."""
    return [(d["device_id"], d["name"]) for d in devices(authorize)]


def download_day(authorize, device_id, day, folder):
    for attempt in range(3):
        try:
            resp = post(f"/index/export_excel?time={int(time.time() * 1000)}", {
                "device_id": device_id, "authorize": authorize, "mode": 0,
                "sdate": f"{day} 00:00", "edate": f"{day} 23:59",
                "sortList": "1|3|4|5|6", "hideList": "",
            })
            if str(resp.get("errcode")) != "0" or not resp.get("url"):
                raise RuntimeError(f"website response: {resp.get('errmsg')}")
            url = resp["url"]
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
                content = r.read()
            if not content.startswith(b"PK"):  # every .xlsx is a zip
                raise RuntimeError("the received file is not an .xlsx")
            destination = folder / urllib.parse.unquote(url.rsplit("/", 1)[-1])
            destination.write_bytes(content)
            return destination.name
        except Exception as error:
            last_error = error
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"failed 3 times ({last_error})")


def download(link, start, folder, log=print, stop=lambda: False):
    """Downloads from `start` to yesterday everything missing in the folder."""
    authorize = link_code(link)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    end = date.today() - timedelta(days=1)
    if is_old(start):
        log(f"WARNING: {WARNING_90}")
    failures = 0
    for device_id, name in stations(authorize):
        log(f"Station {name}: {start:%d/%m/%Y} to {end:%d/%m/%Y}")
        day = start
        while day <= end and not stop():
            if not any(folder.glob(f"{name}({day:%Y%m%d}0000-*.xlsx")):
                try:
                    res = " (30 min)" if is_old(day) else ""
                    log(f"  {day:%d/%m/%Y}  ok{res}  {download_day(authorize, device_id, day, folder)}")
                except RuntimeError as error:
                    failures += 1
                    log(f"  {day:%d/%m/%Y}  ERROR: {error}")
                time.sleep(2)  # be nice to the server
            day += timedelta(days=1)
    log("Interrupted." if stop() else
        f"Completed. {'Run again to try the ' + str(failures) + ' days with errors.' if failures else 'No errors.'}")


def window():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    root = tk.Tk()
    root.title("Download Ecowitt data")
    tabs = ttk.Notebook(root)
    tabs.pack(fill="both", expand=True)
    tab_download, tab_about = tk.Frame(tabs), tk.Frame(tabs)
    tabs.add(tab_download, text="Download")
    tabs.add(tab_about, text="About")

    # ---- Download tab ----
    try:
        saved = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    default = {
        "Share link": saved.get("link", ""),
        "Download from (dd/mm/yyyy)": f"{date.today() - timedelta(days=30):%d/%m/%Y}",
        "Destination folder": saved.get("folder", str(Path.home() / "Documents" / "ecowitt_data")),
    }
    fields = {}
    for i, (label_text, value) in enumerate(default.items()):
        tk.Label(tab_download, text=label_text).grid(row=i, column=0, sticky="w", padx=6, pady=3)
        e = tk.Entry(tab_download, width=60)
        e.insert(0, value)
        e.grid(row=i, column=1, padx=6, pady=3)
        fields[label_text] = e

    def choose_folder():
        p = filedialog.askdirectory()
        if p:
            fields["Destination folder"].delete(0, "end")
            fields["Destination folder"].insert(0, p)

    tk.Button(tab_download, text="…", command=choose_folder).grid(row=2, column=2, padx=6)

    output = scrolledtext.ScrolledText(tab_download, width=90, height=20, state="disabled")
    output.grid(row=4, column=0, columnspan=3, padx=6, pady=6)

    def log(msg):  # called from the download thread; Tk can only be modified in the main thread
        root.after(0, lambda: (output.configure(state="normal"), output.insert("end", msg + "\n"),
                               output.see("end"), output.configure(state="disabled")))

    stop_event = threading.Event()

    def start_download():
        link = fields["Share link"].get().strip()
        folder = fields["Destination folder"].get()
        try:
            start = read_date(fields["Download from (dd/mm/yyyy)"].get())
        except ValueError:
            return log("Invalid date. Use the format dd/mm/yyyy, e.g.: 19/06/2026")
        if not link:
            return log("Paste the station's share link.")
        if is_old(start) and not messagebox.askokcancel("Warning", WARNING_90 + "\n\nContinue?"):
            return
        try:
            CONFIG.write_text(json.dumps({"link": link, "folder": folder}), encoding="utf-8")
        except OSError:
            pass  # remembering the link is just a convenience
        stop_event.clear()
        button.configure(state="disabled")

        def work():
            try:
                download(link, start, folder, log, stop_event.is_set)
            except Exception as error:
                log(f"ERROR: {error}")
            root.after(0, lambda: button.configure(state="normal"))

        threading.Thread(target=work, daemon=True).start()

    button = tk.Button(tab_download, text="Download", width=15, command=start_download)
    button.grid(row=3, column=1, sticky="w", padx=6)
    tk.Button(tab_download, text="Stop", width=15, command=stop_event.set).grid(row=3, column=1, sticky="e", padx=6)

    # ---- About tab ----
    tk.Label(tab_about, text=ABOUT + "\n" + WARNING_90, justify="left", wraplength=620).pack(
        anchor="w", padx=10, pady=10)
    info_text = scrolledtext.ScrolledText(tab_about, width=90, height=14, state="disabled")

    def write_info(msg):
        info_text.configure(state="normal")
        info_text.delete("1.0", "end")
        info_text.insert("end", msg)
        info_text.configure(state="disabled")

    def query_station():
        link = fields["Share link"].get().strip()
        if not link:
            return write_info("Paste the link in the Download tab.")
        write_info("Querying…")

        def work():
            try:
                lines = []
                for d in devices(link_code(link)):
                    lines += [f"{k}: {v}" for k, v in d.items()
                               if isinstance(v, (str, int, float)) and str(v) != ""]
                    lines.append("")
                msg = "\n".join(lines)
            except Exception as error:
                msg = f"ERROR: {error}"
            root.after(0, lambda: write_info(msg))

        threading.Thread(target=work, daemon=True).start()

    tk.Button(tab_about, text="Query station via link", command=query_station).pack(anchor="w", padx=10)
    info_text.pack(padx=10, pady=6)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        window()
    elif sys.argv[1:] == ["--test"]:
        assert link_code("https://www.ecowitt.net/home/share?authorize=ABC123&device_id=x") == "ABC123"
        assert link_code("ABC123") == "ABC123"
        assert read_date(" 19/06/2026 ") == read_date("19-06-2026") == date(2026, 6, 19)
        assert is_old(date.today() - timedelta(days=91)) and not is_old(date.today() - timedelta(days=89))
        print("ok")
    else:
        folder = sys.argv[3] if len(sys.argv) > 3 else Path(__file__).resolve().parent / "data"
        download(sys.argv[1], read_date(sys.argv[2]), folder)
