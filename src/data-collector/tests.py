from riotwatcher import LolWatcher, RiotWatcher, ApiError

### API ###
APIKEY = open("riot.txt", "r").readline()
###=====###

lolWatcher = LolWatcher(APIKEY)
riotWatcher = RiotWatcher(APIKEY)
print(lolWatcher, riotWatcher)

region = "eun1"
platform = "EUROPE"
account = riotWatcher.account.by_riot_id(platform, "BoldogKatica1", "EUNE")
# {'puuid': 'vEgBphSIP4kLidak6uIjOpxOBdvA6oAC_8hL2hKFm22O0WdqmxCkH-B_ARGTCns6KAkwDjKB5e0lhw', 'gameName': 'BoldogKatica1', 'tagLine': 'EUNE'}
summoner = lolWatcher.summoner.by_puuid(region, account["puuid"])
# {'id': 'cOhTGpoZzlyUAXZ1_17XAmr73Tl1W35ZM4904B-uWoYcbUw', 'accountId': 'WKGBVBYq-6X_SbxGPc0Q0Oj15-9jFLYd53cdPTUCQ1PASA',
# 'puuid': 'vEgBphSIP4kLidak6uIjOpxOBdvA6oAC_8hL2hKFm22O0WdqmxCkH-B_ARGTCns6KAkwDjKB5e0lhw', 'profileIconId': 1638, 'revisionDate': 1717009508223, 'summonerLevel': 501}

### matches

matches = lolWatcher.match.matchlist_by_puuid(region, account["puuid"], count=3)
# matches ->list[str] | ['EUN1_3603423536', 'EUN1_3603410322', 'EUN1_3603355849']

match = lolWatcher.match.timeline_by_match(region, matches[0])
myId = [
    ptld["participantId"]
    for ptld in match["info"]["participants"]
    if ptld["puuid"] == account["puuid"]
][0]
# filteredMatch = [frame["events"] for frame in match["info"]["frames"]]
# filteredMatch = list(set(filteredMatch))
print(match["info"]["frames"][3]["events"])
