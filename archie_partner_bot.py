from telegram.ext import Updater, Dispatcher
import telegram
import commands
import chat

import os
import sys
import logging

file_path = os.path.dirname(__file__)
logging.basicConfig(
    filename=file_path + '/' + "bot.log",
    format="%(asctime)s-%(name)s-%(levelname)s-%(message)s",
    level=logging.ERROR
)

_token_path = os.path.join(file_path, '_token')
with open(_token_path, 'r') as rf:
    _token = rf.read()
updater = Updater(token=_token, workers=16)
dispatcher = updater.dispatcher


def error_callback(bot: telegram.Bot, update: telegram.Update, error: telegram.TelegramError):
    logging.error(
        msg="An TelegramError occur when processing message".
            format(error=':'.join([str(error), str(error.message)]))
    )

for handler in commands.COMMAND_HANDLERS:
    dispatcher.add_handler(handler)
for handler in chat.MESSAGE_HANDLERS:
    dispatcher.add_handler(handler)

dispatcher.add_error_handler(error_callback)
updater.start_polling()
