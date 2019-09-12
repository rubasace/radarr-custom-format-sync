import os
import logging
import requests
import json
import configparser
import sys
import itertools

QUALITY = "quality"

CUSTOM_FORMATS = "customFormats"

VER = '0.0.1'

IMPORTED_EVENT_TYPE = "downloadFolderImported"
GRABBED_EVENT_TYPE = "grabbed"
DOWNLOAD_ID = "downloadId"
EVENT_TYPE = "eventType"

########################################################################################################################
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

os.makedirs("./logs", exist_ok=True)
fileHandler = logging.FileHandler("./logs/fromat-sync.log")
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)
########################################################################################################################


def ConfigSectionMap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            if dict1[option] == -1:
                logger.debug("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1

logger.debug('CustomFormatSync Version {}'.format(VER))

Config = configparser.ConfigParser()

# Loads an alternate config file so that I can work on my servers without uploading config to github
if "DEV" in os.environ:
    settingsFilename = os.path.join(os.getcwd(), 'dev/'
                                                 'Config.txt')
else:
    settingsFilename = os.path.join(os.getcwd(), 'Config.txt')
Config.read(settingsFilename)

radarr_url = ConfigSectionMap("Radarr")['url']
radarr_key = ConfigSectionMap("Radarr")['key']

radarrSession = requests.Session()
radarrSession.headers.update({'x-api-key': radarr_key})
# TODO check if needed
radarrSession.trust_env = False
radarrMovies = radarrSession.get('{0}/api/movie'.format(radarr_url))
if radarrMovies.status_code >= 300:
    logger.error('Movies retrieve returned status code {}'.format(radarrMovies.status_code))
    sys.exit(0)

pageSize = 999999999
movieHistoryResponse = radarrSession.get(
    '{0}/api/history?page=1&pageSize={1}&sortKey=movie.title&sortDir=desc'.format(radarr_url, pageSize))
if movieHistoryResponse.status_code >= 300:
    logger.error('History retrieve returned status code {}'.format(radarrMovies.status_code))
    sys.exit(0)

movieHistory = movieHistoryResponse.json()
records = movieHistory["records"]
logger.debug("Number of history records: {}".format(len(records)))

movieIdInfoMap = {movie["id"]: movie for movie in radarrMovies.json()}

# print(radarrMovies.json()[0])
# ids = {}
# movieIdInfoMap = {}
# for movie in radarrMovies.json():
#     id = movie["id"]
#     movieIdInfoMap[id] = movie
#     ids[id] = id
#
# logger.debug("Number of movies: {}".format(len(radarrMovies.json())))
# logger.debug("Number of ids: {}".format(len(ids)))

movieIdRecordMap = itertools.groupby(records, lambda e: e["movieId"])

for movieId, group in movieIdRecordMap:
    movieRecords = list(group)
    # Not enough information so pointless to continue (at least we need one grabbed and one imported event)
    if len(movieRecords) < 2:
        continue
    downloadId = ""
    grabbedCustomFormats = None
    movieRecords.sort(key=lambda e: e["date"], reverse=True)
    for movieRecord in movieRecords:
        recordDownloadId = movieRecord.get(DOWNLOAD_ID, "")
        if downloadId:
            if downloadId == recordDownloadId and GRABBED_EVENT_TYPE == movieRecord[EVENT_TYPE]:
                quality = movieRecord.get(QUALITY, {CUSTOM_FORMATS: None})
                grabbedCustomFormats = quality.get(CUSTOM_FORMATS, None)
                break
        elif IMPORTED_EVENT_TYPE == movieRecord[EVENT_TYPE]:
            downloadId = recordDownloadId
            quality = movieRecord.get(QUALITY, {CUSTOM_FORMATS: None})
            currentCustomFormats = quality.get(CUSTOM_FORMATS, None)
    if grabbedCustomFormats is not None:
        movieInfo = movieIdInfoMap[movieId]
        currentFile = movieInfo.get("movieFile", None)
        if currentFile is None:
            logger.debug("Movie file not found for movie: {}".format(movieInfo["title"]))
        elif grabbedCustomFormats != currentFile["quality"]["customFormats"]:
            movieFile = movieInfo["movieFile"]
            movieFileId = movieFile["id"]
            movieFile["quality"]["customFormats"] = grabbedCustomFormats
            updateResponse = radarrSession.put('{0}/api/movieFile/{1}'.format(radarr_url, movieFileId),
                                               data=json.dumps(movieFile))
            if updateResponse.status_code < 300:
                logger.debug("Movie {0} updated succesfully: {1}".format(movieInfo["title"], grabbedCustomFormats))
            else:
                logger.debug("Error while trying to update: {0}".format(movieInfo["title"]))

