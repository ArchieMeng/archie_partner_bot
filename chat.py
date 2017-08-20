import telegram
from telegram.ext import MessageHandler
from telegram.ext.dispatcher import run_async
import filters
from telegram.ext.filters import Filters
from pickle import dump

MESSAGE_HANDLERS = []


def set_message_handler(
        set_filters,
        allow_edited=False,
        pass_update_queue=False,
        pass_job_queue=False,
        pass_user_data=False,
        pass_chat_data=False,
        message_updates=True,
        channel_post_updates=True,
        edited_updates=False
):
    def decorate(func):
        MESSAGE_HANDLERS.append(
            MessageHandler(
                filters=set_filters,
                callback=func,
                allow_edited=allow_edited,
                pass_update_queue=pass_update_queue,
                pass_job_queue=pass_job_queue,
                pass_user_data=pass_user_data,
                pass_chat_data=pass_chat_data,
                message_updates=message_updates,
                channel_post_updates=channel_post_updates,
                edited_updates=edited_updates
            )
        )
        return func
    return decorate


@set_message_handler(set_filters=filters.test)
@run_async
def echo(bot: telegram.bot.Bot, update: telegram.Update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text=update.message.text
    )


@set_message_handler(set_filters=Filters.text)
@run_async
def record(bot: telegram.bot.Bot, update: telegram.Update):
    # just record message
    chat_id = update.message.chat_id
    # record messages using pickle
    with open("message_of_{}".format(chat_id), "a+b") as record_file:
        dump(update.message, record_file)
