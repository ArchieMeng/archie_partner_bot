from telegram.ext import Updater, Dispatcher
import commands

import logging

logging.basicConfig(format="%(asctime)s-%(name)s-%(levelname)s-%(message)s")

with open('_token', 'r') as rf:
    _token = rf.read()
updater = Updater(token=_token)
updater.dispatcher.add_handler(commands.start_handler)
updater.dispatcher.add_handler(commands.uppercase_handler)
updater.start_polling()
