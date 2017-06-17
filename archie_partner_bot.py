from telegram.ext import Updater, Dispatcher
import telegram
import commands

import logging

logging.basicConfig(
    filename="bot.log",
    format="%(asctime)s-%(name)s-%(levelname)s-%(message)s",
    level=logging.DEBUG
)

with open('_token', 'r') as rf:
    _token = rf.read()
updater = Updater(token=_token)
dispatcher = updater.dispatcher


def error_callback(bot: telegram.Bot, update: telegram.Update, error: telegram.TelegramError):
    logging.error(
        msg="An TelegramError occur when processing message:{message}".format(message=update.message.text),
        error=':'.join([error, error.message])
    )
    bot.send_message(
        chat_id=update.message.chat_id,
        text="Something wrong happened. Message: \"{message}\" raise {error}".format(
            message=update.message.text,
            error=''.join([error, error.message])
        )
    )

for handler in commands.COMMAND_HANDLERS:
    dispatcher.add_handler(handler)
dispatcher.add_error_handler(error_callback)
updater.start_polling()
