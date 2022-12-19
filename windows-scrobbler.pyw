import asyncio
import subprocess
from dataclasses import replace
import os
import webbrowser
import pylast
import time
from dotenv import load_dotenv
from winsdk.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager as MediaManager
import musicbrainzngs
from difflib import SequenceMatcher
import PySimpleGUI as sg
from psgtray import SystemTray

load_dotenv()

musicbrainzngs.set_useragent("MediaScrobbler", "0.1", "http://localhost")

# You have to have your own unique two values for API_KEY and API_SECRET
# Obtain yours from https://www.last.fm/api/account/create for Last.fm

API_KEY = os.getenv('API_KEY')  # this is a sample key

API_SECRET = os.getenv('API_SECRET')


def init_network():
    SESSION_KEY_FILE = os.path.join(os.path.expanduser("~"), ".session_key")
    network = pylast.LastFMNetwork(API_KEY, API_SECRET)
    if not os.path.exists(SESSION_KEY_FILE):
        skg = pylast.SessionKeyGenerator(network)
        url = skg.get_web_auth_url()

        print(f"Please authorize this script to access your account: {url}\n")
        webbrowser.open(url)
        while True:
            try:
                session_key = skg.get_web_auth_session_key(url)
                with open(SESSION_KEY_FILE, "w") as f:
                    f.write(session_key)
                break
            except pylast.WSError:
                time.sleep(1)
    else:
        session_key = open(SESSION_KEY_FILE).read()
    network.session_key = session_key
    
    return network

#function which accepts the song name from discogs and the song name from Windows 
#and returns the percentage of the words that match
def compareSongNames(discogsSongName, windowsSongName):
    return SequenceMatcher(None, discogsSongName, windowsSongName).ratio()

def init_system_tray():
    menu_def = ['BLANK', ['&Show Session Scrobble History', '&Exit']]
    tray = SystemTray(menu=menu_def, icon='favicon.ico', tooltip='MediaScrobbler', window=window)
    tray.show_icon()
    return tray


async def get_media_info():
    sessions = await MediaManager.request_async()

    current_session = sessions.get_current_session()
    if current_session:  
            info = await current_session.try_get_media_properties_async()

            # song_attr[0] != '_' ignores system attributes
            info_dict = {song_attr: info.__getattribute__(song_attr) for song_attr in dir(info) if song_attr[0] != '_'}

            # converts winrt vector to list
            info_dict['genres'] = list(info_dict['genres'])

            return info_dict

async def main():
    old_song = await get_media_info()
    if old_song is not None:
        checkOldTrack = musicbrainzngs.search_recordings(artist=old_song['artist'], recording=old_song['title'])
        countOldTracks = int(checkOldTrack.get('recording-count'))

        if countOldTracks > 0:
            oldMusicBrainzArtist = checkOldTrack.get('recording-list')[0].get('artist-credit')[0].get('artist').get('name')
            oldMusicBrainzTitle =  checkOldTrack.get('recording-list')[0].get('title')
            strippedOldSongTitle = old_song.get('title').replace('Facebook', '').replace('Official', '').replace('Music Video', '').replace('YouTube', '').replace('(', '').replace(')', '').replace('-','').strip()
            comparison = compareSongNames(oldMusicBrainzTitle, strippedOldSongTitle)
            if comparison > 0.75:
                network.scrobble(
                    artist=oldMusicBrainzArtist,
                    title=oldMusicBrainzTitle,
                    timestamp=int(time.time()),
                )
                print("\nScrobbled" + oldMusicBrainzArtist + " - " + oldMusicBrainzTitle + "successfully \n\n") 
        else:
            print('No tracks found on MusicBrainz')

        scrobbledSongs = []

    while True:

        event, values = window.read(timeout=1000)
        window.hide()

        if values == ['&Exit']:
            quit()
        if values == ['&Show Session Scrobble History']:
            #unwrap the list of scrobbled songs in the popup
            scrobbledSongsList = '\n'.join(scrobbledSongs)
            #assign each song a number
            scrobbledSongsList = '\n'.join([f'{i+1}. {song}' for i, song in enumerate(scrobbledSongs)])


            popup = sg.popup_non_blocking(scrobbledSongsList, title='Scrobbled Songs', keep_on_top=True)
            if popup == 'OK':
                popup.close()
            if event == sg.WIN_CLOSED:
                popup.close()

                
            
            
            

        new_song = await get_media_info()
        if new_song is not None:
            current_time_string = time.strftime("%H:%M:%S", time.localtime())
            print("Current song at " + current_time_string + ":\nTitle: " + new_song.get('title') + "\nArtist: " + new_song.get('artist') + "\n\nPrevious Song: \nTitle: " + old_song.get('title') + "\n" + "Artist: " + old_song.get('artist') + "\n\n---------------------------------------------\n")
            if new_song.get('title') != old_song.get('title'):
                old_song = new_song
                strippedNewSongTitle = new_song.get('title').replace('Facebook', '').replace('Official', '').replace('Music Video', '').replace('YouTube', '').replace('(', '').replace(')', '').replace('-','').strip()
                checkTrack = musicbrainzngs.search_recordings(artist=new_song.get('artist'), recording=strippedNewSongTitle)
                countSongs = int(checkTrack.get('recording-count'))
                if countSongs > 0:
                    musicBrainzTitle = checkTrack.get('recording-list')[0].get('title')
                    musicBrainzArtist = checkTrack.get('recording-list')[0].get('artist-credit')[0].get('artist').get('name')
                    
                    comparison = compareSongNames(musicBrainzTitle, strippedNewSongTitle)
                    if comparison > 0.75:
                        network.scrobble(
                            artist=musicBrainzArtist,
                            title=musicBrainzTitle,
                            timestamp=int(time.time()),
                        )
                        print(str(comparison) + " is good enough comparison between " + musicBrainzArtist + "-" + musicBrainzTitle +  " and " + new_song.get('artist') + " - " + strippedNewSongTitle + "\n\n")
                        print("\nScrobbled " + musicBrainzArtist + " - " + musicBrainzTitle + " successfully \n\n")
                        #save the scrobbled song in an array
                        scrobbledSongs.append(musicBrainzArtist + " - " + musicBrainzTitle)
                    else:
                        print(str(comparison) + " is not a good enough match for " + musicBrainzArtist + "-" + musicBrainzTitle + " and " + new_song.get('artist') + " - " + strippedNewSongTitle + "\n\n")
                        print("\nMusicBrainz returned an irelevant result. Skipping.\n\n")
                else:
                    print("\nNo tracks found on Discogs \n")
            await asyncio.sleep(1)

if __name__ == '__main__':
    network = init_network()
    layout = [[sg.Text('MediaScrobbler', font='Any 15')]]
    window = sg.Window('MediaScrobbler', layout, icon='favicon.ico')
    tray = init_system_tray()
    asyncio.run(main())
    





