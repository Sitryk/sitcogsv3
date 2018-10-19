from .lyrics import Lyrics
from . import genius
from colorama import Fore, Style

def setup(bot):
    if not genius._soupAvailable:
        err = "You need to run " + Fore.LIGHTRED_EX + "[p]pipinstall bs4 " + Style.RESET_ALL + 'with your bot in dev mode to use this cog.'
        raise RuntimeError(err)
    bot.add_cog(Lyrics(bot))
