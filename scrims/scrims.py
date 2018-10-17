from redbot.core import checks, commands, Config
from redbot.core.data_manager import bundled_data_path
from discord import FFmpegPCMAudio, PCMVolumeTransformer

import re
import discord
import os
import asyncio
import datetime

# get a countdown file



"""
How scrims cog works:

    s.solos  :: shows if solos are running
    s.duos   :: shows if duos are running
    s.squads :: shows if squads are running

    The above commands also show the pools of players

    s.queue [solos|duos|squads] 25 ::
            counts down from 5 seconds in 25 seconds the squads voice channel
            and restricts squads text channel to scrim codes;
            3 letters or less from @everyone users

    s.q     alias for s.queue


    s.setup :: setup voice and text channels for this
               server

"""

setup_string = """
Thanks for adding me to your server! To get started, my prefix is `s.` which means that any commands must start with `s.`, i.e. `s.help`

You should run `s.setup` in the scrim server, following this the bot will create **two** categories
one that houses **three** text channels for scrim codes and one that houses **three** voice channels for countdowns,
by default users with only the @everyone role will not be able to speak in the voice channels, and will not be able to speak
in the scrim code channels until the countdown has been complete, where it will then collect 3 letter scrim codes from users
if a user enters the scrim code twice in the chat it will not be counted twice, also the most recent 3 letter text from a user will count
as their scrim code, if someone says "lol" in the scrim code chat, that's their fault. 
"""

how_to_queue = """
**How To Queue**

1 → If you click the 3 lines on the top left and scroll down you will see voice channels called "Solo Countdown" "Duo Countdown" "Squad Countdown", you join the voice channel and wait for the bot to countdown, the bot will tell you that it will countdown 2 minutes, 1 minute, 30 seconds and 10 seconds before the countdown begins. The bot will then count down from 5, then queue on "Go".
2 → Once you are in the pre game lobby look at the top left and there will be a server code. In the game code chat <#{soid}> <#{did}> <#{sqid}> whatever game mode your playing at the time and type the **last 3** letters or numbers of your server to see if you and other have your same server. eg a5j, 2cc
3 → The bot will scan the chat for 3 letter codes and make list of the lobbies along with the number of users that also wrote that server code. If you got into a stacked lobby play the game and have fun.
4 → If you die, make sure to spectate the whole game out and **don't leave**. Most game finish around the same time
"""




DefaultGuild_CONFIG = {
    'setup_run' : False,
    'autoscrims_on' : False,
    'scrimCodesCategory' : None,
    'countdownCategory' : None,
    'soloTextChannel': None,
    'soloVoiceChannel': None,
    'duoTextChannel' : None,
    'duoVoiceChannel' : None,
    'squadTextChannel' : None,
    'squadVoiceChannel' : None
}

valid_mode_re = re.compile(r'(solo|duo|squad)s?')
BaseCog = getattr(commands, "Cog", object)


class Scrims(BaseCog):

    def __init__(self, bot):
        self.bot = bot

        #self.scrims_till_poll = 4
        self.autoscrim_tasks = {}

        self.config = Config.get_conf(self, identifier=int('sitryk', 36), force_registration=True)
        self.config.register_guild(**DefaultGuild_CONFIG)

    @commands.command(name='scrimdel')
    async def get_rid_of_scrim_channels(self, ctx):
        async with self.config.guild(ctx.guild).all() as gconf:
            for k, cid in gconf.items():
                if k in ('setup_run', 'autoscrims_on'):
                    continue
                try:
                    await (ctx.guild.get_channel(cid)).delete()
                except AttributeError:
                    pass
                gconf[k] = None

    @commands.command(name='setup')
    @checks.guildowner()
    async def scrim_setup(self, ctx):
        """
        """

        await ctx.send('Running Setup...')

        # remember to write permissions code


        # channel creation

        rsn = "ScrimBot Setup Run"

        overwriteText = {
        ctx.guild.default_role : discord.PermissionOverwrite(send_messages=False)
        }

        overwriteVoice = {
        ctx.guild.default_role : discord.PermissionOverwrite(speak=False)
        }

        scrimCodesCategory = await ctx.guild.create_category_channel(name='Scrim Codes', reason=rsn)
        soloTextChannel = await ctx.guild.create_text_channel(name='Solo Codes', category=scrimCodesCategory,
                                                              reason=rsn, overwrites=overwriteText)
        duoTextChannel = await ctx.guild.create_text_channel(name='Duo Codes', category=scrimCodesCategory,
                                                             reason=rsn, overwrites=overwriteText)
        squadTextChannel = await ctx.guild.create_text_channel(name='Squad Codes', category=scrimCodesCategory,
                                                               reason=rsn, overwrites=overwriteText)

        countdownCategory = await ctx.guild.create_category_channel(name='Scrim Countdown', reason=rsn)
        soloVoiceChannel = await ctx.guild.create_voice_channel(name='Solo Countdown', category=countdownCategory,
                                                                reason=rsn, overwrites=overwriteVoice)
        duoVoiceChannel = await ctx.guild.create_voice_channel(name='Duo Countdown', category=countdownCategory,
                                                               reason=rsn, overwrites=overwriteVoice)
        squadVoiceChannel = await ctx.guild.create_voice_channel(name='Squad Countdown', category=countdownCategory,
                                                                 reason=rsn, overwrites=overwriteVoice)

        await self.config.guild(ctx.guild).set_raw('scrimCodesCategory', value=scrimCodesCategory.id)
        await self.config.guild(ctx.guild).set_raw('soloTextChannel', value=soloTextChannel.id)
        await self.config.guild(ctx.guild).set_raw('duoTextChannel', value=duoTextChannel.id)
        await self.config.guild(ctx.guild).set_raw('squadTextChannel', value=squadTextChannel.id)
        await self.config.guild(ctx.guild).set_raw('countdownCategory', value=countdownCategory.id)
        await self.config.guild(ctx.guild).set_raw('soloVoiceChannel', value=soloVoiceChannel.id)
        await self.config.guild(ctx.guild).set_raw('duoVoiceChannel', value=duoVoiceChannel.id)
        await self.config.guild(ctx.guild).set_raw('squadVoiceChannel', value=squadVoiceChannel.id)

        await ctx.send("Channel Setup Complete.")

        # deal with permissions eventually

    @commands.command(name='manualsetup')
    @checks.guildowner()
    async def manualsetup(self, ctx, tcid: discord.CategoryChannel, solotid: discord.TextChannel, duotid: discord.TextChannel, squadtid: discord.TextChannel, vcid: discord.CategoryChannel, solovid: discord.VoiceChannel, duovid: discord.VoiceChannel, squadvid: discord.VoiceChannel):
        """
        s.manualsetup <TextCategoryID> <SoloTextID> <DuoTextID> <SquadTextID> <VoiceCategoryID> <SoloVoiceID> <DuoVoiceID> <SquadVoiceID>
        """
        await ctx.send(f"Scrim Codes Category : {tcid.mention}\n"
                       f"Solo Code Channel    : {solotid.mention}\n"
                       f"Duo Code Channel     : {duotid.mention}\n"
                       f"Squad Code Channel   : {squadtid.mention}\n\n"
                       f"Scrim Countdown Category : {vcid.name}\n"
                       f"Solo Countdown Channel   : {solovid.name}\n"
                       f"Duo Countdown Channel    : {duovid.name}\n"
                       f"Squad Countdown Channel  : {squadvid.name}")
        await ctx.send("Confirm Channels (y/n)")
        def pred(m):
            return m.content in ('y', 'n')

        try:
            m = await self.bot.wait_for('message', check=pred, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send('Cancelling')
        del pred

        if m.content == 'y':
            await self.config.guild(ctx.guild).set_raw('scrimCodesCategory', value=tcid.id)
            await self.config.guild(ctx.guild).set_raw('soloTextChannel', value=solotid.id)
            await self.config.guild(ctx.guild).set_raw('duoTextChannel', value=duotid.id)
            await self.config.guild(ctx.guild).set_raw('squadTextChannel', value=squadtid.id)
            await self.config.guild(ctx.guild).set_raw('countdownCategory', value=vcid.id)
            await self.config.guild(ctx.guild).set_raw('soloVoiceChannel', value=solovid.id)
            await self.config.guild(ctx.guild).set_raw('duoVoiceChannel', value=duovid.id)
            await self.config.guild(ctx.guild).set_raw('squadVoiceChannel', value=squadvid.id)

            return await ctx.send("Channel IDs confirmed.")
        else:
            return await ctx.send("Manual ID setup cancelled.")



    @commands.command(name='autoscrim', usage="<off|solos|duos|squads>")
    @checks.has_permissions(manage_messages=True)
    async def autoscrim(self, ctx, gamemode: str=...):
        """
        Toggle auto-scrims

        Example:
        s.autoscrim solos
        s.autoscrims off
        """
        if gamemode == 'off':
            if not ctx.guild.id in self.autoscrim_tasks:
                return await ctx.send("Auto-Scrims is not runnning.")
            await self.config.guild(ctx.guild).autoscrims_on.set(False)
            self.autoscrim_tasks[ctx.guild.id].cancel()
            self.autoscrim_tasks.pop(ctx.guild.id)
            return await ctx.send("Auto-Scrims disabled.")

        elif valid_mode_re.fullmatch(str(gamemode)):
            await ctx.send("You've given an invalid gamemode, valid gamemodes are `solo(s)`, `duo(s)` or `squad(s)`")
        elif state and valid_mode_re.fullmatch(str(gamemode)):
            await ctx.send(f"Auto-Scrims enabled with {gamemode.rstrip('s')}s.")
            await self.config.guild(ctx.guild).autoscrims_on.set(True)
            self.autoscrim_tasks[ctx.guild.id] = self.bot.loop.create_task(self.scrim_loop(ctx.guild, gamemode))


    @commands.command(name='queue', aliases=['q'], usage="<solos|duos|squads> <1|2>")
    @checks.has_permissions(manage_messages=True)
    async def queue_mode(self, ctx, gamemode, startin: int=1):
        """
        Start the queueing process for a scrim, start time must be 1 or 2, this is the number of minutes before countdown.
        By default the wait time is 1 minute

        Examples:

        s.queue solo
            or
        s.q solos 2
        """
        if startin not in (1, 2):
            return await ctx.send("Start time must be either `1` or `2`.")

        elif valid_mode_re.fullmatch(gamemode) is None:
            return await ctx.send("You've given an invalid gamemode, valid gamemodes are `solo(s)`, `duo(s)` or `squad(s)`")

        gameTextChannel_id = await self.config.guild(ctx.guild).get_raw(f'{gamemode.rstrip("s")}TextChannel')
        gameTextChannel = discord.utils.get(ctx.guild.text_channels, id=gameTextChannel_id)
        await ctx.send(f"Okay, I will begin counting {gamemode.rstrip('s')}s in {startin} minute{'s' if startin > 1 else ''}. After the countdown has finished, I will collect gamecodes for 1 minute in {gameTextChannel.mention}.")

        gameVoiceChannel_id = await self.config.guild(ctx.guild).get_raw(f'{gamemode.rstrip("s")}VoiceChannel')
        gameVoiceChannel = discord.utils.get(ctx.guild.voice_channels, id=gameVoiceChannel_id)
        await self.begin_countdown(ctx.voice_client, gameVoiceChannel, startin)

        await gameTextChannel.send("**Gamecodes go here for the next minute.**")
        await gameTextChannel.set_permissions(ctx.guild.default_role, send_messages=True)

        def _valid_gamecode_check(m):
            cont = m.content
            try:
                assert gameTextChannel.id == m.channel.id and len(cont) == 3
                int(cont, 36)
            except AssertionError:
                return False
            except ValueError:
                return False

            return True

        gamecode_pool = []
        start = datetime.datetime.now()

        while (datetime.datetime.now() - start).total_seconds() < 60:
            try:
                resp = await self.bot.wait_for('message', check=_valid_gamecode_check, timeout=60 - (datetime.datetime.now()-start).total_seconds())
                gamecode_pool.append(resp)
                continue
            except asyncio.TimeoutError:
                break

        await gameTextChannel.set_permissions(ctx.guild.default_role, send_messages=False)
        await gameTextChannel.send(self._build_lobby_display(self._filter_lobby_codes(gamecode_pool)))

    def _filter_lobby_codes(self, messages):
        messages.sort(key=lambda m: m.created_at, reverse=True)
        seen_users = []
        finals = []
        for m in messages.copy():
            if m.author.id not in seen_users:
                seen_users.append(m.author.id)
                finals.append(m)
            continue
        del seen_users
        return finals


    def _build_lobby_display(self, messages):
        pool = {}
        for m in messages:
            if m.content not in pool:
                pool[m.content] = 1
            else:
                pool[m.content] += 1
        header = [f"**`{len(pool.keys())}` Lobb{'y' if len(pool.keys()) == 1 else 'ies'}**\n"]
        for k, v in pool.items():
            header.append(f"**`{v}`** in lobby `{k}`")
        return '\n'.join(header)



    async def begin_countdown(self, voice_client, channel, startpoint: int):
        """
        Send the bot to the channel to route countdown audio
        """
        assert startpoint in (1, 2)
        vc = voice_client
        await asyncio.sleep(2)

        if startpoint == 2:
            vc = await self.play_audio(voice_client, channel, 'in2minutes')
            print('played audio in2minutes')
            await asyncio.sleep(60)
        vc = await self.play_audio(vc, channel, 'in1minute')
        print('played audio in1minute')
        await asyncio.sleep(30)
        vc = await self.play_audio(vc, channel, 'in30seconds')
        print('played audio in30seconds')
        await asyncio.sleep(20)
        vc = await self.play_audio(vc, channel, 'in10seconds')
        print('played audio in10seconds')
        await asyncio.sleep(10)
        vc = await self.play_audio(vc, channel, 'countdown')
        print('playing countdown')
        await asyncio.sleep(7)
        await vc.disconnect()
        print('disconnect from voice')

    async def play_audio(self, voice_client, channel, filename: str):
        if not filename.endswith('.mp3'):
            filename += '.mp3'
        source = FFmpegPCMAudio(str(bundled_data_path(self) / filename))
        if voice_client is None or (channel.id != voice_client.channel.id):
            vc = await channel.connect()
        else:
            vc = channel.guild.voice_client
        vc.play(source)
        return vc

    def __unload(self):
        for tk in self.autoscrim_tasks.values():
            tk.cancel()

    async def scrim_loop(self, guild, gamemode: str):
        print(f'scrim loop started for {guild}')
        as_on = await self.config.guild(guild).autoscrims_on()
        print(as_on)

        gameTextChannel_id = await self.config.guild(guild).get_raw(f'{gamemode.rstrip("s")}TextChannel')
        gameTextChannel = discord.utils.get(guild.text_channels, id=gameTextChannel_id)
        print(f'gtc, {gameTextChannel}')

        gameVoiceChannel_id = await self.config.guild(guild).get_raw(f'{gamemode.rstrip("s")}VoiceChannel')
        gameVoiceChannel = discord.utils.get(guild.voice_channels, id=gameVoiceChannel_id)
        print(f'gvc, {gameVoiceChannel}')

        def _valid_gamecode_check(m):
            cont = m.content
            try:
                assert gameTextChannel.id == m.channel.id and len(cont) == 3
                int(cont, 36)
            except AssertionError:
                return False
            except ValueError:
                return False

            return True


        while as_on is True:
            as_on = await self.config.guild(guild).autoscrims_on()
            print('as on? ', as_on)
            if not as_on:
                break

            await gameTextChannel.send(f"Okay, I will begin counting {gamemode.rstrip('s')}s in 2 minutes. After the countdown has finished, I will collect gamecodes for 1 minute in here.")
            print('countdown begin')
            await self.begin_countdown(guild.voice_client, gameVoiceChannel)
            print('countdown ended')

            print('gamecodes start')
            await gameTextChannel.send("**Gamecodes go here for the next minute.**")
            await gameTextChannel.set_permissions(guild.default_role, send_messages=True)


            gamecode_pool = []
            start = datetime.datetime.now()

            while (datetime.datetime.now() - start).total_seconds() < 60:
                try:
                    resp = await self.bot.wait_for('message', check=_valid_gamecode_check, timeout=max(1, 60 - (datetime.datetime.now()-start).total_seconds()))
                    gamecode_pool.append(resp)
                    print('found message')
                    continue
                except asyncio.TimeoutError:
                    print('timed out')
                    break

            await gameTextChannel.set_permissions(guild.default_role, send_messages=False)
            await gameTextChannel.send(self._build_lobby_display(gamecode_pool))
            await asyncio.sleep(60*(1/60))
            print('scrim looped')
            print('\n')
        print(f'scrim loop ended for {guild}')


    async def on_guild_join(self, ctx, guild):
        """
        Message the owner of the server to run the s.setup command
        along with a message explaining what happens during the
        setup process
        """
        try:
            await guild.owner.send(setup_string)
        except discord.Forbidden:
            print('Failed to deliver instructions to guild owner')
