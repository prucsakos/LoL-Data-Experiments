from enum import Enum
import time
import requests


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

PLATFORMS = list(
        filter(
            lambda x: len(x) < 5,
            [
                value
                for name, value in vars(Platform).items()
                if isinstance(value, str)
            ],
        )
    )

class Region:
    AMERICAS = "americas"
    ASIA = "asia"
    EUROPE = "europe"
    SEA = "sea"

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

class Queue:
    RANKED_SOLO = "RANKED_SOLO_5x5"
    RANKED_FLEX = "RANKED_FLEX_SR"
    RANKED_TFT = "RANKED_TFT"


class RiotApiInterface:
    """Get data from riot api. Methods implemented only for nececcary endpoints."""

    def __init__(
        self, api_key, platform, default_rate_limit=False
    ):
        self.api_key = api_key
        self.platform = platform
        self.region = PLATFORM_TO_REGION[platform]
        self.base_lol_url = f"https://{platform}.api.riotgames.com/lol/"
        self.base_lol_region_url = f"https://{self.region}.api.riotgames.com/lol/"
        self.headers = {"X-Riot-Token": api_key}

        self.last_call_on_endpoints = {}
        self.default_rate_limit = default_rate_limit

    def rate_limiter(request_per_second):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                if not self.default_rate_limit:
                    last_call_time = self.last_call_on_endpoints.get(func.__name__, 0)
                    delta_seconds = time.time() - last_call_time
                    wait_time = 1 / request_per_second - delta_seconds
                    if wait_time > 0:
                        time.sleep(wait_time)
                else:
                    # use default rate limit 100 request per 2 minute
                    default_request_per_second = 100 / (2 * MINUTE + 1)
                    last_call_time = self.last_call_on_endpoints.get("default", 0)
                    delta_seconds = time.time() - last_call_time
                    wait_time = 1 / default_request_per_second - delta_seconds
                    if wait_time > 0:
                        time.sleep(wait_time)

                result = func(self, *args, **kwargs)
                self.last_call_on_endpoints[func.__name__] = time.time()
                self.last_call_on_endpoints["default"] = time.time()
                return result

            return wrapper

        return decorator

    def handle_response(self, response):
        if response.status_code == 200:
            return response.json()
        else:
            error_code = response.status_code
            error_description = ERROR_CODES.get(error_code, "Unknown Error")
            raise Exception(f"Error {error_code}: {error_description}")

    @rate_limiter(request_per_second=500 / 10 * MINUTE)
    def get_challenger_leagues(self, queue):
        url = f"{self.base_lol_url}league/v4/challengerleagues/by-queue/{queue}"
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)

    @rate_limiter(request_per_second=500 / 10 * MINUTE)
    def get_grandmaster_leagues(self, queue):
        url = f"{self.base_lol_url}league/v4/grandmasterleagues/by-queue/{queue}"
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)

    @rate_limiter(request_per_second=500 / 10 * MINUTE)
    def get_master_leagues(self, queue):
        url = f"{self.base_lol_url}league/v4/masterleagues/by-queue/{queue}"
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)

    @rate_limiter(request_per_second=500 / (2 * MINUTE))
    def get_league_entries(self, queue, division, tier):
        url = f"{self.base_lol_url}league/v4/entries/{queue}/{tier}/{division}"
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)

    @rate_limiter(request_per_second=500 / (2 * MINUTE))
    def get_league_by_id(self, league_id):
        url = f"{self.base_lol_url}league/v4/leagues/{league_id}"
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)

    @rate_limiter(request_per_second=1600 / 1 * MINUTE)
    def get_summoner_by_encrypted_summoner_id(self, encrypted_summoner_id):
        url = f"{self.base_lol_url}summoner/v4/summoners/{encrypted_summoner_id}"
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)

    @rate_limiter(request_per_second=2_000 / 10)
    def get_matchhistory_by_puuid(
        self,
        encrypted_puuid,
        start=0,
        count=20,
        queue=None,
        type=None,
        endTime=None,
        startTime=None,
    ):
        parameters = []
        url = f"{self.base_lol_region_url}match/v5/matches/by-puuid/{encrypted_puuid}/ids?"
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
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)

    @rate_limiter(request_per_second=2_000 / 10)
    def get_match_by_id(self, match_id):
        url = f"{self.base_lol_region_url}match/v5/matches/{match_id}"
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)

    @rate_limiter(request_per_second=2_000 / 10)
    def get_match_timeline_by_id(self, match_id):
        url = f"{self.base_lol_region_url}match/v5/matches/{match_id}/timeline"
        response = requests.get(url, headers=self.headers)
        return self.handle_response(response)
