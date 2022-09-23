#!/usr/bin/python3
import requests
import json
import datetime
import time
import logging
import os
import sys

kyte_boiler_hind = 700.0
bassinikytte_hind = 80.0
bassein_ip = "192.168.1.250"
boiler_ip = "192.168.1.249"
kyte_ip = "192.168.1.248"
bassein_vee_temp_ip ="192.168.1.240"
vee_temp_max = float(20.2)

logfile = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'log')
apidata = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'api.json')

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
       return ee_rate


def lylita_sisse(ip):
       url = "http://"+ ip +"/rpc"
       headers = {'Content-Type': 'application/x-www-form-urlencoded'}
       data = data = '{"id":1,"method":"Switch.Set","params":{"id":0,"on":true}}'
       switch_on =  requests.post(url, headers=headers, data=data)
       return switch_on


def lylita_valja(ip):
       url = "http://"+ ip +"/rpc"
       headers = {'Content-Type': 'application/x-www-form-urlencoded'}
       data = data = '{"id":1,"method":"Switch.Set","params":{"id":0,"on":false}}' 
       switch_off =  requests.post(url, headers=headers, data=data)
       return switch_off
 
def get_pool_temp(ip):
       url = "http://"+ ip +"/status"
       headers = {'Content-Type': 'application/json'}
       req = requests.get(url, headers=headers)

       try:
           data = {}
           data = json.loads(req.text)
           temp = data["ext_temperature"]["0"]["tC"]
           temp_int = float(temp)
           return temp_int

       except Exception as e:
           logging.info("Ei saanud vee temperatuuri katte ")
           logging.info("Exception: %s" % str(e))
           return 100



def main():


    try:
        turuhind = get_price()

    except Exception as e:
        logging.info("Ei saanud turuhinda katte ")
        logging.info("Exception: %s" % str(e))    
        sys.exit(1) 

    

    turuhind_str = str(turuhind)
    bassinikytte_hind_str = str(bassinikytte_hind)
    kyte_boiler_hind_str = str(kyte_boiler_hind)
    vee_temp_max_str = str(vee_temp_max)

    turuhind_int = int(turuhind)
    bassinikytte_hind_int = int(bassinikytte_hind)
    kyte_boiler_hind_int = int(kyte_boiler_hind)


    if turuhind_int > kyte_boiler_hind_int:
          logging.info("Turuhind " + turuhind_str + " on korgem kui kytte hea hind " + kyte_boiler_hind_str +  "  - Kyte ja boiler lyliti valjas")

          try:
              lylita_valja(boiler_ip)
          except Exception as e:
              logging.info("Ei saanud boileri IP -d katte " + boiler_ip)

          try:
              lylita_sisse(kyte_ip)
          except Exception as e:
              logging.info("Ei saanud kytte IP -d katte " + kyte_ip)

    else:
          logging.info("Turuhind " + turuhind_str + " on madalam kui kytte hea hind " + kyte_boiler_hind_str + "  - Kyte ja boiler lyliti sees")
          try:
              lylita_sisse(boiler_ip)
          except Exception as e:
              logging.info("Ei saanud boileri IP -d katte " + boiler_ip)

          try:
              lylita_valja(kyte_ip)
          except Exception as e:
              logging.info("Ei saanud kytte IP -d katte " + kyte_ip)

    if turuhind_int > bassinikytte_hind_int:
          logging.info("Turuhind " + turuhind_str + " on korgem kui hea hind " + bassinikytte_hind_str +  "  - Basseinikyte valjas")
          try:
              lylita_valja(bassein_ip)
          except Exception as e:
              logging.info("Ei saanud basseini IP -d katte " + bassein_ip)

    else:
          logging.info("Turuhind " + turuhind_str + " on madalam kui hea hind " + bassinikytte_hind_str + "  - Kontrollime vee temperatuuri")
          basseini_temp = get_pool_temp(bassein_vee_temp_ip)
          if basseini_temp < vee_temp_max:
              try:
                  basseini_temp_str = str(basseini_temp)
                  lylita_sisse(bassein_ip)
                  logging.info("Basseini temperatuur " + basseini_temp_str + " on madalam kui " + vee_temp_max_str + " - Basseinikyte sees")

              except Exception as e:
                  logging.info("Ei saanud basseini IP -d katte " + bassein_ip)

          elif basseini_temp == vee_temp_max:
              try:
                  basseini_temp_str = str(basseini_temp)
                  lylita_sisse(bassein_ip)
                  logging.info("Basseini temperatuur " + basseini_temp_str + " on vordne " + vee_temp_max_str + " - Basseinikyte sees")
              except Exception as e:
                  logging.info("Ei saanud basseini IP -d katte " + bassein_ip)

          else:
              try:
                  basseini_temp_str = str(basseini_temp)
                  lylita_valja(bassein_ip)
                  logging.info("Basseini temperatuur " + basseini_temp_str + " on korgem kui " + vee_temp_max_str + " - Basseinikyte valjas")
              except Exception as e:
                  logging.info("Ei saanud basseini IP -d katte " + bassein_ip)


               

if __name__ == "__main__":
    main()
