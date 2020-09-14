# VandyBot [![inviteme](https://img.shields.io/static/v1?style=flat&logo=discord&logoColor=FFF&label=&message=invite&color=7289DA)](https://discord.com/api/oauth2/authorize?client_id=748705643757568080&permissions=247872&scope=bot)

VandyBot is a Discord bot written in discord.py for interfacing with various services at Vanderbilt University. Currently, supported services include Campus Dining & the COVID-19 Dashboard, but additional features including AnchorLink acess are in the works.

## Usage

All VandyBot commands are prefixed by a `~`. Current commands include:
* `~covid` to retrieve recent statistics on COVID-19 test results and positive cases (e.g. `~covid`)
* `~hours` to obtain facility operating hours (e.g. `~hours commons tomorrow`)
* `~menu` to access dining menus (e.g. `~menu ebi lunch today`)

Typing `~help` will list all available commands; help with specific commands can be accessed via `~help [command]` (e.g. `help menu`) or `~help [category]` (e.g. `help Dining`).

## Suggestions & Feedback

Bug reports, suggestions, and other feedback can be raised as issues on this repository. If VandyBot goes offline for any reason, message `kg583#8684` on Discord to restart the bot client. If connectivity issues persist, the bot may be moved to 3rd-party hosting service.

## Disclaimer

VandyBot is in no way official endorsed or licensed by Vanderbilt University or any of its affiliates. VandyBot utilizes basic web-scraping tools to access services, and thus its accuracy is dependent on the accuracy of its sources.
