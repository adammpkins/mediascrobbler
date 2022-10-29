import asyncio
from dataclasses import replace
import os
import pylast
import time
from dotenv import load_dotenv
from winsdk.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager as MediaManager
import musicbrainzngs
from difflib import SequenceMatcher

load_dotenv()

musicbrainzngs.set_useragent("MediaScrobbler", "0.1", "http://localhost")


# You have to have your own unique two values for API_KEY and API_SECRET
# Obtain yours from https://www.last.fm/api/account/create for Last.fm

API_KEY = os.getenv('API_KEY')  # this is a sample key

API_SECRET = os.getenv('API_SECRET')

# In order to perform a write operation you need to authenticate yourself
username = os.getenv('LASTFM_USERNAME')
password_hash = pylast.md5(os.getenv('LASTFM_PASSWORD'))

network = pylast.LastFMNetwork(
    api_key=API_KEY,
    api_secret=API_SECRET,
    username=username,
    password_hash=password_hash,
)

#function which accepts the song name from discogs and the song name from Windows 
#and returns the percentage of the words that match
def compareSongNames(discogsSongName, windowsSongName):
    return SequenceMatcher(None, discogsSongName, windowsSongName).ratio()


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

    while True:
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
                        print("\nScrobbled " + musicBrainzArtist + " - " + musicBrainzTitle + " successfully \n\n")
                    else:
                        print("\nMusicBrainz returned an irelevant result. Skipping.\n\n")
                else:
                    print("\nNo tracks found on Discogs \n")
            await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())





