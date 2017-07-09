# Archie Partner Bot

Source code of telegram bot @archie_partner_bot.

## Getting Started

These instructions will get you a copy of the Archie Partner Bot and running on your local machine or remote server.

### Prerequisites

1. Ask @BotFather for token to develop your bot on Telegram. And then, save token into a file named _token
2. install Python module [lru-dict](https://github.com/amitdev/lru-dict) which is required by submodule: GelbooruViewer.
3. install python-telegram-bot
4. upgrade Python to 3.5+

### Installation
```bash
git clone https://github.com/ArchieMeng/archie_partner_bot.git
cd archie_partner_bot
git submodule update --init --recursive
sudo pip3 install lru-dict, python-telegram-bot
```

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE.md](LICENSE) file for details

## Acknowledgments

* Command handler might fail when too many messages received at the same time. 
