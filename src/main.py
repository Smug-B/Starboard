import asyncio
import datetime
from typing import List, Tuple, Dict

import discord
from discord import TextChannel, Embed, ApplicationContext, Interaction
from discord.ui import Button, Item

from src.features.starboard import Starboard

from src.features.starboard_server import StarboardServer

intents = discord.Intents.default()
intents.message_content = True

client = Starboard(command_prefix='$', intents=intents)
client.load()


@client.slash_command(description="Fetches the bot's latency.")
async def ping(ctx):  # a slash command will be created with the name "ping"
    await ctx.respond(f"Latency is at {round(client.latency * 1000, 2)} ms.")


@client.slash_command(description="Sets the server's starboard channel.")
async def set(ctx: ApplicationContext, channel: discord.Option(TextChannel)):
    if ctx.author.guild_permissions.administrator:
        text_channel: TextChannel = channel
        client.starboard_channels[text_channel.guild.id] = text_channel.id
        await ctx.respond(f"{text_channel.jump_url} has been designated as the server's starboard channel.")
    else:
        await ctx.respond(f"👅 𝔉𝔯𝔢𝔞𝔨𝔶 𝔐𝔬𝔡𝔢 𝔄𝔠𝔱𝔦𝔳𝔞𝔱𝔢𝔡; I'm gonna touch you {ctx.author.global_name} 👅.", ephemeral=True)


class LeaderboardView(discord.ui.View):  # Create a class called MyView that subclasses discord.ui.View
    view: int
    content: List[str]
    max_view: int
    view_count: int
    date_time: datetime.datetime

    first_button: Button
    previous_button: Button
    status_button: Button
    next_button: Button
    last_button: Button

    def __init__(self, content: List[str], date_time: datetime, *items: Item):
        super().__init__(*items)
        self.view = 0
        self.content = content
        self.view_count = 10
        self.max_view = len(content) // self.view_count
        self.date_time = date_time

        for child in self.children:
            if type(child) is discord.ui.Button:
                if child.custom_id == "first":
                    self.first_button = child
                elif child.custom_id == "previous":
                    self.previous_button = child
                elif child.custom_id == "status":
                    self.status_button = child
                elif child.custom_id == "next":
                    self.next_button = child
                elif child.custom_id == "last":
                    self.last_button = child

        self.update_status()
        if self.view == self.max_view:
            self.next_button.disabled = True
            self.last_button.disabled = True

    async def generate_embed(self) -> discord.Embed:
        return discord.Embed(
            color=0x70aeff,
            title="Leaderboard",
            timestamp=self.date_time,
            description="\n".join(self.content[(self.view * self.view_count):
                                               min((self.view + 1) * self.view_count, len(self.content))]))

    def update_status(self):
        self.status_button.label = f"{self.view + 1} / {self.max_view + 1}"

    async def on_timeout(self):
        self.content.clear()
        self.disable_all_items()

    @discord.ui.button(label="<<", style=discord.ButtonStyle.grey, disabled=True, custom_id="first")
    async def first_page(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        self.view = 0
        button.disabled = True
        self.previous_button.disabled = True
        if self.view < self.max_view:
            self.next_button.disabled = False
            self.last_button.disabled = False
        self.update_status()
        embed: Embed = await self.generate_embed()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.grey, disabled=True, custom_id="previous")
    async def previous_page(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        self.view -= 1
        if self.view == 0:
            button.disabled = True
            self.first_button.disabled = True
        if self.view < self.max_view:
            self.next_button.disabled = False
            self.last_button.disabled = False
        self.update_status()
        embed: Embed = await self.generate_embed()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="1", style=discord.ButtonStyle.grey, custom_id="status", disabled=True)
    async def current_status(self, button: Button, interaction: Interaction):
        await interaction.response.defer()

    @discord.ui.button(label=">", style=discord.ButtonStyle.grey, custom_id="next")
    async def next_page(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        self.view += 1
        if self.view == self.max_view:
            button.disabled = True
            self.last_button.disabled = True
        if self.view > 0:
            self.previous_button.disabled = False
            self.first_button.disabled = False
        self.update_status()
        embed: Embed = await self.generate_embed()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.grey, custom_id="last")
    async def last_page(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        self.view = self.max_view
        button.disabled = True
        self.next_button.disabled = True
        if self.view > 0:
            self.previous_button.disabled = False
            self.first_button.disabled = False
        self.update_status()
        embed: Embed = await self.generate_embed()
        await interaction.message.edit(embed=embed, view=self)


@client.slash_command(description="View the starboard leaderboard.")
async def leaderboard(ctx: ApplicationContext):
    starboard_server: StarboardServer = client.server_data.get(ctx.guild.id)
    experience_values: Dict[int, int] = {}
    for user_id, user_xp_values in starboard_server.experience_leaderboard.items():
        experience_values[user_id] = sum(user_xp_values.values())

    sorted_experience_values: List[Tuple[int, int]] = sorted(experience_values.items(), key=lambda item: -item[1])
    leaderboard_messages: List[str] = []
    for i in range(0, len(sorted_experience_values)):
        sorted_user_id, sorted_user_xp_values = sorted_experience_values[i]
        leaderboard_messages.append(f"`#{i + 1}` <@{sorted_user_id}> - {sorted_user_xp_values} XP")
    now: datetime = datetime.datetime.now()
    replied_embed: Embed = discord.Embed(
        color=0x70aeff,
        title="Leaderboard",
        timestamp=now,
        description="\n".join(leaderboard_messages[0:min(10, len(leaderboard_messages))]))
    view: LeaderboardView = LeaderboardView(leaderboard_messages, now)
    await ctx.respond(embed=replied_embed, view=view)


token: str
with open("token.txt", "r") as file:
    token = file.readline()


async def main():
    async with client:
        client.listen.start()
        await client.start(token)


asyncio.run(main())
