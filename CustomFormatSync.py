import os
import logging
import pathlib
import requests
import json
import configparser
import sys
import itertools
import time

QUALITY = "quality"

CUSTOM_FORMATS = "customFormats"

VER = '1.0.0'

IMPORTED_EVENT_TYPE = "downloadFolderImported"
GRABBED_EVENT_TYPE = "grabbed"
DOWNLOAD_ID = "downloadId"
EVENT_TYPE = "eventType"

########################################################################################################################
logger = logging.getLogger()
log_level = os.getenv("LOG_LEVEL", "INFO")
logger.setLevel(log_level)
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


def get_custom_format_names(movie_info):
    return list(map(lambda e: e["name"], movie_info['movieFile']["quality"]["customFormats"]))


def rename_file(movie_info, appends):
    current_path = get_current_path(movie_info)
    current_filename = get_current_filename(movie_info)

    file_parts = os.path.splitext(current_filename)
    new_filename = file_parts[0]
    for custom_format in get_custom_format_names(movie_info):
        postfix = appends.get(custom_format.lower(), "")
        if postfix not in file_parts[0]:
            new_filename += postfix

    new_filename = "{}{}".format(new_filename, file_parts[1])
    changed = new_filename != current_filename
    if changed:
        original_path = os.path.join(current_path, current_filename)
        new_path = os.path.join(current_path, new_filename)
        logger.debug("{} will be moved to {}".format(str(original_path), str(new_path)))
        os.rename(original_path, new_path)
        logger.info("{} renamed to {}".format(str(original_path), str(new_path)))

    return new_filename, changed


def refresh_movie(movie_info):
    movie_id = movie_info["id"]
    title = movie_info["title"]
    command = {"movieId": movie_id, "name": "refreshMovie"}
    refresh_response = radarrSession.post("{0}/api/command".format(radarr_url),
                                          data=json.dumps(command))
    if refresh_response.status_code < 300:
        logger.debug("Movie {} refreshed succesfully".format(title))
    else:
        logger.error("Error while refreshing movie: {}".format(title))


def get_current_path(movie_info):
    path = pathlib.Path(movie_info['path'])
    return str(path)


def get_current_filename(movie_info):
    return movie_info['movieFile']['relativePath']


def refresh_movie(movie_info):
    movie_id = movie_info['id']
    title = movie_info["title"]
    command = {"movieId": movie_id, "name": "refreshMovie"}
    refresh_response = radarrSession.post("{0}/api/command".format(radarr_url),
                                          data=json.dumps(command))
    if refresh_response.status_code < 300:
        logger.debug("Movie {} refreshed succesfully".format(title))
    else:
        logger.error("Error while refreshing movie: {}".format(title))


logger.info('CustomFormatSync Version {}'.format(VER))

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
appends = ConfigSectionMap("Append")

radarrSession = requests.Session()
radarrSession.headers.update({'x-api-key': radarr_key})
# TODO check if needed
radarrSession.trust_env = False
radarrMovies = radarrSession.get('{0}/api/movie'.format(radarr_url))
if radarrMovies.status_code >= 300:
    logger.error('Movies retrieve returned status code {}\n{}'.format(radarrMovies.status_code, radarrMovies.json()))
    sys.exit(1)

pageSize = 999999999
movieHistoryResponse = radarrSession.get(
    '{0}/api/history?page=1&pageSize={1}&sortKey=movie.title&sortDir=desc'.format(radarr_url, pageSize))
if movieHistoryResponse.status_code >= 300:
    logger.error('History retrieve returned status code {}\n{}'.format(movieHistoryResponse.status_code,
                                                                       movieHistoryResponse.json()))
    sys.exit(2)

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
        elif IMPORTED_EVENT_TYPE == movieRecord[EVENT_TYPE]:
            downloadId = recordDownloadId
    if grabbedCustomFormats is not None:
        movie_info = movieIdInfoMap[movieId]
        currentFile = movie_info.get("movieFile", None)
        if currentFile is None:
            logger.debug("Movie file not found for movie: {}".format(movie_info["title"]))
        elif grabbedCustomFormats != currentFile["quality"]["customFormats"]:
            movie_file = movie_info["movieFile"]
            movie_file_id = movie_file["id"]
            movie_file["quality"]["customFormats"] = grabbedCustomFormats

            relative_path, changed = rename_file(movie_info, appends)

            if changed:
                # Need to call it twice to catch renames (first will stop finding the file and second will find new one)
                refresh_movie(movie_info)

                # Need to wait some time so it does catch file changes properly
                time.sleep(20)

                refresh_movie(movie_info)

            movie_file['relativePath'] = relative_path

            updateResponse = radarrSession.put('{0}/api/movieFile/{1}'.format(radarr_url, movie_file_id),
                                               data=json.dumps(movie_file))
            if updateResponse.status_code < 300:
                logger.info("Movie {0} updated successfully: {1}".format(movie_info["title"], grabbedCustomFormats))
            else:
                logger.error("Error while trying to update: {0}".format(movie_info["title"]))

logger.info("Done!!")
