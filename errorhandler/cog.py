import logging
import traceback
import textwrap
import io
from contextlib import redirect_stdout

from redbot.core import checks, commands, Config, utils
from redbot.core.dev_commands import Dev
import discord

log = logging.getLogger('red')

cf = utils.chat_formatting

default_reply = "await ctx.send(f\"`Error in command '{ctx.command.qualified_name}'. Check your console or logs for details.`\")"
GLOBAL_DEFAULT = {'response': default_reply}


class ErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, int('sitryk', 36), force_registration=True)
        self.config.register_global(**GLOBAL_DEFAULT)
        self._old_handler = self.bot.on_command_error
        self._eval_string = None

        bot.on_command_error = self.on_command_error

    async def on_command_error(self, ctx, error, unhandled_by_cog=False):
        if isinstance(error, commands.CommandInvokeError):
            # let me know if you want that generate error ticket ID feature here
            # logging and stuff is straight out of events.py to make sure those
            # still occur for this error type
            cmd = ctx.command

            log.exception(f"Exception in command '{cmd.qualified_name}'", exc_info=error.original)
            exception_log = f"Exception in command '{cmd.qualified_name}'\n"
            exception_log += "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            ctx.bot._last_exception = exception_log

            eh_cog = ctx.bot.get_cog("ErrorHandler")
            if eh_cog._eval_string is None:
                eh_cog._eval_string = await eh_cog.config.response()

            # redbot.core.dev_commands L186 helped a bunch here
            # also could probably use locals() here but don't care
            env = {
                'ctx': ctx,
                'error': error,
                'discord': discord,
                'cf': cf
            }

            to_compile = "async def func():\n%s" % textwrap.indent(eh_cog._eval_string, "  ")
            try:
                compiled = Dev.async_compile(to_compile, "<string>", "exec")
                exec(compiled, env)
            except SyntaxError as e:
                return await ctx.send(Dev.get_syntax_error(e))

            func = env["func"]
            await func()
            return
        await self._old_handler(ctx, error, unhandled_by_cog)

    def cog_unload(self):
        self.bot.on_command_error = self._old_handler

    @commands.group()
    @checks.is_owner()
    async def errorhandler(self, ctx):
        """
        Set and view the code for when a CommandInvokeError is raised.
        """
        pass

    @errorhandler.command(name="view")
    async def view_handler(self, ctx):
        """
        View the string set to eval when a CommandInvokeError is raised.
        """
        r = await self.config.response()
        await ctx.send(f"The current evaluated code is```py\n{r}\n```")

    @errorhandler.command(name="set")
    async def set_handler(self, ctx, *, code):
        """
        Set the string to evaluate, use a python code block.

        Environment variables:
            cf      - redbot.core.utils.chat_formatting module
            ctx     - context of invokation
            error   - the error that was raised
            discord - discord.py library
        """
        body = Dev.cleanup_code(code)
        await self.config.response.set(value=body)
        await ctx.send(f"Handler code set to\n```py\n{body}\n```\nIt's recommended that you test the handler by running `{ctx.prefix}errorhandler test`")
        self._eval_string = body

    @errorhandler.command(name='test')
    async def test_handler(self, ctx):
        """
        This command contains an AssertionError purposely so that you can make sure your handler works
        """
        assert False