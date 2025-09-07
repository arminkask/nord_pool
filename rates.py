#!/usr/bin/python3
import requests
import json
import datetime
from pytz import timezone
import time
import logging
import os
import sys
import configparser
import time
#Variables
#If set to 1 then run else exit 
run = 1
#Set to 1 if temperature in rooms should be kept no higher winter_holiday_temp variable
winter_holiday = 0
## Get config from file
config = configparser.ConfigParser(interpolation=None)
config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.ini')
logfile = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'log')
apidata = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'api.json')
config.read(config_file)

cloud_id = config['CREDS']['CLOUD_ID']
cloud_token = config['CREDS']['CLOUD_TOKEN']
cloud_host =  config['SERVER']['CLOUD_HOST']
bassein_ip = config['SERVER']['POOL_IP']
boiler_ip = config['SERVER']['BOILER_IP']
kyte_x2_ip = config['SERVER']['HEATING_X2_IP']
kyte_x3_ip = config['SERVER']['HEATING_X3_IP']
bassein_vee_temp_ip = config['SERVER']['POOL_WATER_TEMP_IP']
vent_ip = config['SERVER']['VENT_IP']
k0_temp_id = config['SERVER']['0K_TEMP_ID']
k0_dush_id = config['SERVER']['0K_DUSH_ID']
k1_temp_id = config['SERVER']['1K_TEMP_ID']
k2_temp_id = config['SERVER']['2K_TEMP_ID']
k2_dush_id = config['SERVER']['2K_DUSH_ID']
k2_kuivati = config['SERVER']['2K_KUIVATI']
k0_kuivati = config['SERVER']['0K_KUIVATI']
pool_temp_id = config['SERVER']['POOL_TEMP_ID']

##Prices
kyte_boiler_max_hind = 400.0
kyte_saast_hind = 200.0
bassinikytte_hind = 75.0

##Temps and humidity
vee_temp_max = float(21.5)
toa_temp_max = float(21.5)
p_temp_ok = float(18.0)
k0_temp_ok = float(18.5)
k1_temp_ok = float(20.5)
k2_temp_ok = float(20.5)
winter_holiday_temp = float(11.0)
humidity_ok = float(60.0)

##Energy company rates
EE_marginal = 0.0
ELV_day = 45
ELV_night = 25.6

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    filename=logfile,
    filemode='a',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')



def get_price():
    EET = timezone('Europe/Tallinn')
    curDT =  datetime.datetime.now(EET)
    hour = curDT.strftime("%H")
    weekday = datetime.datetime.today().weekday()
    url = "https://dashboard.elering.ee/api/nps/price/EE/current"
    response = requests.get(url)
    data = response.text
    parsed = json.loads(data)
    json_file = open(apidata,"w")
    json_file.write(data)
    rates = parsed["data"][0]["price"]
    if weekday >= 5 or hour in [ "22", "23", "0", "1", "2", "3", "4", "5", "6" ]:
        ELV_rate = ELV_night
        price = round((rates + ELV_rate)* 1.22 + EE_marginal)
    else:
        ELV_rate = ELV_day
        price = round((rates + ELV_rate)* 1.22 + EE_marginal)

    #logging.info(+ date_time + "Hind on "  str(ee_rate) )
    return price

def get_state(ip):
       url = "http://"+ ip +"/rpc"
       headers = {'Content-Type': 'application/x-www-form-urlencoded'}
       body = '{"id":1,"method":"Switch.GetStatus","params":{"id":0}}'
       try:
           req = requests.post(url, headers=headers, data=body)
           data = {}
           data = json.loads(req.text)
           state = data["result"]["output"]
           return state

       except Exception as e:
           logging.info("Ei saanud " + ip + " staatust katte ")
           logging.info("Exception: %s" % str(e))
           return None

def lylita_sisse(ip,switch_id):
    url = "http://"+ ip +"/rpc"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = '{"id":1,"method":"Switch.Set","params":{"id":'+switch_id+',"on":true}}'
    if switch_id == "":
        logging.info("lylita_valja ei saanud koiki parameetreid katte")      
    try:
        switch_on =  requests.post(url, headers=headers, data=data)
    except:
            switch_on = None
    return switch_on

def lylita_valja(ip,switch_id):
    url = "http://"+ ip +"/rpc"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = '{"id":1,"method":"Switch.Set","params":{"id":'+switch_id+',"on":false}}'
    if switch_id == "":
        logging.info("lylita_valja ei saanud koiki parameetreid katte")
    try:
        switch_off =  requests.post(url, headers=headers, data=data)
    except:
        switch_off = None
    return switch_off

def get_pool_temp(ip):
        url = "http://"+ ip +"/status"
        headers = {'Content-Type': 'application/json'}

        try:
            req = requests.get(url, headers=headers)
            data = {}
            data = json.loads(req.text)
            temp = data["ext_temperature"]["0"]["tC"]
            temp_float = float(temp)
            return temp_float

        except Exception as e:
            logging.info("Ei saanud vee temperatuuri katte ")
            logging.info("Exception: %s" % str(e))
            return 100

def get_room_temp_from_cloud(cloud_dev_id):
        url = f"https://{cloud_host}/v2/devices/api/get?auth_key={cloud_token}"
        headers = {"Content-Type": "application/json"}
        body = {
                "ids" : [cloud_dev_id],
                "select" : ["status"]
               }
        try:
            req = requests.post(url, json=body,headers=headers)
            data = json.loads(req.text)
            temp = data[0]["status"]["temperature:0"]["tC"]
            temp_float = float(temp)
            time.sleep(1)
            return temp_float

        except Exception as e:
            print(str(e) + " cloud ID " + cloud_dev_id)
            return 100

def get_room_humidity_from_cloud(cloud_dev_id):
        url = f"https://{cloud_host}/v2/devices/api/get?auth_key={cloud_token}"
        headers = {"Content-Type": "application/json"}
        body = {
                "ids" : [cloud_dev_id],
                "select" : ["status"]
               }
        try:
            req = requests.post(url, json=body,headers=headers)
            data = json.loads(req.text)
            temp = data[0]["status"]["humidity:0"]["rh"]
            temp_float = float(temp)
            time.sleep(1)
            return temp_float

        except Exception as e:
            logging.info(str(e) + " cloud ID " + cloud_dev_id)
            return 100
 

def main():

    if run != 1:
        logging.info("Run muutuja on " + str(run) + ". Valjun" ) 
        sys.exit(1)

    try:
        turuhind = get_price()

    except Exception as e:
        logging.info("Ei saanud turuhinda katte ")
        logging.info("Exception: %s" % str(e))
        sys.exit(1)


    turuhind_str = str(turuhind)
    bassinikytte_hind_str = str(bassinikytte_hind)
    kyte_boiler_max_hind_str = str(kyte_boiler_max_hind)
    kyte_saast_hind_str = str(kyte_saast_hind)
    vee_temp_max_str = str(vee_temp_max)

    turuhind_int = int(turuhind)
    bassinikytte_hind_int = int(bassinikytte_hind)
    kyte_boiler_max_hind_int = int(kyte_boiler_max_hind)
    kyte_saast_hind_int = int(kyte_saast_hind)

    k0_temp = get_room_temp_from_cloud(k0_temp_id)
    k1_temp = get_room_temp_from_cloud(k1_temp_id)
    k2_temp = get_room_temp_from_cloud(k2_temp_id)
    p_temp = get_room_temp_from_cloud(pool_temp_id)
    k0_humidity = get_room_humidity_from_cloud(k0_dush_id)
    k2_humidity = get_room_humidity_from_cloud(k2_dush_id)
    k0_temp_str = str(k0_temp)
    k1_temp_str = str(k1_temp)
    k2_temp_str = str(k2_temp)
    p_temp_str = str(p_temp)
    k0_humidity_str = str(k0_humidity)
    k2_humidity_str = str(k2_humidity)
    toa_temp_max_str = str(toa_temp_max)
    winter_holiday_temp_str = str(winter_holiday_temp)
    
    """ Kontrollime niiskust dushiruumides"""
    if k0_humidity > humidity_ok and turuhind_int < kyte_boiler_max_hind_int:
        try:
            lylita_sisse(vent_ip,"0")
            lylita_sisse(k0_kuivati,"0")
            logging.info("Niiskus saunas on "+k0_humidity_str+" - Ventilaator sees")

        except Exception as e:
            logging.info("Ei saanud ventilaatori IP -d katte " + vent_ip)
    else:
        try:
            lylita_valja(vent_ip,"0")
            lylita_valja(k0_kuivati,"0")
            logging.info("Niiskus saunas on "+k0_humidity_str+" - Ventilaator valjas")
        except Exception as e:
            logging.info("Ei saanud ventilaatori IP -d katte " + vent_ip)
            
    if k2_humidity > humidity_ok and turuhind_int < kyte_boiler_max_hind_int:
        try:
            lylita_sisse(vent_ip,"1")
            lylita_sisse(k2_kuivati,"0")
            logging.info("Niiskus 2k on "+k2_humidity_str+" - Ventilaator sees")
        except Exception as e:
            logging.info("Ei saanud ventilaatori IP -d katte " + vent_ip)
    else:
        try:
            lylita_valja(vent_ip,"1")
            lylita_valja(k2_kuivati,"0")
            logging.info("Niiskus 2k on "+k2_humidity_str+" - Ventilaator valjas")
        except Exception as e:
            logging.info("Ei saanud ventilaatori IP -d katte " + vent_ip)
    
    """ Kontrollime basseini temperatuuri ja hinda"""

    if turuhind_int > bassinikytte_hind_int:
        logging.info("Turuhind " + turuhind_str + " on korgem kui hea hind " + bassinikytte_hind_str +  "  - Basseinikyte valjas")
        try:
            lylita_valja(bassein_ip,"0")
            bassein_state = False
        except Exception as e:
            logging.info( + turuhind_int + "> "+ bassinikytte_hind_int +"- Ei saanud basseini IP -d katte " + bassein_ip)

    else:
          logging.info("Turuhind " + turuhind_str + " on madalam kui hea hind " + bassinikytte_hind_str + "  - Kontrollime vee temperatuuri")
          basseini_temp = get_pool_temp(bassein_vee_temp_ip)
          if basseini_temp <= vee_temp_max:
              try:
                  basseini_temp_str = str(basseini_temp)
                  lylita_sisse(bassein_ip,"0")
                  bassein_state = True
                  logging.info("Basseini temperatuur " + basseini_temp_str + " on madalam voi vordne kui " + vee_temp_max_str + " - Basseinikyte sees")

              except Exception as e:
                  logging.info(+ basseini_temp + " <  " + vee_temp_max + "- Ei saanud basseini IP -d katte " + bassein_ip)

          else:
              try:
                  basseini_temp_str = str(basseini_temp)
                  lylita_valja(bassein_ip,"0")
                  bassein_state = False
                  logging.info("Basseini temperatuur " + basseini_temp_str + " on korgem kui " + vee_temp_max_str + " - Basseinikyte valjas")
              except Exception as e:
                  logging.info("basseini_temp > vee_temp_max - Ei saanud basseini IP -d katte " + bassein_ip)

    
    """ Kui turuhind on korgem kui kyte_boiler_max_hind_int, siis lülita kyte ja boiler välja """

    if turuhind_int > kyte_boiler_max_hind_int:
        kyte_x3_state = get_state(kyte_x3_ip)  
        logging.info("Turuhind " + turuhind_str + " on korgem kui kytte max hind " + kyte_boiler_max_hind_str +  "  - Kyte ja boiler lyliti valjas")

        try:
            lylita_valja(boiler_ip,"0")
        except Exception as e:
            logging.info("turuhind > kyte_boiler_max_hind - Ei saanud boileri IP -d katte " + boiler_ip)
            
        try:
            if not kyte_x3_state:
               lylita_sisse(kyte_x3_ip,"0")
        except Exception as e:
            logging.info("turuhind > kyte_boiler_max_hind - Ei saanud kytte IP -d katte " + kyte_x3_ip)

    else:
        logging.info("Turuhind " + turuhind_str + " on madalam kui kytte hea hind " + kyte_boiler_max_hind_str + "  - Kyte ja boiler lyliti sees")

        try:
            lylita_sisse(boiler_ip,"0")
        except Exception as e:
            logging.info("turuhind <  kyte_boiler_max_hind_int - Ei saanud boileri IP -d katte " + boiler_ip)
         
        try:
            lylita_valja(kyte_x3_ip,"0")
            
        except Exception as e:
            logging.info("turuhind > kyte_boiler_max_hind - Ei saanud kytte IP -d katte " + kyte_x3_ip)


    """Kui winter_holiday on 1, siis hoiame temperatuure winter_holiday_temp väärtuse juures"""

    if winter_holiday == 1:
        try:
            kyte_x3_state = get_state(kyte_x3_ip)

        except Exception as e:
            logging.info("Winter holiday - X3 - Ei saanud IP -d katte " + kyte_x3_ip)
            sys.exit(1)

        if k1_temp < winter_holiday_temp and kyte_x3_state:
            try:
                lylita_valja(kyte_x3_ip,"0")
                logging.info("Winter holiday - 1 korruse temperatuur on madal " + k1_temp_str + " - Kyte sees")
                sys.exit(1)
            except Exception as e:
               logging.info("Winter holiday - 1 korruse temperatuur on madal - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        elif k2_temp < winter_holiday_temp and kyte_x3_state:
            try:
                lylita_valja(kyte_x3_ip,"0")
                logging.info("Winter holiday - 2 korruse temperatuur on madal " + k2_temp_str + " - Kyte sees")
                sys.exit(1)
            except Exception as e:
                logging.info("Winter holiday - 2 korruse temperatuur on madal - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        elif k0_temp < winter_holiday_temp and kyte_x3_state:
            try:
                lylita_valja(kyte_x3_ip,"0")
                logging.info("Winter holiday - 0 korruse temperatuur on madal " + k0_temp_str + " - Kyte sees")
                sys.exit(1)
            except Exception as e:
                logging.info("Winter holiday - 0 korruse temperatuur on madal - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        elif not kyte_x3_state:
            logging.info("Winter holiday -  temperatuur on " + k1_temp_str + ", K2 temperatuur on " + k2_temp_str +". See on korgem kui "+ winter_holiday_temp_str +" - Kyte valjas")
            try:
                lylita_sisse(kyte_x3_ip,"0")
                sys.exit(1)
            except Exception as e:
                logging.info("Winter holiday - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        else:
            sys.exit()
            
    """Kui turuhind on kalli ja madala vahel, siis vaata temperatuure"""

    if turuhind_int < kyte_boiler_max_hind_int and turuhind_int > kyte_saast_hind_int:
        logging.info("Turuhind " + turuhind_str + " on suurem kui kytte saastu hind " + kyte_saast_hind_str + ",kuid madalam kui " + kyte_boiler_max_hind_str + "  - Vaatame temperatuure")

        try:
            kyte_x3_state = get_state(kyte_x3_ip)

        except Exception as e:
                logging.info("get X3 - Ei saanud IP -d katte " + kyte_x3_ip)
                sys.exit(1)

        
        if k1_temp < k1_temp_ok:
            try:
                lylita_valja(kyte_x3_ip,"0")
                logging.info("1 korruse temperatuur on madal " + k1_temp_str + " - Kyte sees")
                sys.exit(1)
            except Exception as e:
               logging.info("1 korruse temperatuur on madal - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        elif k2_temp < k2_temp_ok:
            try:
                lylita_valja(kyte_x3_ip,"0")
                logging.info("2 korruse temperatuur on madal " + k2_temp_str + " - Kyte sees")
                sys.exit(1)

            except Exception as e:
                logging.info("2 korruse temperatuur on madal - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        elif not kyte_x3_state:
            try:
                lylita_sisse(kyte_x3_ip,"0")
                logging.info(f"Temperatuurid ruumides(k1 - {k1_temp_str},k2 -{k2_temp_str} on korgemad kui minimaalne temp - Kyte valjas")

            except Exception as e:
                logging.info("Temperatuurid ruumides on korgemad kui minimaalne temp -  Ei saanud kytte IP -d katte " + kyte_x3_ip)

        else:
            logging.info("X3 oli juba sees")
            
    """ Kui turuhind on madalam, kui kyte_saast_hind_int"""

    if turuhind_int < kyte_saast_hind_int:
        logging.info("Turuhind " + turuhind_str + " on madalam kui kytte saastu hind " + kyte_saast_hind_str + " - Kontrollime temperatuure")

        try:
            kyte_x3_state = get_state(kyte_x3_ip)

        except Exception as e:
            logging.info("Turuhind " + turuhind_str + " on madalam kui kytte saastu hind " + kyte_saast_hind_str + "Reset X3 - Ei saanud IP -d katte " + kyte_x3_ip)
            sys.exit(1)

        if k1_temp > toa_temp_max:
            logging.info("K1 temperatuur on " + k1_temp_str +". See on korgem kui "+ toa_temp_max_str +" - Kyte valjas")
            try:
                lylita_sisse(kyte_x3_ip,"0")
                sys.exit(1)
            except Exception as e:
                logging.info("turuhind < kyte_saast_hind - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        elif k2_temp > toa_temp_max:
            logging.info("K2 temperatuur on " + k2_temp_str +". See on korgem kui "+ toa_temp_max_str +" - Kyte valjas")

            try:
                lylita_sisse(kyte_x3_ip,"0")
                sys.exit(1)
            except Exception as e:
                logging.info("turuhind < kyte_saast_hind - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        elif kyte_x3_state:
            logging.info("K1 temperatuur on " + k1_temp_str + ", K2 temperatuur on " + k2_temp_str +". See on madalam kui "+ toa_temp_max_str +" - Kyte sees")
            try:
                lylita_valja(kyte_x3_ip,"0")
            except Exception as e:
                logging.info("turuhind < kyte_saast_hind - Ei saanud kytte IP -d katte " + kyte_x3_ip)

        else:
            logging.info("X3 oli juba valjas")


if __name__ == "__main__":
    main()
