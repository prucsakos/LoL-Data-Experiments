import queue
import time
import os
import threading
import datetime
import json
import sqlite3
from typing import List
from RiotApiInterface import *
import pandas as pd
from tqdm import tqdm
import multiprocessing
import sys


def convert_date_to_string(year, month, day):
    return str(int(datetime.datetime(year, month, day).timestamp()))


def main():
    out = "data/data.db"
    start_date = convert_date_to_string(2024, 7, 1)
    
    # api
    api_keys = open("riot.txt", "r").read().split("\n")
    api_keys = list(filter(lambda x: len(x) > 5, api_keys))

    # proxies
    #proxies = open("proxies.txt", "r").read().split("\n")
    #proxies = list(filter(lambda x: len(x) > 5, proxies))
    #assign_apikeys_to_proxies(proxies, api_keys, leave_first=False)

    # START WRITER
    terminate = False
    db_writer_queue = queue.Queue()
    # start db writer
    db_writer = threading.Thread(
        target=worker_write_data_to_db, args=(out, db_writer_queue, terminate)
    )
    db_writer.start()

    # THREAD FOR EACH REGION
    ts = []
    for region in REGIONS:
        print(f"Starting scraper for {region}")
        t = threading.Thread(target=start_scraper_for_region, args=(api_keys, region, db_writer_queue, start_date))
        t.start()
        ts.append(t)
        
    [t.join() for t in ts]
    while not db_writer_queue.empty():
        time.sleep(1)
    terminate = True   
    
def main_multiproc():
    out = "data/data.db"
    start_date = convert_date_to_string(2024, 7, 1)
    
    # api
    api_keys = open("riot.txt", "r").read().split("\n")
    api_keys = list(filter(lambda x: len(x) > 5, api_keys))

    # proxies (commented out since they are not used)
    #proxies = open("proxies.txt", "r").read().split("\n")
    #proxies = list(filter(lambda x: len(x) > 5, proxies))
    #assign_apikeys_to_proxies(proxies, api_keys, leave_first=False)

    # START WRITER
    manager = multiprocessing.Manager()
    db_writer_queue = manager.Queue()
    terminate = manager.Value('b', False)

    # start db writer
    db_writer = multiprocessing.Process(
        target=worker_write_data_to_db, args=(out, db_writer_queue, terminate)
    )
    db_writer.start()

    # PROCESS FOR EACH REGION
    processes = []
    for region in REGIONS:
        print(f"Starting scraper for {region}")
        p = multiprocessing.Process(target=start_scraper_for_region, args=(api_keys, region, db_writer_queue, start_date))
        p.start()
        processes.append(p)
        
    for p in processes:
        p.join()
    while not db_writer_queue.empty():
        time.sleep(1)
    terminate.value = True
    db_writer.join() 
    
def main_arg():
    out = "data/data.db"
    start_date = convert_date_to_string(2024, 7, 1)
    
    # api
    api_keys = open("riot.txt", "r").read().split("\n")
    api_keys = list(filter(lambda x: len(x) > 5, api_keys))

    # proxies
    #proxies = open("proxies.txt", "r").read().split("\n")
    #proxies = list(filter(lambda x: len(x) > 5, proxies))
    #assign_apikeys_to_proxies(proxies, api_keys, leave_first=False)

    # START WRITER
    terminate = False
    db_writer_queue = queue.Queue()
    # start db writer
    db_writer = threading.Thread(
        target=worker_write_data_to_db, args=(out, db_writer_queue, terminate)
    )
    db_writer.start()


    region = sys.argv[1]
    print(f"Starting scraper for {region}")
    t = threading.Thread(target=start_scraper_for_region, args=(api_keys, region, db_writer_queue, start_date))
    t.start()
    t.join()
    
    while not db_writer_queue.empty():
        time.sleep(1)
    terminate = True
    
    print("All jobs done, waiting for db writer to finish")    
    
    
def start_scraper_for_region(api_keys, region, db_writer_queue, start_date):    
    p = RiotDataScraper_2024_07(api_keys,  region)
    p.start(db_writer_queue, start_date=start_date)

def worker_write_data_to_db(db_path, data_queue, terminate):

    db = sqlite3.connect(db_path)

    while not terminate:
        try:
            data = data_queue.get(block=False, timeout=None)

            game_data = pd.json_normalize(data)
            game_data.drop(
                ["metadata.participants", "info.participants", "info.teams"],
                axis=1,
                inplace=True,
            )

            # preprocess data
            game_participants = pd.json_normalize(
                data, record_path=["info", "participants"], max_level=0, sep="."
            )
            game_participants.drop(
                ["challenges", "missions", "perks"], axis=1, inplace=True
            )
            game_participants["gameId"] = data["info"]["gameId"]

            # out to sqlite
            game_data.to_sql(
                con=db, name="game_data", if_exists="append", index=False
            )
            game_participants.to_sql(
                con=db, name="game_participants", if_exists="append", index=False
            )

        except queue.Empty as e:
            time.sleep(0.1)
        except Exception as e:
            print(e)

class RiotDataScraper_2024_07:
    """There steps
    Maintain a table tracking rate rimit per endpoint.
    Main thread reads the table and creates jobs. Pushes jobs to a queue.
    Worker threads obtain jobs and complete them.
    """

    def __init__(self, api_keys: List[str], region):
        self.api_keys = api_keys
        self.rai = RiotApiInterface()
        self.region = region
        self.region_platforms = REGION_TO_PLATFORMS[region]

        # use default rate limit 100 request per 2 minute
        self.call_interval = (2 * MINUTE + 1) / 100.0
        
        # report time
        self.report_time = time.time()

        # matchhistory and matchbyid are actually from the same endpoint
        self.rai_funcs = [
            self.rai.get_summoner_by_encrypted_summoner_id,
            #self.rai.get_matchhistory_by_puuid,     -> UNIFIED WITH SUMMID
            self.rai.get_match_by_id,
        ]
        # dict to store last endpoint call times and locks
        self.request_timepoints = {
            (api_key, func): time.time()
            for api_key in self.api_keys
            for func in self.rai_funcs
        }

        # dict to store process datas
        self.process_data = {}

        # set for matchids
        self.unique_matchids = set()
        self.lock_matchids = threading.Lock()

        print(
            "Initialize RiotDataScraper for {} \nIncluded platforms: {} \
            \nRate limit set is 1 call every {} second, which is {} call per second.".format(
                region,
                ", ".join(self.region_platforms),
                self.call_interval,
                1 / self.call_interval,
            )
        )
        #print("Scheduled endpoints: ", self.request_timepoints.keys())

    def _endpoint_str(self, func_name, location):
        return f"{func_name}_{location}"

    def start(self, db_writer_queue, start_date):
        # queues for main thread
        summIds = queue.Queue()
        puuids = queue.Queue()
        matchIds = queue.Queue()
        matchdata = db_writer_queue

        # init progress bars
        #puuid_progress = tqdm(total=0, desc="PUUIDs Processed for {}".format(self.region))
        #match_progress = tqdm(total=0, desc="Matches Processed For {}".format(self.region))
        #summIds_progresses = {api: tqdm(total=0, desc=f"SummIds Processed {api[:5]}") for api in self.api_keys}

        # Put (summid, platform) into summIds queue
        top_tier_players = {}
        for api in self.api_keys:
            for platform in self.region_platforms:
                for q in ["RANKED_SOLO_5x5", "RANKED_FLEX_SR"]:
                    #print(f"Getting challenger leagues for {q} on {platform}, api: {api}")
                    resp = self.rai.get_challenger_leagues(q, platform, api)
                    resp2 = self.rai.get_grandmaster_leagues(q, platform, api)
                    for entry in resp["entries"] + resp2["entries"]:
                        key = (platform, entry["leaguePoints"], entry["rank"], entry["wins"], entry["losses"], entry["veteran"], entry["inactive"], entry["freshBlood"], entry["hotStreak"])
                        if not top_tier_players.get(key):
                            top_tier_players[key] = {}
                        if not top_tier_players[key].get(api):
                            top_tier_players[key][api] = []
                        top_tier_players.get(key).get(api).append(entry["summonerId"])

        # TEST - filter out most of items
        #top_tier_players = dict(list(top_tier_players.items())[:4])

        # update process data
        self.process_data["sumIdLen"] = sum([sum([len(_v) for _k, _v in v.items()]) for k, v in top_tier_players.items()])/len(self.api_keys)
        
        print("Full number of keys ", len(top_tier_players.keys()))
        print("Keys found by API ", sum([len(v.keys()) for k, v in top_tier_players.items()])/len(self.api_keys))
        print("Total summids", sum([sum([len(_v) for _k, _v in v.items()]) for k, v in top_tier_players.items()])/len(self.api_keys))


        # put them in for placeholders
        #[summIds.put(_) for keys in list(summIds_list.keys())]
        summId_per_api = math.ceil(len(top_tier_players.keys()) / len(self.api_keys))
        summId_idxes = {api: [i, i*summId_per_api, min((i+1)*summId_per_api, len(top_tier_players.keys()))] for i, api in enumerate(self.api_keys)}
        print("summId_idxes: ",summId_idxes)

        # list to be deterministic
        top_tier_players = list(top_tier_players.items())

        print("Starting data collection")
        # job distributor thread
        while (
            #not summIds.empty()
            len(summId_idxes.items()) > 0
            or not puuids.empty()
            or not matchIds.empty()
            or not matchdata.empty()
        ):
            #print("Condition states: ", len(summId_idxes.items()) > 0, not puuids.empty(), not matchIds.empty(), not matchdata.empty())
            scheduler_items = list(self.request_timepoints.items())
            # check if endpoints are free and there are jobs to be done
            for item in scheduler_items:
                if (
                    item[0][1] == self.rai.get_summoner_by_encrypted_summoner_id
                    and time.time() - item[1] > self.call_interval
                    #and not summIds.empty()
                    and summId_idxes.get(item[0][0], None)
                ):
                    api_key = item[0][0]
                    
                    # aqcuire item (bcs of concurrency)
                    #summId, platform = summIds.get()
                    summIdx = summId_idxes[api_key][1]
                    summId_idxes[api_key][1] += 1
                    # pop if no item left for this particular thread
                    if summId_idxes[api_key][1] >= summId_idxes[api_key][2]:
                        summId_idxes.pop(api_key)
                        
                    if not top_tier_players[summIdx][1].get(api_key, None):
                        continue
                    
                    summId = top_tier_players[summIdx][1][api_key][0]
                    platform = top_tier_players[summIdx][0][0]
                    #t = threading.Thread(
                    #    target=self.worker_summoner_id_to_puuid,
                    #    args=(platform, api_key, puuids, summId),
                    #)
                    t = threading.Thread(
                        target=self.worker_summid_to_matchids_unified,
                        args=(self.region, platform, api_key, matchIds, summId, start_date),
                    )
                    t.start()
                    self.request_timepoints[item[0]] = time.time()

                    # update process data
                    self.process_data["puuidLen"] = (
                        self.process_data.get("puuidLen", 0) + 1
                    )

                elif (  # turned off since unified with summid
                    item[0][1] == self.rai.get_matchhistory_by_puuid
                    and time.time() - item[1] > self.call_interval
                    and not puuids.empty()
                ):
                    puuid = puuids.get()
                    t = threading.Thread(
                        target=self.worker_puuid_to_matchids,
                        args=(self.region, puuid, matchIds, item[0][0], start_date),
                    )
                    t.start()
                    self.request_timepoints[item[0]] = time.time()
                    print("Getting matchids")
                    print(len(self.unique_matchids))

                elif (
                    item[0][1] == self.rai.get_match_by_id
                    and time.time() - item[1] > self.call_interval
                    and not matchIds.empty()
                    #and summIds.empty()
                    and not summId_idxes.get(item[0][0], None)
                    and puuids.empty()  # only start when all puuids are fetched and matchids are obtained (bcs it works from the match endpoint as well - rate limit issues)
                ):
                    # only unique matchIds
                    matchid = matchIds.get()
                    threading.Thread(
                        target=self.worker_matchid_to_matchdata,
                        args=(self.region, matchid, item[0][0], matchdata),
                    ).start()
                    self.request_timepoints[item[0]] = time.time()

                    # update metadata
                    self.process_data["matchDataLen"] = (
                        self.process_data.get("matchDataLen", 0) + 1
                    )

            # create / update tqdm progress bars for
            # 1. progress bar: self.process_data["puuidLen"] / self.process_data["sumIdLen"]
            # 2. progress bar: self.process_data["matchDataLen"] / len(self.unique_matchids)
            #puuid_progress.total = self.process_data.get("sumIdLen", 0)
            #puuid_progress.n = self.process_data.get("puuidLen", 0)
            #puuid_progress.refresh()

            #match_progress.total = len(self.unique_matchids)
            #match_progress.n = self.process_data.get("matchDataLen", 0)
            #match_progress.refresh()
            
            
            # report every 60 seconds: percentage, current n, total n
            
            puuid_total = self.process_data.get("sumIdLen", 0)
            puuid_n = self.process_data.get("puuidLen", 0)
            
            
            match_progress_total = len(self.unique_matchids)
            match_progress_n = self.process_data.get("matchDataLen", 0)
            
            if time.time() - self.report_time > 10:
                self.report_time = time.time()
                puuid_percentage = (puuid_n / (puuid_total+1)) * 100
                match_progress_percentage = (match_progress_n / (match_progress_total+1)) * 100
                if match_progress_percentage <= 95:
                    print(f"{self.region} | PUUIDs: {puuid_n}/{puuid_total} ({puuid_percentage:.2f}%), Match Data: {match_progress_n}/{match_progress_total} ({match_progress_percentage:.2f}%)")
            
            
            #for api, progress in summIds_progresses.items():
            #    if summId_idxes.get(api, None):
            #        progress.total = summId_per_api
            #        progress.n = summId_idxes[api][1] - summId_idxes[api][0]*summId_per_api 
            #        progress.refresh()
                
            time.sleep(0.1)

        print("All jobs done, waiting for db writer to finish")

    def worker_summid_to_matchids_unified(self, region, platform, api_key, matchid_queue, summid, start_date):
        rai = RiotApiInterface()
        summoner = rai.get_summoner_by_encrypted_summoner_id(summid, platform, api_key)
        puuid = summoner["puuid"]
        
        matchlist = rai.get_matchhistory_by_puuid(
            region, puuid, api_key, startTime=start_date, type="ranked"
        )
        with self.lock_matchids:
            for matchid in matchlist:
                if matchid not in self.unique_matchids:
                    self.unique_matchids.add(matchid)
                    matchid_queue.put(matchid)

    def worker_summoner_id_to_puuid(self, platform, api_key, puuid_queue, summid):
        rai = RiotApiInterface()
        summoner = rai.get_summoner_by_encrypted_summoner_id(summid, platform, api_key)
        puuid_queue.put(summoner["puuid"])

    def worker_puuid_to_matchids(
        self,
        region,
        puuid,
        matchid_queue,
        api_key,
        start_date,
    ):
        rai = RiotApiInterface()
        matchlist = rai.get_matchhistory_by_puuid(
            region, puuid, api_key, startTime=start_date, type="ranked"
        )
        with self.lock_matchids:
            for matchid in matchlist:
                if matchid not in self.unique_matchids:
                    self.unique_matchids.add(matchid)
                    matchid_queue.put(matchid)

    def worker_matchid_to_matchdata(self, region, matchId, api_key, matchdata):
        rai = RiotApiInterface()
        matchData = rai.get_match_by_id(region, matchId, api_key)
        matchdata.put(matchData)


if __name__ == "__main__":
    main()