from enum import Enum
import time
import requests
import math


MINUTE = 60

ERROR_CODES = {
    400: "Bad Request: There is a syntax error in the request.",
    401: "Unauthorized: The request does not contain the necessary authentication credentials.",
    403: "Forbidden: The server refuses to authorize the request.",
    404: "Not Found: The server has not found a match for the API request.",
    415: "Unsupported Media Type: The body of the request is in a format that is not supported.",
    429: "Rate Limit Exceeded: The application has exhausted its maximum number of API calls allowed.",
    500: "Internal Server Error: An unexpected condition prevented the server from fulfilling the request.",
    503: "Service Unavailable: The server is currently unavailable to handle requests.",
}


class Platform:
    BR1 = "br1"
    EUN1 = "eun1"
    EUW1 = "euw1"
    JP1 = "jp1"
    KR = "kr"
    LA1 = "la1"
    LA2 = "la2"
    NA1 = "na1"
    OC1 = "oc1"
    TR1 = "tr1"
    RU = "ru"
    PH2 = "ph2"
    SG2 = "sg2"
    TH2 = "th2"
    TW2 = "tw2"
    VN2 = "vn2"


PLATFORMS = [
    Platform.BR1,
    Platform.EUN1,
    Platform.EUW1,
    Platform.JP1,
    Platform.KR,
    Platform.LA1,
    Platform.LA2,
    Platform.NA1,
    Platform.OC1,
    Platform.TR1,
    Platform.RU,
    Platform.PH2,
    Platform.SG2,
    Platform.TH2,
    Platform.TW2,
    Platform.VN2,
]


class Region:
    AMERICAS = "americas"
    ASIA = "asia"
    EUROPE = "europe"
    SEA = "sea"


REGIONS = [Region.AMERICAS, Region.ASIA, Region.EUROPE, Region.SEA]

PLATFORM_TO_REGION = {
    Platform.EUN1: Region.EUROPE,
    Platform.EUW1: Region.EUROPE,
    Platform.TR1: Region.EUROPE,
    Platform.RU: Region.EUROPE,
    Platform.BR1: Region.AMERICAS,
    Platform.LA1: Region.AMERICAS,
    Platform.LA2: Region.AMERICAS,
    Platform.NA1: Region.AMERICAS,
    Platform.JP1: Region.ASIA,
    Platform.KR: Region.ASIA,
    Platform.VN2: Region.SEA,
    Platform.TW2: Region.SEA,
    Platform.TH2: Region.SEA,
    Platform.SG2: Region.SEA,
    Platform.OC1: Region.SEA,
    Platform.PH2: Region.SEA,
}

REGION_TO_PLATFORMS = {
    Region.EUROPE: [Platform.EUN1, Platform.EUW1, Platform.TR1, Platform.RU],
    Region.AMERICAS: [Platform.BR1, Platform.LA1, Platform.LA2, Platform.NA1],
    Region.ASIA: [Platform.JP1, Platform.KR],
    Region.SEA: [
        Platform.VN2,
        Platform.TW2,
        Platform.TH2,
        Platform.SG2,
        Platform.OC1,
        Platform.PH2,
    ],
}


class Queue:
    RANKED_SOLO = "RANKED_SOLO_5x5"
    RANKED_FLEX = "RANKED_FLEX_SR"
    RANKED_TFT = "RANKED_TFT"


QUEUES = [Queue.RANKED_SOLO, Queue.RANKED_FLEX, Queue.RANKED_TFT]

API_TO_PROXY_MAP = {}


def assign_apikeys_to_proxies(proxy_list, api_keys, leave_first=False):
    assert len(proxy_list) >= (len(api_keys)-1 if leave_first else len(api_keys)), "Not enough proxies for api keys"
    api_size = len(api_keys) - 1 if leave_first else len(api_keys)
    ceiled_step = math.ceil(len(proxy_list) / api_size)
    for i, api in enumerate(api_keys):
        if leave_first and i == 0:
            API_TO_PROXY_MAP[api] = None
            continue
        
        API_TO_PROXY_MAP[api] = proxy_list[
            i * ceiled_step : min((i + 1) * ceiled_step, len(proxy_list))
        ]


def get_proxies(api_key):
    return API_TO_PROXY_MAP.get(api_key, None)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
]

API_TO_AGENT_MAP = {}


def get_user_agent(api_key):
    agent = API_TO_AGENT_MAP.get(api_key, None)
    if not agent:
        agent = USER_AGENTS[len(API_TO_AGENT_MAP.items())]
        API_TO_AGENT_MAP[api_key] = agent
    return agent


class RiotApiInterface:
    """Get data from riot api. Methods implemented only for nececcary endpoints."""

    def get_header(self, api_key):
        return {
            "X-Riot-Token": api_key,
            "User-Agent": get_user_agent(api_key),
        }

    def get_platform_url(self, platform):
        return f"https://{platform}.api.riotgames.com/lol/"

    def get_region_url(self, region):
        return f"https://{region}.api.riotgames.com/lol/"

    def handle_response(self, response):
        if response.status_code == 200:
            return response.json()
        else:
            error_code = response.status_code
            error_description = ERROR_CODES.get(error_code, "Unknown Error")
            print(f"Error {error_code} for URL: {response.url}")
            print(f"Response content: {response.text}")
            raise Exception(f"Error for {error_code}: {error_description}")

    def _get_resposne(self, url, api_key):
        #print(f"Requesting {url}, with api key {api_key}")
        if len(API_TO_AGENT_MAP.items()) == 0:
            return requests.get(url, headers=self.get_header(api_key))

        # handle timeout errors with multiple proxies
        proxies = get_proxies(api_key)
        # just run without proxy if returned none
        if not proxies:
            return requests.get(url, headers=self.get_header(api_key))
        
        for proxy in proxies:
            print(f"Using proxy {proxy}")
            try:
                return requests.get(
                    url,
                    headers=self.get_header(api_key),
                    proxies={"http": proxy, "https": proxy},
                )
            except (requests.RequestException, requests.Timeout) as e:
                #print(f"Error with proxy {proxy}")
                API_TO_PROXY_MAP[api_key].remove(proxy)
                #print(
                #    f"Removed proxy {proxy}, remaining: {len(API_TO_PROXY_MAP[api_key])}"
                #)

    def get_challenger_leagues(self, queue, platform, api_key):
        url = f"{self.get_platform_url(platform)}league/v4/challengerleagues/by-queue/{queue}"
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)
    
    def http_get_challenger_leagues(self, queue, platform, api_key):
        url = f"{self.get_platform_url(platform)}league/v4/challengerleagues/by-queue/{queue}"
        url = url.replace("https://", "http://")
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)

    def get_grandmaster_leagues(self, queue, platform, api_key):
        url = f"{self.get_platform_url(platform)}league/v4/grandmasterleagues/by-queue/{queue}"
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)

    def get_master_leagues(self, queue, platform, api_key):
        url = (
            f"{self.get_platform_url(platform)}league/v4/masterleagues/by-queue/{queue}"
        )
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)

    def get_league_entries(self, platform, queue, division, tier, api_key):
        url = f"{self.get_platform_url(platform)}league/v4/entries/{queue}/{tier}/{division}"
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)

    def get_league_by_id(self, league_id, platform, api_key):
        url = f"{self.get_platform_url(platform)}league/v4/leagues/{league_id}"
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)

    def get_summoner_by_encrypted_summoner_id(
        self, encrypted_summoner_id, platform, api_key
    ):
        url = f"{self.get_platform_url(platform)}summoner/v4/summoners/{encrypted_summoner_id}"
        response = self._get_resposne(url, api_key)
        return self.handle_response(response)

    def get_matchhistory_by_puuid(
        self,
        region,
        encrypted_puuid,
        api_key,
        start=0,
        count=20,
        queue=None,
        type=None,
        endTime=None,
        startTime=None,
    ):
        parameters = []
        url = f"{self.get_region_url(region)}match/v5/matches/by-puuid/{encrypted_puuid}/ids?"
        if queue:
            parameters.append(f"queue={queue}")
        if type:
            parameters.append(f"type={type}")
        if endTime:
            parameters.append(f"endTime={endTime}")
        if startTime:
            parameters.append(f"startTime={startTime}")
        parameters.append(f"start={start}")
        parameters.append(f"count={count}")
        url += "&".join(parameters)
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)

    def get_match_by_id(self, region, match_id, api_key):
        url = f"{self.get_region_url(region)}match/v5/matches/{match_id}"
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)

    def get_match_timeline_by_id(self, region, match_id, api_key):
        url = f"{self.get_region_url(region)}match/v5/matches/{match_id}/timeline"
        response = requests.get(url, headers=self.get_header(api_key))
        return self.handle_response(response)
