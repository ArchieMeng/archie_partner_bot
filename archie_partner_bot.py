from telegram.ext import Updater, Dispatcher
import commands

import logging

logging.basicConfig(format="%(asctime)s-%(name)s-%(levelname)s-%(message)s")

with open('_token', 'r') as rf:
    _token = rf.read()
updater = Updater(token=_token)
dispatcher = updater.dispatcher

for handler in commands.COMMAND_HANDLERS:
    dispatcher.add_handler(handler)
updater.start_polling()
