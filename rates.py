#!/usr/bin/python3
import requests
import json
import datetime
from pytz import timezone
import logging
import os
import sys
import configparser
import time
from typing import Optional

# =========================
# GLOBAL FLAGS
# =========================
RUN = True
DRY_RUN = False          # <-- set True to test without switching relays
WINTER_HOLIDAY = False

# =========================
# HTTP SESSION
# =========================
SESSION = requests.Session()
SESSION.headers.update({"Content-Type": "application/json"})

def http_get(url):
    return SESSION.get(url, timeout=5)

def http_post(url, **kwargs):
    return SESSION.post(url, timeout=5, **kwargs)

# =========================
# CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(BASE_DIR, "config.ini"))

logfile = os.path.join(BASE_DIR, "log")
apidata = os.path.join(BASE_DIR, "api.json")

cloud_id = config['CREDS']['CLOUD_ID']
cloud_token = config['CREDS']['CLOUD_TOKEN']
cloud_host = config['SERVER']['CLOUD_HOST']

bassein_ip = config['SERVER']['POOL_IP']
boiler_ip = config['SERVER']['BOILER_IP']
kyte_x3_ip = config['SERVER']['HEATING_X3_IP']
vent_ip = config['SERVER']['VENT_IP']

k0_temp_id = config['SERVER']['0K_TEMP_ID']
k1_temp_id = config['SERVER']['1K_TEMP_ID']
k2_temp_id = config['SERVER']['2K_TEMP_ID']
pool_temp_id = config['SERVER']['POOL_TEMP_ID']
pool_water_temp_id = config['SERVER']['POOL_WATER_TEMP_ID']
k0_dush_id = config['SERVER']['0K_DUSH_ID']
k2_dush_id = config['SERVER']['2K_DUSH_ID']
k0_kuivati = config['SERVER']['0K_KUIVATI']
k2_kuivati = config['SERVER']['2K_KUIVATI']


bassein_vee_temp_ip = config['SERVER']['POOL_WATER_TEMP_IP']


# =========================
# LIMITS
# =========================
kyte_boiler_max_hind = 500
kyte_saast_hind = 200
bassinikytte_hind = 75

toa_temp_max = 21.5
k1_temp_ok = 20.5
k2_temp_ok = 20.5
winter_holiday_temp = 11.0
humidity_ok = 54.0
vee_temp_max = 1.5
talve_temp_min = 15.0

ELV_day = 45
ELV_night = 25.6
EE_marginal = 0

# =========================
# LOGGING
# =========================
logging.basicConfig(
    filename=logfile,
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)

# =========================
# SWITCH HELPERS
# =========================
def switch(ip: str, switch_id: str, on: bool, device: str):
    if DRY_RUN:
        logging.info(f"DRY_RUN {device} {ip}:{switch_id} -> {'ON' if on else 'OFF'}")
        return
    payload = {
        "id": 1,
        "method": "Switch.Set",
        "params": {"id": int(switch_id), "on": on}
    }
    try:
        http_post(f"http://{ip}/rpc", json=payload)
        logging.info(f"---- {device} {ip}:{switch_id} -> {'ON' if on else 'OFF'}")
    except Exception as e:
        logging.error(f"Switch failed {ip}:{switch_id} -> {e}")

def get_state(ip: str) -> Optional[bool]:
    try:
        r = http_post(
            f"http://{ip}/rpc",
            json={"id": 1, "method": "Switch.GetStatus", "params": {"id": 0}}
        )
        return r.json()["result"]["output"]
    except Exception as e:
        logging.error(f"State read failed {ip}: {e}")
        return None

# =========================
# HEATER SWITCH
# =========================
def heater_on():
    switch(kyte_x3_ip, "0", False, "kyte")

def heater_off():
    switch(kyte_x3_ip, "0", True, "kyte")

# =========================
# PRICE
# =========================
def get_price() -> Optional[int]:
    now = time.time()
    try:
        r = http_get("https://dashboard.elering.ee/api/nps/price/EE/current")
        data = r.json()
        rate = data["data"][0]["price"]
        hour = datetime.datetime.now(timezone("Europe/Tallinn")).hour
        weekday = datetime.datetime.today().weekday()
        elv = ELV_night if weekday >= 5 or hour >= 22 or hour < 7 else ELV_day
        price = round((rate + elv) * 1.22 + EE_marginal)
        with open(apidata, "w") as f:
            json.dump({"ts": now, "price": price}, f)
        return price
    except Exception as e:
        logging.error(f"Price fetch failed: {e}")
        return None

# =========================
# CLOUD FETCH
# =========================
def get_cloud_status(ids):
    try:
        r = http_post(
            f"https://{cloud_host}/v2/devices/api/get?auth_key={cloud_token}",
            json={"ids": ids, "select": ["status"]}
        )
        return {d["id"]: d["status"] for d in r.json()}
    except Exception as e:
        logging.error(f"Cloud fetch failed: {e}")
        return {}

# =========================
# POOL TEMP
# =========================
def get_pool_temp(ip):
        url = f"http://{ip}/status"
        headers = {'Content-Type': 'application/json'}
        try:
            req = requests.get(url, headers=headers)
            data = {}
            data = json.loads(req.text)
            temp = data["ext_temperature"]["0"]["tC"]
            temp_float = float(temp)
            return temp_float

        except Exception as e:
            logging.error(f"Pool temp fetch failed {ip} -  {e}")
            return None
    
# =========================
# MAIN LOGIC
# =========================
def main():
    if not RUN:
        return

    price = get_price()
    if price is None:
        logging.warning("Price missing - fail safe")
        heater_off()
        return

    cloud = get_cloud_status([
        k1_temp_id, k2_temp_id,
        k0_dush_id, k2_dush_id,
    ])

    k1 = cloud.get(k1_temp_id, {}).get("temperature:0", {}).get("tC")
    k2 = cloud.get(k2_temp_id, {}).get("temperature:0", {}).get("tC")
    h0 = cloud.get(k0_dush_id, {}).get("humidity:0", {}).get("rh")
    h2 = cloud.get(k2_dush_id, {}).get("humidity:0", {}).get("rh")
    pool_temp = get_pool_temp(bassein_vee_temp_ip)

    logging.info(f"PRICE={price} K1={k1} K2={k2} H0={h0} H2={h2} Pool={pool_temp}")

    # -------- HUMIDITY --------
    if h0 and h0 > humidity_ok and price < kyte_boiler_max_hind:
        logging.info(f"Niiskus H0 on {h0} - hind on {price} - Kuivatus sisse")
        switch(vent_ip, "0", True, "Vent_0k")
        switch(k0_kuivati, "0", True, "Kuivati_0k")
    else:
        logging.info(f"Niiskus H0 on {h0} - hind on {price} - Kuivatus valja")
        switch(vent_ip, "0", False, "Vent_0k")
        switch(k0_kuivati, "0", False, "Kuivati_0k")

    if h2 and h2 > humidity_ok and price < kyte_boiler_max_hind:
        logging.info(f"Niiskus H2 on {h2} - hind on {price} - Kuivatus sisse")
        switch(vent_ip, "1", True, "Vent_2k")
        switch(k2_kuivati, "0", True, "Kuivati_2k")
    else:
        logging.info(f"Niiskus H2 on {h2} - hind on {price} - Kuivatus valja")
        switch(vent_ip, "1", False, "Vent_2k")
        switch(k2_kuivati, "0", False, "Kuivati_2k")

    
    if WINTER_HOLIDAY:
        if any(t and t < winter_holiday_temp for t in [k1, k2]):
            logging.info(f"TALVE PUHKUS - temperatuur madalam kui {winter_holiday_temp}  - Kyte sisse")
            heater_on()
        else:
            heater_off()
        return

    if price > kyte_boiler_max_hind:
        if not any(t and t < talve_temp_min for t in [k1, k2]):
            logging.info(f"Hind {price} on korgem kui {kyte_boiler_max_hind} - Kyte ja boiler valja")
            heater_off()
            switch(boiler_ip, "0", False, "Boiler")
        else:
            heater_on()
        return

    logging.info(f"Hind {price} on madalam kui {kyte_boiler_max_hind} - Kyte ja boiler sisse")
    switch(boiler_ip, "0", True, "Boiler")
    
    # -------- POOL -----------
    
    if price > bassinikytte_hind:
        logging.info(f"Hind {price} on korgem kui basseinikytte lubatud hind {bassinikytte_hind} - Basseinikyte valjas")
        switch(bassein_ip,"0", False, "Bassein")

    else:
        if pool_temp <= vee_temp_max:
            switch(bassein_ip, "0", True, "Bassein")
            logging.info(f"Basseini temperatuur {pool_temp} on madalam voi vordne kui {vee_temp_max} - Basseinikyte sees")
        else:
            switch(bassein_ip, "0", False, "Bassein")
            logging.info(f"Basseini temperatuur {pool_temp} on korgem kui {vee_temp_max} - Basseinikyte valjas")

    # -------- HEATING --------
    if price < kyte_saast_hind:
        if (k1 and k1 < toa_temp_max) or (k2 and k2 < toa_temp_max):
            heater_on()
            logging.info(f"Hind {price} on madalam kui {kyte_saast_hind} - K1 temp {k1}, K2 temp {k2} on madalam kui {toa_temp_max} - kyte sisse")
        else:
            heater_off()
            logging.info(f"Hind {price} on madalam kui {kyte_saast_hind} - K1 temp {k1}, K2 temp {k2} on korgem kui {toa_temp_max} - kyte valja")
        return

    if (k1 and k1 < k1_temp_ok) or (k2 and k2 < k2_temp_ok):
        heater_on()
        logging.info(f"Hind {price} on korgem kui {kyte_saast_hind} - K1 temp {k1}, K2 temp {k2} on madalam kui K1:{k1_temp_ok}, K2:{k2_temp_ok} - kyte sisse")
    else:
        heater_off()
        logging.info(f"Hind {price} on korgem kui {kyte_saast_hind} - K1 temp {k1}, K2 temp {k2} on korgem kui K1:{k1_temp_ok}, K2:{k2_temp_ok} - kyte valja")

# =========================
if __name__ == "__main__":
    main()

