from discord import Emoji


def emoji_id(emoji: Emoji) -> int | str:
    return emoji if type(emoji) is str else emoji.id
