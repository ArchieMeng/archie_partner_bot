import telegram
from telegram.ext import CommandHandler


def start(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="My name is Altair, Archie Meng's partner"
    )


def uppercase(bot: telegram.bot.Bot, update: telegram.Update, args):
    bot.send_chat_action(telegram.ChatAction.TYPING)

    if args:
        uppercase_args = ' '.join([arg.upper() for arg in args])
        bot.send_message(
            chat_id=update.message.chat_id,
            text=uppercase_args
        )
    else:
        help_text = '''
            uppercase usage:
                /upper <string>
        '''
        bot.send_message(
            chat_id=update.message.chat_id,
            text=help_text
        )



start_handler = CommandHandler(
    command='start',
    callback=start
)
uppercase_handler = CommandHandler(
    command='upper',
    callback=uppercase,
    pass_args=True
)
i = 1
