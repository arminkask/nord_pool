#!/usr/bin/python3
import requests
import json
import datetime
import time
import logging
import os
import sys
import configparser

#Variables
#If set to 1 then run else exit 
run = 1
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
k0_temp_id = config['SERVER']['0K_TEMP_ID']
k1_temp_id = config['SERVER']['1K_TEMP_ID']
k2_temp_id = config['SERVER']['2K_TEMP_ID']
pool_temp_id = config['SERVER']['POOL_TEMP_ID']

##Prices
kyte_boiler_max_hind = 600.0
kyte_saast_hind = 200.0
bassinikytte_hind = 100.0

##Temps
vee_temp_max = float(20.2)
toa_temp_max = float(20.5)
p_temp_ok = float(18.0)
k0_temp_ok = float(19.0)
k1_temp_ok = float(19.0)
k2_temp_ok = float(19.0)



logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    filename=logfile,
    filemode='a',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def get_price():
       curDT = datetime.datetime.utcnow()
       date_time = curDT.strftime("%Y-%m-%dT%H")
       url = "https://dashboard.elering.ee/api/nps/price?start=" + date_time + "%3A00%3A00.999Z&end=" + date_time + "%3A00%3A00.999Z"
       response = requests.get(url)
       data = response.text
       parsed = json.loads(data)
       json_file = open(apidata,"w")
       json_file.write(data)
       rates = parsed["data"]["ee"][0]
       ee_rate = rates.get('price')
       #logging.info(+ date_time + "Hind on "  str(ee_rate) )
       return ee_rate

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

def lylita_sisse(ip):
       url = "http://"+ ip +"/rpc"
       headers = {'Content-Type': 'application/x-www-form-urlencoded'}
       data = '{"id":1,"method":"Switch.Set","params":{"id":0,"on":true}}'
       switch_on =  requests.post(url, headers=headers, data=data)
       return switch_on

def lylita_valja(ip):
       url = "http://"+ ip +"/rpc"
       headers = {'Content-Type': 'application/x-www-form-urlencoded'}
       data = '{"id":1,"method":"Switch.Set","params":{"id":0,"on":false}}'
       switch_off =  requests.post(url, headers=headers, data=data)
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

def get_room_temp_from_cloud(cloud_id):
        body = {
                'id': cloud_id,
                'auth_key': cloud_token
               }
        try:
            req = requests.post('https://' + cloud_host + '/device/status', data=body)
            data = {}
            data = json.loads(req.text)
            temp = data["data"]["device_status"]["temperature:0"]["tC"]
            temp_float = float(temp)
            return temp_float

        except Exception as e:
            logging.info(str(e) + " cloud ID " + cloud_id)
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
    k0_temp_str = str(k0_temp)
    k1_temp_str = str(k1_temp)
    k2_temp_str = str(k2_temp)
    p_temp_str = str(p_temp)
    toa_temp_max_str = str(toa_temp_max)
    
    """ Kontrollime basseini temperatuuri ja hinda"""

    if turuhind_int > bassinikytte_hind_int:
          logging.info("Turuhind " + turuhind_str + " on korgem kui hea hind " + bassinikytte_hind_str +  "  - Basseinikyte valjas")
          try:
              lylita_valja(bassein_ip)
              bassein_state = False
          except Exception as e:
              logging.info( + turuhind_int + "> "+ bassinikytte_hind_int +"- Ei saanud basseini IP -d katte " + bassein_ip)

    else:
          logging.info("Turuhind " + turuhind_str + " on madalam kui hea hind " + bassinikytte_hind_str + "  - Kontrollime vee temperatuuri")
          basseini_temp = get_pool_temp(bassein_vee_temp_ip)
          if basseini_temp < vee_temp_max:
              try:
                  basseini_temp_str = str(basseini_temp)
                  lylita_sisse(bassein_ip)
                  bassein_state = True
                  logging.info("Basseini temperatuur " + basseini_temp_str + " on madalam kui " + vee_temp_max_str + " - Basseinikyte sees")

              except Exception as e:
                  logging.info(+ basseini_temp + " <  " + vee_temp_max + "- Ei saanud basseini IP -d katte " + bassein_ip)

          elif basseini_temp == vee_temp_max:
              try:
                  basseini_temp_str = str(basseini_temp)
                  lylita_sisse(bassein_ip)
                  bassein_state = True
                  logging.info("Basseini temperatuur " + basseini_temp_str + " on vordne " + vee_temp_max_str + " - Basseinikyte sees")

              except Exception as e:
                  logging.info(+ basseini_temp + " = " + vee_temp_max + "- Ei saanud basseini IP -d katte " + bassein_ip)

          else:
              try:
                  basseini_temp_str = str(basseini_temp)
                  lylita_valja(bassein_ip)
                  bassein_state = False
                  logging.info("Basseini temperatuur " + basseini_temp_str + " on korgem kui " + vee_temp_max_str + " - Basseinikyte valjas")
              except Exception as e:
                  logging.info("basseini_temp > vee_temp_max - Ei saanud basseini IP -d katte " + bassein_ip)

    
    """ Kui turuhind on korgem kui kyte_boiler_max_hind_int, siis lülita kyte ja boiler välja """

    if turuhind_int > kyte_boiler_max_hind_int:
          logging.info("Turuhind " + turuhind_str + " on korgem kui kytte max hind " + kyte_boiler_max_hind_str +  "  - Kyte ja boiler lyliti valjas")

          try:
              lylita_valja(boiler_ip)
              boiler_state = False
          except Exception as e:
              logging.info("turuhind > kyte_boiler_max_hind - Ei saanud boileri IP -d katte " + boiler_ip)

          try:
              lylita_sisse(kyte_x3_ip)
              kyte_x3_state = True

          except Exception as e:
              logging.info("turuhind > kyte_boiler_max_hind - Ei saanud kytte IP -d katte " + kyte_x3_ip)

    else:
        logging.info("Turuhind " + turuhind_str + " on madalam kui kytte hea hind " + kyte_boiler_max_hind_str + "  - Kyte ja boiler lyliti sees")

        try:
            lylita_sisse(boiler_ip)
            boiler_state = True
        except Exception as e:
            logging.info("turuhind <  kyte_boiler_max_hind_int - Ei saanud boileri IP -d katte " + boiler_ip)

    """Kui turuhind on kalli ja madala vahel, siis lylita sisse saastureziim"""

    if turuhind_int < kyte_boiler_max_hind_int and turuhind_int > kyte_saast_hind_int:
        logging.info("Turuhind " + turuhind_str + " on suurem kui kytte saastu hind " + kyte_saast_hind_str + ",kuid madalam kui " + kyte_boiler_max_hind_str + "  - Vaatame temperatuure")


        try:
            lylita_valja(kyte_x3_ip)
            kyte_x3_state = False
            logging.info("Reset X3 - Kytte X3 valjas")

        except Exception as e:
                logging.info("Reset X3 - Ei saanud IP -d katte " + kyte_x3_ip)

        if k0_temp < k0_temp_ok:
            try:
                lylita_sisse(kyte_x2_ip)
                kyte_x2_state = True
                logging.info("0 korruse temperatuur on madal " + k0_temp_str + " - Kyte sees saastureziimis")

            except Exception as e:
                logging.info("k0_temp < k0_temp_ok - Ei saanud kytte IP -d katte " + kyte_x2_ip)

        elif k1_temp < k1_temp_ok:
            try:
                lylita_sisse(kyte_x2_ip)
                kyte_x2_state = True
                logging.info("1 korruse temperatuur on madal " + k1_temp_str + " - Kyte sees saastureziimis")

            except Exception as e:
               logging.info("1 korruse temperatuur on madal - Ei saanud kytte IP -d katte " + kyte_x2_ip)

        elif k2_temp < k2_temp_ok:
            try:
                lylita_sisse(kyte_x2_ip)
                kyte_x2_state = True
                logging.info("2 korruse temperatuur on madal " + k2_temp_str + " - Kyte sees saastureziimis")
            except Exception as e:
                logging.info("2 korruse temperatuur on madal - Ei saanud kytte IP -d katte " + kyte_x2_ip)

#        elif p_temp < p_temp_ok:
#            try:
#                lylita_sisse(kyte_x2_ip)
#                kyte_x2_state = True
#                logging.info("Basseiniruumi temperatuur on madal " + p_temp_str + " - Kyte sees saastureziimis")
#
#            except Exception as e:
#               logging.info("Basseiniruumi temperatuur on madal - Ei saanud kytte IP -d katte " + kyte_x2_ip)

        else:
            try:
                lylita_valja(kyte_x2_ip)
                kyte_x2_state = False
                logging.info("Temperatuurid ruumides on korgemad kui minimaalne temp - Kytte X2 valjas")

            except Exception as e:
                logging.info("Temperatuurid ruumides on korgemad kui minimaalne temp -  Ei saanud kytte IP -d katte " + kyte_x2_ip)

            try:
                lylita_sisse(kyte_x3_ip)
                kyte_x3_state = True
                logging.info("Temperatuurid ruumides on korgemad kui minimaalne temp -  X3 sees(Kyte ise valjas)")

            except Exception as e:
                logging.info("Kytted korras - Ei saanud kytte IP -d katte " + kyte_x3_ip)

    """ Kui turuhind on madalam, kui kyte_saast_hind_int"""

    if turuhind_int < kyte_saast_hind_int:
       logging.info("Turuhind " + turuhind_str + " on madalam kui kytte saastu hind " + kyte_saast_hind_str + " - Kontrollime temperatuure")

       try:
           lylita_valja(kyte_x3_ip)
           kyte_x3_state = False
           logging.info("Reset X3 - Kytte X3 valjas")

       except Exception as e:
           logging.info("Turuhind " + turuhind_str + " on madalam kui kytte saastu hind " + kyte_saast_hind_str + "Reset X3 - Ei saanud IP -d katte " + kyte_x3_ip)

       try:
           lylita_valja(kyte_x2_ip)
           kyte_x2_state = False
           logging.info("Reset X2 - Kytte X2 valjas")

       except Exception as e:
           logging.info("Turuhind " + turuhind_str + " on madalam kui kytte saastu hind " + kyte_saast_hind_str + "Reset X2 - Ei saanud IP -d katte " + kyte_x2_ip)


       if k1_temp > toa_temp_max:
          logging.info("K1 temperatuur on " + k1_temp_str +". See on korgem kui "+ toa_temp_max_str +" - Kyte valjas")

          try:
              lylita_sisse(kyte_x3_ip)
              kyte_x3_state = True

          except Exception as e:
              logging.info("turuhind < kyte_saast_hind - Ei saanud kytte IP -d katte " + kyte_x3_ip)

       elif k2_temp > toa_temp_max and kyte_x3_state == False:
          logging.info("K2 temperatuur on " + k2_temp_str +". See on korgem kui "+ toa_temp_max_str +" - Kyte valjas")

          try:
              lylita_sisse(kyte_x3_ip)
              kyte_x3_state = True

          except Exception as e:
              logging.info("turuhind < kyte_saast_hind - Ei saanud kytte IP -d katte " + kyte_x3_ip)

       else:
            logging.info("K1 temperatuur on " + k1_temp_str + ", K2 temperatuur on " + k2_temp_str +". See on madalam kui "+ toa_temp_max_str +" - Kyte sees")

if __name__ == "__main__":
    main()

