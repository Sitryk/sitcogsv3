try:
    from bs4 import BeautifulSoup

    _soupAvailable = True
except:
    _soupAvailable = False

import aiohttp
import asyncio


class LyricsNotFoundError(Exception):
    pass


class GeniusSong:
    def __init__(self, *args, **kwargs):
        self.type = kwargs.pop("type", None)
        self.full_title = kwargs.pop("full_title")
        self.title = kwargs.pop("title")
        self.song_artist = kwargs.pop("main_artist")
        self.page_url = kwargs.pop("page_url")
        self.header_image_url = kwargs.pop("header_image_url")
        self.cover_art = kwargs.pop("cover_art_url")
        self.annotations = kwargs.pop("annotation_count")
        self.is_hot = kwargs.pop("hot", False)
        self.views = kwargs.pop("views", None)
        self.api_path = kwargs.pop("api_path")
        # self.lyrics = closed(lyrics_from_path, self.page_url)

    async def get_lyrics(self):
        return await lyrics_from_path(self.page_url)


class GeniusArtist:
    def __init__(self, *args, **kwargs):
        self.name = kwargs.pop("name")
        self.iq = kwargs.pop("iq")
        self.verified = kwargs.pop("verified")
        self.meme_verified = kwargs.pop("meme_verified")
        self.pfp_url = kwargs.pop("pfp_url")
        self.url = kwargs.pop("artist_url")


headers = {"Authorization": "Bearer 2wjXkB5_rWzVnEFOKwFMWhJOwvNPAlFDTywyaRK0jc3gtrCZjx8CsaXjzcE-2_4j"}
api_url = "https://api.genius.com"

# Genius related functions


async def lyrics_from_path(path):
    """Gets the lyrics from a song path"""

    async with aiohttp.ClientSession() as session:
        page = await session.get(path)
        t = await page.text()
        html = BeautifulSoup(t, "html.parser")
        [h.extract() for h in html("script")]
        try:
            lyrics = html.find("div", class_="lyrics").get_text()
        except AttributeError as e:
            raise LyricsNotFoundError from e
        return lyrics


async def genius_search(query: str):
    """Get the data from the genius api"""

    search_url = api_url + "/search"
    data = {"q": query}
    json = None
    async with aiohttp.ClientSession() as session:
        r = await session.get(search_url, data=data, headers=headers)
        json = await r.json()

    songs = []
    for index, hit in enumerate(json["response"]["hits"]):

        try:
            iq = str(hit["result"]["primary_artist"]["iq"])
        except KeyError:
            iq = "0"
        try:
            views = str(hit["result"]["stats"]["pageviews"])
        except KeyError:
            views = None

        song_data = {
            "type": hit["type"],
            "api_path": hit["result"]["api_path"],
            "annotation_count": hit["result"]["annotation_count"],
            "title": hit["result"]["title"],
            "full_title": hit["result"]["full_title"],
            "header_image_url": hit["result"]["header_image_url"],
            "page_url": hit["result"]["url"],
            "cover_art_url": hit["result"]["song_art_image_thumbnail_url"],
            "hot": hit["result"]["stats"]["hot"],
            "views": views,
            "main_artist": None,
        }

        artist_data = {
            "name": hit["result"]["primary_artist"]["name"],
            "artist_url": hit["result"]["primary_artist"]["url"],
            "iq": iq,
            "meme_verified": hit["result"]["primary_artist"]["is_meme_verified"],
            "verified": hit["result"]["primary_artist"]["is_verified"],
            "pfp_url": hit["result"]["primary_artist"]["image_url"],
        }

        artist = GeniusArtist(**artist_data)
        song_data["main_artist"] = artist
        song = GeniusSong(**song_data)
        songs.append(song)

    return songs
