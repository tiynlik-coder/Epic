"""Global error handler."""

from config import log


async def error_handler(update,ctx): log.exception("Unhandled error",exc_info=ctx.error)
