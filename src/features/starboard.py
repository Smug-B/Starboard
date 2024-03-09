import logging
import os
import pickle
from datetime import datetime
from typing import Dict, Annotated, List, Tuple, Set

import discord
from discord import Guild, channel, Message, Embed, Reaction, User, Attachment, Member
from discord.ext import tasks, commands

from src.features.starboard_server import StarboardServer, load_reaction_data
from src.utils.bidictionary import BiDict
from src.utils.emoji import emoji_id


# noinspection PyMethodMayBeStatic
class Starboard(commands.Bot):
    server_data: Annotated[Dict[int, StarboardServer], "Associates a given server ID to its reaction data"]

    starboard_channels: Annotated[Dict[int, int], "Associates a given server ID to its respective starboard channel ID"]

    # This will probably also become a dictionary
    starboard_limiter: Annotated[int, "The number of reactions to qualify for starboard."] = 3

    def __init__(self, command_prefix: str, intents: discord.Intents):
        self.server_data = {}
        self.starboard_channels = {}
        super().__init__(command_prefix=command_prefix, help_command=None, intents=intents)

    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        for guild in self.guilds:
            if guild.id not in self.server_data:
                self.server_data[guild.id] = load_reaction_data(guild.id)

    # Actually gross
    async def safe_get_data(self, payload: discord.RawReactionActionEvent) -> \
            (tuple[Guild, int, channel, channel, Message] | None):
        guild: Guild = self.get_guild(payload.guild_id)

        starboard_channel_id: int = self.starboard_channels.get(payload.guild_id)
        if starboard_channel_id is None:
            return None

        starboard_channel: channel = guild.get_channel(starboard_channel_id)
        if starboard_channel is None:
            return None

        message_channel: channel = guild.get_channel(payload.channel_id)
        if message_channel is None:
            return None

        reacted_message: Message = await message_channel.fetch_message(payload.message_id)
        if reacted_message is None:
            return None

        return guild, starboard_channel_id, starboard_channel, message_channel, reacted_message

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        starboard_server: StarboardServer = self.server_data.get(payload.guild_id)
        if starboard_server is None:
            starboard_server = StarboardServer(payload.guild_id, BiDict(), {}, {})
            self.server_data[payload.guild_id] = starboard_server

        starboard_server.latest_reaction_time = datetime.now()
        starboard_server.reaction_channel[payload.message_id] = payload.channel_id

        data: tuple[Guild, int, channel, channel, Message] = await self.safe_get_data(payload)
        if data is None:
            return

        guild, starboard_channel_id, starboard_channel, message_channel, reacted_message = data

        if payload.user_id == reacted_message.author.id:
            return

        if payload.user_id != self.application_id and payload.message_id in starboard_server.reaction_data.backward:
            await self.handle_react_starboard(payload, starboard_server, guild, payload.message_id, reacted_message)
        else:
            cached_message_id: int = starboard_server.reaction_data.f_get(payload.message_id)
            if cached_message_id is None:
                await self.handle_send_starboard(payload, starboard_server, guild, starboard_channel, reacted_message)
            else:
                await self.handle_edit_starboard(starboard_server, guild, starboard_channel, cached_message_id,
                                                 reacted_message)

    async def handle_auto_reacts(self, starboard_message: Message, reacted_message: Message):
        for reaction in reacted_message.reactions:
            if (reaction.count >= self.starboard_limiter and
                    (type(reaction.emoji) is str or self.get_emoji(reaction.emoji.id) is not None)):
                await starboard_message.add_reaction(reaction.emoji)

    async def handle_react_starboard(self, payload: discord.RawReactionActionEvent,
                                     starboard_server: StarboardServer,
                                     guild: Guild,
                                     starboard_message_id: int,
                                     reacted_message: Message):
        """
        Handles the logic when a user opts to react to the starboard version of a message in lieu of the actual message.
        :param guild:
        :param payload:
        :param starboard_server:
        :param starboard_message_id:
        :param reacted_message:
        :return:
        """
        original_message_id = starboard_server.reaction_data.b_get(starboard_message_id)
        original_channel_id = starboard_server.reaction_channel.get(original_message_id)
        if original_message_id is None or original_channel_id is None:
            return

        original_message_channel = guild.get_channel(original_channel_id)
        message = await original_message_channel.fetch_message(original_message_id)
        if message is None:
            return

        embed: List[Embed] = await self.create_embed(message, guild)
        showcase_message, experience = await self.format_emojis(message.reactions,
                                                                reacted_message.reactions,
                                                                self.starboard_limiter,
                                                                message.author.id)
        if showcase_message is not None:
            await reacted_message.edit(content=showcase_message, embeds=embed)

        await self.update_server_experience(starboard_server, message, experience)

    async def handle_edit_starboard(self, starboard_server: StarboardServer,
                                    guild: Guild,
                                    starboard_channel: channel,
                                    starboard_message_id: int,
                                    reacted_message: Message):
        """
        Handles the logic when a user reacts to the original message after it has already reached starboard.
        :param guild:
        :param starboard_server:
        :param starboard_channel:
        :param starboard_message_id:
        :param reacted_message:
        :return:
        """
        message = await starboard_channel.fetch_message(starboard_message_id)
        if message is None:
            return

        embed: List[Embed] = await self.create_embed(reacted_message, guild)
        showcase_message, experience = await self.format_emojis(reacted_message.reactions,
                                                                message.reactions,
                                                                self.starboard_limiter,
                                                                reacted_message.author.id)
        if showcase_message is not None:
            await message.edit(content=showcase_message, embeds=embed)

        await self.handle_auto_reacts(message, reacted_message)
        await self.update_server_experience(starboard_server, reacted_message, experience)

    async def handle_send_starboard(self, payload: discord.RawReactionActionEvent,
                                    starboard_server: StarboardServer,
                                    guild: Guild,
                                    starboard_channel: channel,
                                    reacted_message: Message):
        """
        Handles the logic when a post gets reacted to, but has either not quite or just reached the threshold for entry
        into starboard.
        :param guild:
        :param payload:
        :param starboard_server:
        :param starboard_channel:
        :param reacted_message:
        :return:
        """
        embed: List[Embed] = await self.create_embed(reacted_message, guild)
        showcase_message, experience = await self.format_emojis(reacted_message.reactions,
                                                                None,
                                                                self.starboard_limiter,
                                                                reacted_message.author.id)
        if showcase_message is None:
            return

        message = await starboard_channel.send(content=showcase_message, embeds=embed)
        starboard_server.reaction_data[payload.message_id] = message.id
        await self.handle_auto_reacts(message, reacted_message)
        await self.update_server_experience(starboard_server, reacted_message, experience)
        starboard_server.save_reaction_data()

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        starboard_server: StarboardServer = self.server_data.get(payload.guild_id)
        if starboard_server is None:
            starboard_server = StarboardServer(payload.guild_id, BiDict(), {}, {})
            self.server_data[payload.guild_id] = starboard_server

        starboard_server.latest_reaction_time = datetime.now()

        data: tuple[Guild, int, channel, channel, Message] = await self.safe_get_data(payload)
        if data is None:
            return

        guild, starboard_channel_id, starboard_channel, message_channel, reacted_message = data

        if payload.user_id != self.application_id and payload.message_id in starboard_server.reaction_data.backward:
            await self.handle_react_starboard(payload, starboard_server, guild, payload.message_id, reacted_message)
        else:
            cached_message_id: int = starboard_server.reaction_data.f_get(payload.message_id)
            if cached_message_id is None:
                return
            else:
                await self.handle_edit_starboard(starboard_server, guild, starboard_channel, cached_message_id,
                                                 reacted_message)
        starboard_server.save_reaction_data()

    async def update_server_experience(self, starboard_server: StarboardServer, reacted_message: Message,
                                       experience: int):
        message_id: int = reacted_message.id
        author_id: int = reacted_message.author.id
        if author_id not in starboard_server.experience_leaderboard:
            starboard_server.experience_leaderboard[author_id] = {message_id: experience}
        else:
            starboard_server.experience_leaderboard.get(author_id)[message_id] = experience

    async def format_emojis(self, post_reactions: List[Reaction], starboard_reactions: List[Reaction] | None,
                            emoji_count_limiter: int,
                            post_author_id: int) -> Tuple[str | None, int]:
        output: str = ""
        reaction_tracker: Dict[int | str, set[int]] = {}
        if starboard_reactions is not None:
            for reaction in starboard_reactions:
                all_users: List[User] = await reaction.users().flatten()
                reaction_tracker[emoji_id(reaction.emoji)] = {user.id for user in all_users
                                                              if user.id != self.application_id
                                                              and user.id != post_author_id}

        experience: int = 0
        for reaction in post_reactions:
            all_users: List[User] = await reaction.users().flatten()
            reactors: Set[id] = {user.id for user in all_users if user.id != self.application_id
                                 and user.id != post_author_id}
            emoji_identifier: int | str = emoji_id(reaction.emoji)
            if emoji_identifier in reaction_tracker:
                reactors.update(reaction_tracker[emoji_identifier])

            reaction_experience: int = len(reactors)
            experience += reaction_experience
            if reaction_experience < emoji_count_limiter:
                continue
            output += f"{reaction.emoji} **{reaction_experience}**, "

        if output != "":
            return output[:-2] + f" **|** {post_reactions[0].message.jump_url}", experience
        return None, experience

    async def create_embed(self, message: discord.Message, guild: Guild) -> List[Embed]:
        output: List[Embed] = []

        def handle_multiple_attachments(handled_message: discord.Message, handled_embed: discord.Embed):
            attachment_count: int = len(handled_message.attachments)
            embed_count: int = len(handled_message.embeds)
            has_set_embed: bool = False
            if attachment_count == 0:
                if embed_count > 0:
                    if handled_message.embeds[0].image is not None:
                        handled_embed.set_image(url=handled_message.embeds[0].image.proxy_url)
                    else:
                        handled_embed.set_image(url=handled_message.embeds[0].url)
                    has_set_embed = True
                output.append(handled_embed)

            for i in range(0, attachment_count):
                attachment: Attachment = handled_message.attachments[i]
                if i == 0:
                    handled_embed.set_image(url=attachment.url)
                    output.append(handled_embed)
                else:
                    output.append(discord.Embed(image=attachment.url, color=handled_embed.colour))

            for i in range(0, embed_count):
                message_embed: Embed = handled_message.embeds[i]
                if has_set_embed and i == 0:
                    continue
                message_embed.colour = 0x70aeff
                output.append(message_embed)

        if message.reference is not None:
            replied_message: Message = await message.channel.fetch_message(message.reference.message_id)
            replied_author: Member = await guild.fetch_member(replied_message.author.id)
            replied_embed: Embed = discord.Embed(
                color=0x2b2d31,
                author=discord.EmbedAuthor(
                    name=f"Replying to {replied_author.display_name}",
                    url=replied_message.jump_url,
                    icon_url=replied_author.display_avatar.url),
                timestamp=replied_message.created_at,
                description=replied_message.content)
            handle_multiple_attachments(replied_message, replied_embed)

        message_author: Member = await guild.fetch_member(message.author.id)
        embed: Embed = discord.Embed(
            color=0x70aeff,
            author=discord.EmbedAuthor(
                name=message_author.display_name,
                url=message.jump_url,
                icon_url=message_author.display_avatar.url),
            timestamp=message.created_at,
            description=message.content)
        handle_multiple_attachments(message, embed)
        return output

    first_save: bool = True

    @tasks.loop(minutes=10)
    async def listen(self):
        if self.first_save:
            self.first_save = False
            return

        print(f"Attempting to save server data at: {datetime.now()}")
        await self.save()

    async def save(self):
        try:
            if not os.path.exists("data/"):
                os.makedirs("data/")

            with open(f"data/channel.pkl", "wb") as file:
                pickle.dump(obj=self.starboard_channels, file=file)

            for starboard_server in self.server_data.values():
                starboard_server.save_reaction_data()

            # self.reaction_data.clear()
        except Exception as exception:
            logging.log(logging.ERROR, exception)

    def load(self):
        try:
            if not os.path.exists(f"data/"):
                os.makedirs("data/")
                return

            with open(f"data/channel.pkl", "rb") as file:
                self.starboard_channels = pickle.load(file)

            for dirPath, dirNames, fileNames in os.walk("data/"):
                for dirName in dirNames:
                    if not dirName.isdigit():
                        continue
                    server_id = int(dirName)
                    self.server_data[server_id] = load_reaction_data(server_id)
        except Exception as exception:
            logging.log(logging.ERROR, exception)
