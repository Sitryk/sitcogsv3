from .cog import ErrorHandler

async def setup(bot):
    bot.add_cog(ErrorHandler(bot))