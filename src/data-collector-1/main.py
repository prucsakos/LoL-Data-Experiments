"""Scrap timestamp based match data from Riot API. Matches are collected from higher tier summoners' match history.
"""

import queue
import time
import os
import threading
import datetime
import json
import sqlite3
from typing import List
import RiotApiInterface
import pandas as pd
import tqdm

def fetch_high_tier_puuids():
    platforms = list(
        filter(
            lambda x: len(x) < 5,
            [
                value
                for name, value in vars(RiotApiInterface.Platform).items()
                if isinstance(value, str)
            ],
        )
    )

    if not os.path.exists("./data/puuids"):
        os.mkdir("./data/puuids")
    threads = []
    for platform in platforms:
        thread = threading.Thread(target=get_hightier_puuids, args=(platform,))
        thread.start()
        threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

"""
Load puuids for each platform and obtain their match histories. 
Obtain both match data and match timeline data for these matches. 
Save match and timeline data per platform as pandas parquet files into ./data/matches folder.
This function starts  a thread for each platform to fetch match data concurrently.
"""     
def fetch_matchlist_by_puuid(startTime):
    platforms_per_region = { u_region:[_k for (_k,_v) in RiotApiInterface.PLATFORM_TO_REGION.items() if _v == u_region] for u_region in list(set(RiotApiInterface.PLATFORM_TO_REGION.values())) }


    if not os.path.exists("./data/match_ids"):
        os.mkdir("./data/match_ids")
    threads = []
    for region, platforms in platforms_per_region.items():
        thread = threading.Thread(target=get_matchids_by_puuid, args=(platforms, startTime, ))
        thread.start()
        threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

def fetch_match_data_by_matchid(database_path):
    platforms_per_region = { u_region:[_k for (_k,_v) in RiotApiInterface.PLATFORM_TO_REGION.items() if _v == u_region] for u_region in list(set(RiotApiInterface.PLATFORM_TO_REGION.values())) }

    _queue = queue.Queue()

    threads = []
    for region, platforms in platforms_per_region.items():
        thread = threading.Thread(target=produce_match_data_by_match_id, args=(platforms, _queue))
        thread.start()
        threads.append(thread)

    writer_thread = threading.Thread(target=write_match_data_by_match_id, args=(database_path, _queue, threads))
    writer_thread.start()
    writer_thread.join()
    
    

def main():
    db_path = "./data/data.db"
    fetch_high_tier_puuids()
    matchids_starttime = convert_date_to_string(2024, 6, (29-14))
    fetch_matchlist_by_puuid(matchids_starttime)
    fetch_match_data_by_matchid(db_path)
    
def convert_date_to_string(year, month, day):
    return str(int(datetime.datetime(year, month, day).timestamp()))
    

    
def write_match_data_by_match_id(database_path, _queue: queue.Queue, threads):
    db = sqlite3.connect(database_path)
    i = 0
    while True:
        try:
            game_data, game_participants, game_timeline = _queue.get(block=False, timeout=None)
            game_data.to_json("game_data.json")
            game_participants.to_json("game_participants.json")
            break
            
            game_data.to_sql(con=db, name="game_data", if_exists='append', index=False)
            game_participants.to_sql(con=db, name="game_participants", if_exists='append', index=False)
            # game_timeline.to_sql(con=db, name="game_timeline", if_exists='append', index=False)
            i += 1
            if i % 1000 == 0:
                print(f"Written {i} rows")
        except queue.Empty as e:
            time.sleep(0.1)
            if not any([t.is_alive() for t in threads]):
                break
        except Exception as e:
            print("Error at db writer thread:", e)
    db.close()
    print("End of writer thread")

def produce_match_data_by_match_id(platforms: List[str], _queue: queue.Queue):
    API = open("./riot.txt", "r").readline()
    for platform in platforms:
        rai = RiotApiInterface.RiotApiInterface(API, platform, default_rate_limit=True)
        f = "./data/match_ids/machids_{}.txt".format(platform)
        if not os.path.exists(f):
            print("{} does not exist".format(f))
            continue
        matchids = open(f, "r").read().split("\n")
        for matchid in tqdm.tqdm(matchids, desc="Getting match data from {}".format(platform)):
            try:
                match = rai.get_match_by_id(matchid)
                #match_timeline = rai.get_match_timeline_by_id(matchid)
                game_data = pd.json_normalize(match)
                game_data.drop(["metadata.participants", "info.participants", "info.teams"], axis=1, inplace=True)
                
                game_participants = pd.json_normalize(match, record_path=["info", "participants"], max_level=0, sep='.')
                game_participants.drop(["challenges", "missions", "perks"], axis=1, inplace=True)
                game_participants["gameId"] = match["info"]["gameId"]
                # timestamp events
                #match_timeline["info"]["frames"] = [event for frame in match_timeline["info"]["frames"] for event in frame["events"]]
                #match_timeline["info"]["frames"] = [event for event in match_timeline["info"]["frames"] if "ITEM" in event["type"]]
                #game_timeline = pd.json_normalize(match_timeline, record_path=["info", "frames"], sep='.')
                
                #game_timeline['itemId'] = game_timeline['itemId'].astype('Int32')
                #game_timeline['participantId'] = game_timeline['participantId'].astype('Int32')
                #game_timeline['timestamp'] = game_timeline['timestamp'].astype('Int64')
                #game_timeline['type'] = game_timeline['type'].astype('string')
                #if 'afterId' in game_timeline.columns:
                #    game_timeline['afterId'] = game_timeline['afterId'].astype('Int32')
                #if 'beforeId' in game_timeline.columns:
                #    game_timeline['beforeId'] = game_timeline['beforeId'].astype('Int32')
                #if 'goldGain' in game_timeline.columns:
                #    game_timeline['goldGain'] = game_timeline['goldGain'].astype('Int32')
                #game_timeline["gameId"] = match["metadata"]["matchId"]
                
                # send game_data, game_participants and game_timeline to writer thread
                #_queue.put((game_data, game_participants, game_timeline))
                _queue.put((game_data, game_participants, None))
            except Exception as e:
                print(f"Error getting match data at {platform}: {str(e)}")

def get_matchids_by_puuid(platforms: List[str], startTime):
    # https://leagueoflegends.fandom.com/wiki/Patch_(League_of_Legends)
    API = open("./riot.txt", "r").readline()
    for platform in platforms:
        rai = RiotApiInterface.RiotApiInterface(API, platform, default_rate_limit=True)
        f = "./data/puuids/puuids_{}.txt".format(platform)
        if not os.path.exists(f):
            print("{} does not exists".format(f))
            continue
        puuids = open(f, "r").read().split("\n")
        matchlist = set()
        for puuid in tqdm.tqdm(puuids, desc="Getting matchids from {}".format(platform)):    
            try:
                match_history = rai.get_matchhistory_by_puuid(puuid, start=0, count=100, startTime=startTime)
                matchlist.update(match_history)
            except Exception as e:
                print(f"Error getting matchlist at {platform}: {str(e)}")
        # save list of puuids to file
        with open("./data/match_ids/machids_{}.txt".format(platform), "w") as f:
            f.write("\n".join(list(matchlist)))


def get_hightier_puuids(platform):
    API = open("./riot.txt", "r").readline()

    rai = RiotApiInterface.RiotApiInterface(API, platform, default_rate_limit=True)

    leagues = rai.get_challenger_leagues(RiotApiInterface.Queue.RANKED_SOLO)

    summonerIds = set()  # Get summonerIds from high elo tiers.
    for queue in [
        RiotApiInterface.Queue.RANKED_SOLO,
        RiotApiInterface.Queue.RANKED_FLEX,
    ]:
        leagues = rai.get_challenger_leagues(queue)
        summonerIds.update([entry["summonerId"] for entry in leagues["entries"]])
        leagues = rai.get_grandmaster_leagues(queue)
        summonerIds.update([entry["summonerId"] for entry in leagues["entries"]])
        leagues = rai.get_master_leagues(queue)
        summonerIds.update([entry["summonerId"] for entry in leagues["entries"]])
    print("Number of summonerIds:", len(summonerIds))
    # Get puuids of each summonerId

    puuids = set()
    for summonerId in tqdm.tqdm(
        summonerIds, desc="Getting puuids from {}".format(platform)
    ):
        try:
            summoner = rai.get_summoner_by_encrypted_summoner_id(summonerId)
            puuids.add(summoner["puuid"])
        except Exception as e:
            print(f"Error getting puuid for summonerId {summonerId}: {str(e)}")

    # save list of puuids to file
    with open("./data/puuids/puuids_{}.txt".format(platform), "w") as f:
        f.write("\n".join(puuids))


main()