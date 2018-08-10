from telegram.ext import BaseFilter


class FilterTest(BaseFilter):
    def filter(self, message):
        if message and message.text:
            return message.text.startswith("test")
        else:
            return False


test = FilterTest()
