import requests
import tqdm
import threading
#from requests.auth import HTTPBasicAuth 
from RiotApiInterface import *

proxy = "88.216.34.192:50101"

proxies = {
    'http': proxy,
    'https': proxy
}

rai = RiotApiInterface()


try:
#    response = requests.get('https://www.example.com', proxies=proxies, timeout=2, auth=('prucsakos', 'iWPH2VRWIo'))
    #response = rai.http_get_challenger_leagues("RANKED_SOLO_5x5", "euw1", "RGAPI-aeff7db7-b38e-43c1-937c-ddc949a18ad0")
    response = rai.get_challenger_leagues("RANKED_SOLO_5x5", "euw1", "RGAPI-aeff7db7-b38e-43c1-937c-ddc949a18ad0")
    print(response)
except Exception as e:
    print('Error:', e)
