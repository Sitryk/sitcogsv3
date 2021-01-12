# cog.py

import asyncio
import contextlib
import os
import re
from collections import OrderedDict

import discord
import lavalink
from discord.ext.commands import TextChannelConverter
from redbot.core import Config, checks, commands
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from . import genius

feat_re = re.compile(
    r"((\[)|(\()){1}.*(of?ficial|feat\.?|ft\.?|audio|video|lyrics?|remix){1}.*(?(2)\]|\))",
    flags=re.I,
)


def remove_useless_title_features(string: str):
    new_s = feat_re.sub("", string)
    return new_s


emoji_map = OrderedDict()

emoji_map["back"] = "⬅"
emoji_map["request lyrics"] = "🎶"
emoji_map["exit"] = "❌"
emoji_map["queue in audio"] = "▶"
emoji_map["next"] = "➡"

inverse_map = OrderedDict({v: k for k, v in emoji_map.items()})

loadgif = "https://i.pinimg.com/originals/58/4b/60/584b607f5c2ff075429dc0e7b8d142ef.gif"
greentick = "http://icons.iconarchive.com/icons/paomedia/small-n-flat/1024/sign-check-icon.png"
rederror = "https://icons.iconarchive.com/icons/saki/nuoveXT-2/128/Status-dialog-error-icon.png"
geniusicon = "https://images.genius.com/8ed669cadd956443e29c70361ec4f372.1000x1000x1.png"

GuildDefault = {"autolyrics": False, "channel": None}


class Lyrics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, int("sitryk", 36), force_registration=True)
        self.config.register_guild(**GuildDefault)

    async def get_dest(self, ctx, public: bool = False):
        dest = await self.config.guild(ctx.guild).channel()
        dest = ctx.guild.get_channel(dest)

        if public:
            if dest is None:
                pass
            else:
                return dest

        if dest is None:
            dest = ctx.author
        return dest

    # Setting related commands

    @commands.group()
    @checks.admin()
    async def lyricset(self, ctx):
        """Change lyric related settings"""
        pass

    @lyricset.command()
    async def channel(self, ctx, *, channel_name: str):
        """
        Set the channel for lyrics to be sent to
        Note: to reset default channel to DMs enter dms
        """
        guild = ctx.guild
        if channel_name.lower() != "dms":
            try:
                channelObj = await (TextChannelConverter()).convert(ctx, channel_name)
            except commands.BadArgument:
                return await ctx.send("Couldn't find that channel.")

        if channel_name.lower() == "dms":
            await self.config.guild(guild).channel.set(None)
            await ctx.send("Lyrics will now be sent to DMs")
        else:
            await self.config.guild(guild).channel.set(channelObj.id)
            await ctx.send(f"Lyrics will now be sent to {channelObj.mention}")

    # Base commands start

    @commands.group(invoke_without_command=True)
    async def lyrics(self, ctx, *, query: str):
        """
        Used to fetch lyrics from a search query
        Usage:
               [p]lyrics white ferrari
               [p]lyrics public np

        You can use '[p]lyrics np' to search for what's currently
        playing in audio

        Put the word public at the beginning of your search to send the
        lyrics to the set lyric channel
        """

        guild = ctx.guild
        author = ctx.author
        channel = ctx.channel

        if query.startswith("public "):
            public = True
            query = query[7:]
        else:
            public = False

        AudioCog = self.bot.get_cog("Audio")
        query = query.strip()
        if query == "np":
            if AudioCog is not None:
                try:
                    player = lavalink.get_player(guild.id)
                    query = remove_useless_title_features(player.current.title)
                except KeyError:
                    e = discord.Embed(description="Nothing is playing right now.", colour=16776960)
                    return await ctx.send(embed=e)
            else:
                return await ctx.send("Audio needs to be loaded to use this functionality.")

        songs = await genius.genius_search(query)

        if len(songs) < 1:
            desc = f"There were no results for {query}"
            e = discord.Embed(description=desc, colour=16776960)
            await ctx.send(embed=e)
            return

        items = ""
        for idx, song in enumerate(songs):
            items += "**{}.** {}\n\n".format(idx + 1, song.full_title)

        authdesc = "Genius"
        footdesc = "Results based on search for: {}".format(query)

        choices = discord.Embed(description=items, colour=discord.Color.green())
        choices.set_author(name=authdesc, icon_url=geniusicon)
        choices.set_footer(text=footdesc)

        try:
            sent = await ctx.send(embed=choices)
        except discord.errors.Forbidden:
            await ctx.send("I need the `Embed Messages` Permission")
            return

        def check(msg):
            content = msg.content

            if (
                content.isdigit()
                and int(content) in range(0, len(items) + 1)
                and msg.author is author
                and msg.channel is channel
            ):
                return True

        try:
            choice = await self.bot.wait_for("message", timeout=20, check=check)
        except asyncio.TimeoutError:
            choice = None

        if choice is None or choice.content.strip() == "0":
            e = discord.Embed(description="Cancelled", colour=discord.Colour.orange())
            await sent.edit(embed=e)
            return
        else:
            choice = choice.content.strip()
            choice = int(choice) - 1

            destination = await self.get_dest(ctx, public)
            if isinstance(destination, discord.Member) and public:
                await ctx.send(
                    "An admin or server owner needs to create the "
                    "public lyrics channel using the `lyricset` command, "
                    "I've sent the lyrics to you.",
                    delete_after=60,
                )

            song = songs[choice]

            try:
                lyrics = await song.get_lyrics()
            except genius.LyricsNotFoundError:
                e = discord.Embed(colour=discord.Colour.red())
                e.set_author(name=f"Error getting lyrics for {song.full_title}", icon_url=rederror)
                await sent.edit(embed=e)
                return

            lyrics = cf.pagify(lyrics)

            song_title = song.full_title

            e = discord.Embed(colour=16776960)  # Aesthetics
            e.set_author(name="Requested lyrics for {}".format(song_title), icon_url=loadgif)
            await sent.edit(embed=e)

            e = discord.Embed(colour=discord.Colour.green())  # Aesthetics
            e.set_author(name="Here are the lyrics for {}".format(song_title), icon_url=greentick)
            try:
                await destination.send(embed=e)
            except discord.errors.Forbidden:
                e = discord.Embed(colour=discord.Colour.red())  # Aesthetics
                e.set_author(
                    name="Couldn't send lyrics for {}\nEither you blocked me or you disabled DMs in this server.".format(
                        song_title
                    ),
                    icon_url=rederror,
                )
                await sent.edit(embed=e)
                return

            for page in lyrics:  # Send the lyrics
                if len(page) >= 1:
                    await destination.send(page)

            e = discord.Embed(colour=discord.Colour.green())  # Aesthetics
            e.set_author(name="Sent lyrics for {}".format(song_title), icon_url=greentick)
            await sent.edit(embed=e)

    @lyrics.command()
    @commands.bot_has_permissions(embed_links=True)
    async def spotify(self, ctx, *, user: discord.Member = None):
        """
        Returns lyrics from a member's Listening to Spotify status.

        User arguments - Mention/ID
        NOTE: This command uses Discord presence intent, enable in development portal.
        """
        if not user:
            user = ctx.author

        guild = ctx.guild
        channel = ctx.channel
        target = "You are" if user is ctx.author else f"{user} is"

        spot = next((c for c in user.activities if isinstance(c, discord.Spotify)), None)
        if spot is None:
            return await ctx.send(f"{target} currently not listening to Spotify! 🤔")

        query = f"{spot.title} {spot.artist}"
        songs = await genius.genius_search(query)
        if len(songs) < 1:
            desc = f"There were no results for {spot.title}"
            e = discord.Embed(description=desc, colour=16776960)
            await ctx.send(embed=e)
            return

        items = ""
        for idx, song in enumerate(songs):
            items += f"`[{str(idx + 1).zfill(2)}]` - {song.full_title}\n\n"

        authdesc = "Genius"
        footdesc = f"Results based on search for: {spot.title}"

        choices = discord.Embed(
            description=items,
            colour=discord.Color.green(),
        )
        choices.set_author(name=authdesc, icon_url=geniusicon)
        choices.set_footer(text=footdesc)

        sent = await ctx.send(embed=choices)

        def check(msg):
            content = msg.content
            if (
                content.isdigit()
                and int(content) in range(0, len(items) + 1)
                and msg.author is ctx.author
                and msg.channel is channel
            ):
                return True

        try:
            choice = await self.bot.wait_for("message", timeout=60, check=check)
        except asyncio.TimeoutError:
            choice = None

        if choice is None or choice.content.strip() == "0":
            e = discord.Embed(description="Cancelled", colour=discord.Colour.orange())
            await sent.edit(embed=e)
            return
        else:
            choice = choice.content.strip()
            choice = int(choice) - 1

            song = songs[choice]

            try:
                lyrics = await song.get_lyrics()
            except genius.LyricsNotFoundError:
                e = discord.Embed(colour=discord.Colour.red())
                e.set_author(
                    name=f"Error getting lyrics for {song.full_title}",
                    icon_url=rederror,
                )
                await sent.edit(embed=e)
                return

            song_title = song.full_title

            temp_pages = []
            pages = []
            for page in cf.pagify(lyrics, page_length=500):
                temp_pages.append(page)

            max_i = len(temp_pages)
            i = 1
            for page in temp_pages:
                artists = ", ".join(a for a in spot.artists)
                e = discord.Embed(
                    title=f"{spot.title} by {artists}",
                    colour=discord.Colour.green(),
                )
                e.set_author(
                    name=f"{user.display_name} is listening to:",
                    icon_url=str(user.avatar_url)
                )
                e.description = page
                e.set_thumbnail(url=spot.album_cover_url)
                e.set_footer(text=f"Page {i} of {max_i}")
                pages.append(e)
                i += 1
            await sent.delete()
            await menu(ctx, pages, controls=DEFAULT_CONTROLS, timeout=300.0)

    @commands.command(pass_context=True)
    async def genius(self, ctx, *, query: str):
        """Used to fetch items from a search query
        Usage:
               [p]genius Childish Gambino
               [p]genius Kendrick Lamar
        """
        channel = ctx.channel
        guild = ctx.guild
        author = ctx.author

        bool_convert = {True: "Yes", False: "No"}

        AudioCog = self.bot.get_cog("Audio")
        query = query.strip()
        if query == "np":
            if AudioCog is not None:
                try:
                    player = lavalink.get_player(guild.id)
                    query = remove_useless_title_features(player.current.title)
                except KeyError:
                    e = discord.Embed(description="Nothing is playing right now.", colour=16776960)
                    return await ctx.send(embed=e)
            else:
                return await ctx.send("Audio needs to be loaded to use this functionality.")

        songs = await genius.genius_search(query)
        if len(songs) == 0:
            e = discord.Embed(colour=discord.Colour.red())
            e.set_author(name=f"No songs were found for your query.", icon_url=rederror)
            await sent.edit(embed=e)
            return
        embeds = []

        for idx, song in enumerate(songs):

            artist = song.song_artist

            e = discord.Embed(colour=discord.Colour.green())
            e.add_field(name="Title", value=song.title, inline=True)
            e.add_field(name="Primary Artist", value=artist.name, inline=True)
            e.add_field(name="Verified", value=artist.verified, inline=True)
            e.add_field(name="Views", value=song.views, inline=True)
            e.add_field(name="Hot ", value=song.is_hot, inline=True)
            e.set_thumbnail(url=song.cover_art)
            e.set_footer(text="Page {} - Search: {}".format(idx + 1, query))
            embeds.append(e)

        await self.genius_menu(ctx, displays=embeds, extra_data={"songs": songs})

    # Lunars menu control

    async def genius_menu(
        self,
        ctx,
        displays: list,
        extra_data: dict,
        message: discord.Message = None,
        page=0,
        timeout: int = 30,
    ):
        """
        Menu control logic for this credited to
        https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py
        """

        selected = page
        songs = extra_data["songs"]
        song = songs[selected]
        author = ctx.author
        channel = ctx.channel
        guild = ctx.guild

        current_display = displays[page]

        if not message:
            message = await channel.send(embed=current_display)
            for e in inverse_map:
                await message.add_reaction(e)
        else:
            await message.edit(embed=current_display)

        def rcheck(r, u):
            if u == ctx.author and r.message.id == message.id and r.emoji in ("➡", "⬅", "❌", "🎶", "▶"):
                return True
            return False

        try:
            react, user = await self.bot.wait_for("reaction_add", check=rcheck, timeout=30)
        except asyncio.TimeoutError:
            react = None

        if react is None:
            await self._clearReacts(ctx, inverse_map.keys())
            return

        action = inverse_map[react.emoji]

        if action == "next":
            next_page = (page + 1) % len(displays)
            await self.sup_rem_react(message, emoji_map[action], author)
            return await self.genius_menu(ctx, displays, extra_data, message=message, page=next_page, timeout=timeout)

        elif action == "back":
            next_page = (page - 1) % len(displays)
            await self.sup_rem_react(message, emoji_map[action], author)
            return await self.genius_menu(ctx, displays, extra_data, message=message, page=next_page, timeout=timeout)
        elif action == "queue in audio":
            await self.sup_rem_react(message, emoji_map[action], author)
            audio = self.bot.get_cog("Audio")
            if audio:
                await ctx.invoke(audio.command_play, query=song.full_title)
                await message.delete()
                await self.genius_menu(ctx, displays, extra_data, page=selected, timeout=timeout)
            else:
                e = discord.Embed(colour=16776960)
                e.set_author(name="You need the audio package loaded to use this function")
                await message.edit(embed=e)
                await asyncio.sleep(5)
                await self.genius_menu(ctx, displays, extra_data, message=message, page=selected, timeout=timeout)

        elif action == "request lyrics":
            await self._clearReacts(ctx, message, inverse_map.keys())

            e = discord.Embed(colour=16776960)
            e.set_author(name="Requested lyrics for {}".format(song.full_title), icon_url=loadgif)
            await message.edit(embed=e)

            destination = await self.get_dest(ctx)

            try:
                lyrics = await song.get_lyrics()
            except genius.LyricsNotFoundError:
                e = discord.Embed(colour=discord.Colour.red())
                e.set_author(name=f"Error getting lyrics for {song.full_title}", icon_url=rederror)
                await message.edit(embed=e)
                return

            lyrics = cf.pagify(lyrics)

            for page in lyrics:
                if len(page) > 0:
                    await destination.send(page)

            e = discord.Embed(colour=discord.Colour.green())
            e.set_author(name="Sent lyrics for {}".format(song.full_title), icon_url=greentick)
            await message.edit(embed=e)

        else:
            return await message.delete()

    async def sup_rem_react(self, msg, react, user):
        if msg.channel.permissions_for(msg.guild.me).manage_messages:
            await msg.remove_reaction(react, user)

    async def _clearReacts(self, ctx, message, to_remove: list = None):
        try:
            await message.clear_reactions()
        except:
            try:
                for e in remove:
                    await message.remove_reaction(e, ctx.guild.me)
            except:
                pass
        return None
