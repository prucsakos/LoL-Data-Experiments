"""Scrap timestamp based match data from Riot API. Matches are collected from higher tier summoners' match history.
"""

import RiotApiInterface
import time
import tqdm
import threading


def main():

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

    threads = []
    for platform in platforms:
        thread = threading.Thread(target=get_hightier_puuids, args=(platform,))
        thread.start()
        threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
        thread.join()


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
    with open("puuids_{}.txt".format(platform), "w") as f:
        f.write("\n".join(puuids))


main()
