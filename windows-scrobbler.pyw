import asyncio
import subprocess
from dataclasses import replace
import os
import webbrowser
import pylast
import time
from dotenv import load_dotenv
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)
import musicbrainzngs
from difflib import SequenceMatcher
import PySimpleGUI as sg
from psgtray import SystemTray
import selenium
from selenium import webdriver
import requests

load_dotenv()

musicbrainzngs.set_useragent("MediaScrobbler", "0.1", "http://localhost")

API_URL = os.getenv("API_SERVER")


# Updating for the authentication api
# Check that the session key file exists
# If it doesn't exist, create it by querying the auth api at Http://localhost:5000/api/v1/authorize
# That will redirect to a page which has the session key in the url
# The session key is then written to the file
def init_script():
    SESSION_KEY_FILE = os.path.join(os.path.expanduser("~"), ".session_key")
    if not os.path.exists(SESSION_KEY_FILE):
        url = API_URL + "authorize"
        driver = selenium.webdriver.Chrome()
        driver.get(url)

        while "session_key" not in driver.current_url:
            time.sleep(1)
            if "session_key" in driver.current_url:
                session_key = driver.current_url.split("session_key=")[1]
                session_key = session_key.split("&")[0]

                with open(SESSION_KEY_FILE, "w") as f:
                    f.write(session_key)

    else:
        session_key = open(SESSION_KEY_FILE).read()

    return session_key


# function which accepts the song name from MusicBrainz and the song name from Windows
# and returns the percentage of the words that match
def compareSongNames(discogsSongName, windowsSongName):
    return SequenceMatcher(None, discogsSongName, windowsSongName).ratio()


def init_system_tray():
    menu_def = ["BLANK", ["&Show Session Scrobble History", "Log Out", "&Exit"]]
    tray = SystemTray(
        menu=menu_def, icon="favicon.ico", tooltip="MediaScrobbler", window=window
    )
    tray.show_icon()
    return tray


async def get_media_info():
    sessions = await MediaManager.request_async()

    current_session = sessions.get_current_session()
    if current_session:
        info = await current_session.try_get_media_properties_async()

        info_dict = {
            song_attr: info.__getattribute__(song_attr)
            for song_attr in dir(info)
            if song_attr[0] != "_"
        }

        info_dict["genres"] = list(info_dict["genres"])

        return info_dict


async def main():
    old_song = await get_media_info()
    if old_song is not None:
        checkOldTrack = musicbrainzngs.search_recordings(
            artist=old_song["artist"], recording=old_song["title"]
        )
        countOldTracks = int(checkOldTrack.get("recording-count"))

        if countOldTracks > 0:
            oldMusicBrainzArtist = (
                checkOldTrack.get("recording-list")[0]
                .get("artist-credit")[0]
                .get("artist")
                .get("name")
            )
            oldMusicBrainzTitle = checkOldTrack.get("recording-list")[0].get("title")
            strippedOldSongTitle = (
                old_song.get("title")
                .replace("Facebook", "")
                .replace("Official", "")
                .replace("Music Video", "")
                .replace("YouTube", "")
                .replace("(", "")
                .replace(")", "")
                .replace("-", "")
                .strip()
            )
            comparison = compareSongNames(oldMusicBrainzTitle, strippedOldSongTitle)
            if comparison > 0.75:
                try:
                    scrobble_data = {
                        "session_key": session_key,
                        "artist": oldMusicBrainzArtist,
                        "track": oldMusicBrainzTitle,
                        "timestamp": int(time.time()),
                    }

                    response = requests.post(API_URL + "scrobble", json=scrobble_data)
                    print(response)
                except Exception as e:
                    print(e)

                print(
                    str(comparison)
                    + " is good enough comparison between "
                    + oldMusicBrainzArtist
                    + "-"
                    + oldMusicBrainzTitle
                    + " and "
                    + old_song.get("artist")
                    + " - "
                    + strippedOldSongTitle
                    + "\n\n"
                )

            print(
                "\nScrobbled"
                + oldMusicBrainzArtist
                + " - "
                + oldMusicBrainzTitle
                + "successfully \n\n"
            )
        else:
            print("No tracks found on MusicBrainz")

        scrobbledSongs = []

    while True:
        event, values = window.read(timeout=1000)
        window.hide()

        if values == ["&Exit"]:
            quit()
        if values == ["Log Out"]:
            os.remove(os.path.join(os.path.expanduser("~"), ".session_key"))
            quit()
        if values == ["&Show Session Scrobble History"]:
            # unwrap the list of scrobbled songs in the popup
            scrobbledSongsList = "\n".join(scrobbledSongs)
            # assign each song a number
            scrobbledSongsList = "\n".join(
                [f"{i+1}. {song}" for i, song in enumerate(scrobbledSongs)]
            )

            popup = sg.popup_non_blocking(
                scrobbledSongsList, title="Scrobbled Songs", keep_on_top=True
            )
            if popup == "OK":
                popup.close()
            if event == sg.WIN_CLOSED:
                popup.close()

        new_song = await get_media_info()
        if new_song is not None:
            current_time_string = time.strftime("%H:%M:%S", time.localtime())
            print(
                "Current song at "
                + current_time_string
                + ":\nTitle: "
                + new_song.get("title")
                + "\nArtist: "
                + new_song.get("artist")
                + "\n\nPrevious Song: \nTitle: "
                + old_song.get("title")
                + "\n"
                + "Artist: "
                + old_song.get("artist")
                + "\n\n---------------------------------------------\n"
            )
            if new_song.get("title") != old_song.get("title"):
                old_song = new_song
                strippedNewSongTitle = (
                    new_song.get("title")
                    .replace("Facebook", "")
                    .replace("Official", "")
                    .replace("Music Video", "")
                    .replace("YouTube", "")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("-", "")
                    .strip()
                )
                checkTrack = musicbrainzngs.search_recordings(
                    artist=new_song.get("artist"), recording=strippedNewSongTitle
                )
                countSongs = int(checkTrack.get("recording-count"))
                if countSongs > 0:
                    musicBrainzTitle = checkTrack.get("recording-list")[0].get("title")
                    musicBrainzArtist = (
                        checkTrack.get("recording-list")[0]
                        .get("artist-credit")[0]
                        .get("artist")
                        .get("name")
                    )

                    comparison = compareSongNames(
                        musicBrainzTitle, strippedNewSongTitle
                    )
                    if comparison > 0.75:
                        scrobble_data = {
                            "session_key": session_key,
                            "artist": musicBrainzArtist,
                            "track": musicBrainzTitle,
                            "timestamp": int(time.time()),
                        }

                        response = requests.post(
                            API_URL + "scrobble", json=scrobble_data
                        )
                        print(
                            str(comparison)
                            + " is good enough comparison between "
                            + musicBrainzArtist
                            + "-"
                            + musicBrainzTitle
                            + " and "
                            + new_song.get("artist")
                            + " - "
                            + strippedNewSongTitle
                            + "\n\n"
                        )
                        print(
                            "\nScrobbled "
                            + musicBrainzArtist
                            + " - "
                            + musicBrainzTitle
                            + " successfully \n\n"
                        )
                        # save the scrobbled song in an array
                        scrobbledSongs.append(
                            musicBrainzArtist + " - " + musicBrainzTitle
                        )
                    else:
                        print(
                            str(comparison)
                            + " is not a good enough match for "
                            + musicBrainzArtist
                            + "-"
                            + musicBrainzTitle
                            + " and "
                            + new_song.get("artist")
                            + " - "
                            + strippedNewSongTitle
                            + "\n\n"
                        )
                        print(
                            "\nMusicBrainz returned an irelevant result. Skipping.\n\n"
                        )
                else:
                    print("\nNo tracks found on Discogs \n")
            await asyncio.sleep(1)


if __name__ == "__main__":
    session_key = init_script()
    layout = [[sg.Text("MediaScrobbler", font="Any 15")]]
    window = sg.Window("MediaScrobbler", layout, icon="favicon.ico")
    tray = init_system_tray()
    asyncio.run(main())
