# VandyBot 3.0 [![inviteme](https://img.shields.io/static/v1?style=flat&logo=discord&logoColor=FFF&label=&message=invite&color=7289DA)](https://discord.com/api/oauth2/authorize?client_id=748705643757568080&permissions=247872&scope=bot) [![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/kg583/VandyBot.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/kg583/VandyBot/context:python)

VandyBot is a Discord bot written in discord.py for interfacing with various services at Vanderbilt University. Currently, supported services include Campus Dining & facility hours, but additional features including AnchorLink access are in the works.

## Usage

All VandyBot commands are prefixed by a `~`. Current commands include:
* `~github` to return a link to this repository (e.g. `~github`)
* `~hours` to obtain facility operating hours (e.g. `~hours central-library tomorrow`)
* `~menu` to access dining menus (e.g. `~menu ebi lunch today`)
* `~ping` to check VandyBot's latency (e.g. `~ping`)

Typing `~help` will list all available commands; help with specific commands can be accessed via `~help [command]` (e.g. `~help menu`) or `~help [category]` (e.g. `~help Dining`).

## Suggestions & Feedback

Bug reports, suggestions, and other feedback can be raised as issues on this repository. If VandyBot goes offline for any reason, message `kg583#8684` on Discord to restart the bot client. If connectivity issues persist, the bot may be moved to a 3rd-party hosting service.

## Disclaimer

VandyBot is in no way officially endorsed or licensed by Vanderbilt University or any of its affiliates. VandyBot utilizes basic web-scraping tools and minimal API systems to access services, and thus its accuracy is dependent on the accuracy of its sources.

VandyBot is not currently subject to privileged content restraints or bot verification requirements. Nevertheless, VandyBot adheres to all Discord policies concerning data access and storage; no personally-identifying information is ever saved by VandyBot or any of its component programs. Any and all necessarily persistent data concerns server-level information only, and cannot be used to identify server members or other private server attributes. 

If you believe any elements of VandyBot's code or design frameworks violate the above guidelines or simply do not realize such goals in the most safe, effective, or efficient manner possible, please do not hesitate to raise a relevant issue on this repository or contact the repository owner to provide your suggestion(s).
