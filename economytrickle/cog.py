import datetime
from random import randint
from math import floor
import asyncio
import logging

from redbot.core import commands, Config, bank
import discord


DEFAULT_GUILD = {
    'enabled': False,s
    'payout_chance': 50,
    'new_active_bonus': 1,
    'active_bonus_deflate': 1,
    'payout_interval': 2,
    'payout_per_active': 1,
    'active_timeout': 10,
    'channels': [],
    'base_payout': 0,
}


class EconomyTrickle(commands.Cog):

    def __init__(self):
        self.config = Config.get_conf(self, int('irdumbs', 36), force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)

        self.active_users = {}
        self.current_user = {}
        self.trickle_pot = {}
        self.previous_drip = {}

    @commands.group()
    async def trickleset(self, ctx):
        """
        Changes economy trickle settings
            Trickle amount:
                base amount + (# active users - 1) x multiplier + bonus pot
            Every active user gets the trickle amount. 
            It is not distributed between active users.
        """
        pass

    @trickleset.command()
    async def enabled(self, ctx, state: bool):
        """
        Toggles trickling in a guild
        [p]trickleset
        """
        await self.config.guild(ctx.guild).enabled.set(value=state)
        fmt = {False: '**disabled**', True: '**enabled**'}

        await ctx.send(f'Trickling is now {fmt[state]} in this guild')

    @trickleset.command()
    async def chance(self, ctx, percentage: int):
        """
        Sets percentage chance that the trickle will be successful [0-100]
        """
        if not 0 < percentage < 100:
            await ctx.send('Percentage must be in range 0 - 100.')
            return

        if percentage == 0:
            await ctx.send('```fix\n'
                           'Warning: This will stop all trickling '
                           'you may aswell unload this package.'
                           '```')
        await self.config.guild(ctx.guild).payout_chance.set(value=percentage)
        await ctx.send(f'Payout chance is set to {percentage}%')

    @trickleset.command(name='base')
    async def base_amount(self, ctx, amount: int):
        """
        Sets the base amount to give to every active user.

        Every trickle, active users will get at least this amount
        """
        if amount < 0:
            await ctx.send('```fix\n'
                           'Warning: Base amount should be positive '
                           'unless you want to discourage conversations'
                           '```')

        await self.config.guild(ctx.guild).base_payout.set(value=amount)
        await ctx.send(f'Base payout set to `{amount}`')
        
    @trickleset.command(name='leak')
    async def bonus_deflate(self, ctx, amount: int):
        """
        Sets the bonus pot leak amount.

        Whenever a trickle occurs (successful or not),
        this amount is taken out of the bonus pot
        """
        if amount < 0:
            await ctx.send('```fix\n'
                           'Warning: The bonus pot does not reset each '
                           'trickle. With a negative leak, the bonus pot '
                           'will grow each time a trickle occurs.'
                           '```')
        await self.config.guild(ctx.guild).active_bonus_deflate.set(value=amount)
        await ctx.send(f'Bonus pot leak is now `{amount}`')

    @trickleset.command(name='bonus')
    async def activebonus(self, ctx, amount: int):
        """
        Sets the bonus amount per new active user.

        When there is a new active user,
        this amount will be added to the bonus pot
        """
        if amount < 0:
            await ctx.send('```fix\n'
                           'Warning: Bonus amount should be positive '
                           'unless you want to discourage conversations'
                           '```')
        await self.config.guild(ctx.guild).new_active_bonus.set(value=amount)
        await ctx.send(f"Bonus per new active user is now `{amount}`")

    @trickleset.command()
    async def multiplier(self, ctx, amount: int):
        """
        Sets the amount added to the trickle amount per active user.
        """

        if amount < 0:
            await ctx.send("```fix\n"
                           'Warning: A negative multiplier would '
                           'be taking away currency the more active '
                           'users you have. This will discourage '
                           'conversations.'
                           '```')
        await self.config.guild(ctx.guild).payout_per_active.set(value=amount)
        await ctx.send(f'Base payout per active user is now `{amount}`')

    @trickleset.command()
    async def interval(self, ctx, minutes: float):
        """
        Sets the interval that must pass between each trickle
        """
        if minutes <= 0:
            await ctx.send('```fix\n'
                           'Warning: With an interval this low, '
                           'a trickle will occur after every message'
                           '```')
        await self.config.guild(ctx.guild).payout_interval.set(value=minutes)
        await ctx.send(f'Payout interval is now `{minutes}` minutes')

    @trickleset.command()
    async def timeout(self, ctx, minutes: float):
        """
        Sets the amount of time a user is considered active after sending a message
        """
        if minutes <= 0:
            await ctx.send('Timeout interval must be more than `0` minutes')
            return
        await self.config.guild(ctx.guild).active_timeout.set(value=minutes)
        await ctx.send(f'Active user timeout is now `{minutes}` minutes')

    @trickleset.command(usage='<one or more channels>')
    async def channel(self, ctx, *possible_channels: discord.TextChannel):
        """
        Toggles trickling in one or more channels
        Leaving blank will list the current trickle channels
        """
        gcnf = self.config.guild(ctx.guild)
        fmt = ''

        if not await gcnf.enabled() :
            fmt = ('Note: You will not see these changes take effect '
                   'until you set `{}trickleset enable on` to '
                   '**channels**.\n'.format(ctx.clean_prefix))

        csets = await gcnf.channels()
        current = sorted(filter(None, (ctx.guild.get_channel(c) for c in csets)),
                         key=lambda c: c.position)
        channels = set(possible_channels)

        if not channels:  # no channels specified
            if not current:
                fmt += 'There are no channels set to specifically trickle in.'
            else:
                fmt += ('Channels to trickle in:\n' +
                        '\n'.join('\t' + c.mention for c in current))
            return await ctx.send(fmt)

        current = set(current)
        overlap_choice = ''
        if not (channels.isdisjoint(current) or  # new channels
                current.issuperset(channels)):   # remove channels
            await ctx.send('Some channels listed are already in the '
                           'trickle list while some are not. Trickle'
                           ' to all the channels you listed, stop '
                           'trickling to them, or cancel? '
                           '`(all/stop/cancel)`')
            try:
                msg = await ctx.bot.wait_for('message', 
                                              timeout = 30,
                                              check = lambda m: m.author.id == ctx.author.id and \
                                                    ctx.channel.id == m.channel.id \
                                                    and m.content in ('all', 'stop', 'cancel'))
                overlap_choice = msg.content.lower()
            except asyncio.TimeoutError:
                overlap_choice = None

            
            if overlap_choice not in ('all', 'stop'):
                return ctx.send('Cancelling. Trickle '
                                'Channels are unchanged.')

        if overlap_choice == 'all' or channels.isdisjoint(current):
            current.update(channels)
        else:
            current -= channels

        await gcnf.channels.set(value=[c.id for c in current])
        await ctx.send(f'Trickle channels updated.\n{fmt}')

    @trickleset.command(name='settings')
    async def current_settings(self, ctx):
        """
        Display current settings
        """
        settings = await self.config.guild(ctx.guild).all()
        print(settings)
        form = '```\n'
        for k, v in settings.items():
            if k == 'channels':
                continue
            n = k.replace('_', ' ')
            form += f'{n.title()}: {v}\n'

        chnls = [ctx.guild.get_channel(_id).name for _id in settings['channels']]
        form += '\nChannels: ' + ', '.join(chnls) if chnls else '' 
        form += '```'

        await ctx.send(form)

    async def on_message(self, msg):
        """
        message listener that decides when to trickle
        """
        guild_conf = self.config.guild(msg.guild)
        enabled = await guild_conf.enabled()
        channels = await guild_conf.channels()

        if not msg.guild or msg.author.bot or not enabled or msg.channel.id not in channels:
            return

        gid = msg.guild.id
        author = msg.author

        current_user = self.current_user.get(gid, None)
        diff_user = current_user != author.id

        if diff_user:
            self.current_user[gid] = author.id
            now = datetime.datetime.now()
            active_users = self.active_users.get(gid, None)
            if gid in self.active_users.keys():
                if self.current_user[gid] not in active_users.keys():
                    nab = await guild_conf.new_active_bonus()
                    self.trickle_pot[gid] += nab
            else:
                self.active_users[gid] = {}
                self.trickle_pot[gid] = 0
            self.active_users[gid][msg.author.id] = now

            payout_interval = await guild_conf.payout_interval()
            threshold = (now - datetime.timedelta(minutes=payout_interval))
            if gid not in self.previous_drip.keys():
                self.previous_drip[gid] = now
            elif self.previous_drip[gid] < threshold:
                self.previous_drip[gid] = now

                trickle_amount = 0
                chance = await guild_conf.payout_chance()
                if randint(1, 100) <= chance:
                    number_active = len(self.active_users[gid])
                    base_payout = await guild_conf.base_payout()
                    payout_per_active = await guild_conf.payout_per_active()
                    trickle_amount = floor(base_payout + (number_active-1) * payout_per_active + self.trickle_pot[gid])

                active_timeout = await guild_conf.active_timeout()
                expiry_time = now - datetime.timedelta(minutes=active_timeout)

                tmplist = []
                for uid in self.active_users[gid].keys():
                    u_obj = msg.guild.get_member(uid)

                    if self.active_users[gid][uid] < expiry_time or u_obj is None:
                        templist.append(uid)
                    else:
                        await bank.deposit_credits(u_obj, trickle_amount)
                        logging.debug(f'Trickled {trickle_amount} to {u_obj}')

                for uid in tmplist:
                    del self.active_users[gid][uid]

                abd = await guild_conf.active_bonus_deflate()
                if self.trickle_pot[gid] > 0:
                    self.trickle_pot[gid] -= abd

                if self.trickle_pot[gid] < 0:
                    self.trickle_pot[gid] = 0
