from .cog import EconomyTrickle

async def setup(bot):
    cog = EconomyTrickle()
    bot.add_cog(cog)
