from redbot.core import data_manager
from .scrims import Scrims

async def setup(bot):
    cog = Scrims(bot)
    data_manager.load_bundled_data(cog, __file__)
    bot.add_cog(cog)
