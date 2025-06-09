import json
import logging

from django.conf import settings
from django.http import HttpResponse

from .misc import feed_raw_update

logger = logging.getLogger(__name__)


async def process_update(request):
    bot_secret_key = request.META.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN")
    if not bot_secret_key:
        return HttpResponse("Missing telegram bot API secret key", status=401)
    if not request.META.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN") == settings.BOT_WEBHOOK_SECRET:
        return HttpResponse("bot API secret key is invalid", status=401)
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        try:
            await feed_raw_update(json.loads(body_unicode))
        except Exception as e:
            logger.exception(e)
        return HttpResponse(status=200)
    return HttpResponse('Method not allowed', status=405)


process_update.csrf_exempt = True