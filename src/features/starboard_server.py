import logging
import os
import pickle
from datetime import datetime
from typing import Dict

from src.utils.bidictionary import BiDict


class StarboardServer:
    """
    Encapsulates all the data associated with a server that the bot may utilize for starboard purposes.
    """

    server_ID: int
    """
    The unique snowflake used by Discord to identify a server.
    """

    reaction_data: BiDict[int, int]
    """
    A bi-directional dictionary that maps the message ID of a starboard-ed post to its starboard-showcase variant.
    This is bi-directional as in, knowing one variable allows you to access its respective counterpart. 
    """

    reaction_channel: Dict[int, int]
    """
    A dictionary that maps the message ID of a starboard-ed post to its channel ID. 
    """

    experience_leaderboard: Dict[int, Dict[int, int]]
    """
    A dictionary that maps the snowflake of a user to a subsequent dictionary that matches a message ID to its number
    of unique reactions.
    """

    latest_reaction_time: datetime | None
    """
    The last time a message had a reaction modification in this server.
    Defaults to None if server data has been saved and no new reactions have been added for a while.
    """

    def __init__(self, server_id: int,
                 reaction_data: BiDict[int, int],
                 experience_leaderboard: Dict[int, Dict[int, int]],
                 reaction_channel: Dict[int, int]) -> None:
        self.server_ID = server_id
        self.reaction_data = reaction_data
        self.experience_leaderboard = experience_leaderboard
        self.reaction_channel = reaction_channel

    def __str__(self):
        return f"[{self.server_ID}, {self.reaction_data}]"

    def get_experience(self, user_id: int) -> int:
        """
        Calculates the total acquired experience of a given user from a user ID. Returns 0 if said user has no logged
        experience points.
        :param user_id: The snowflake of the user whose experience is requested.
        :return: A number representing the total amount of starboard experience the user associated with the given user
        ID has acquired.
        """
        starboard_data: Dict[int, int] = self.experience_leaderboard.get(user_id)
        if starboard_data is None:
            return 0

        experience: int = 0
        for reaction_count in starboard_data.values():
            experience += reaction_count
        return experience

    def save_reaction_data(self):
        try:
            if self.latest_reaction_time is None or (datetime.now() - self.latest_reaction_time).total_seconds() < 600:
                return

            save_dir: str = f"data/{self.server_ID}/"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            with open(f"{save_dir}reaction_data.pkl", "wb") as file:
                pickle.dump(obj=self.reaction_data.forward, file=file)

            with open(f"{save_dir}reaction_channel.pkl", "wb") as file:
                pickle.dump(obj=self.reaction_channel, file=file)

            with open(f"{save_dir}experience_leaderboard.pkl", "wb") as file:
                pickle.dump(obj=self.experience_leaderboard, file=file)

            self.latest_reaction_time = None
        except Exception as exception:
            logging.log(logging.ERROR, exception)


def load_reaction_data(server_id: int) -> StarboardServer:
    try:
        reaction_data = BiDict()
        with open(f"data/{server_id}/reaction_data.pkl", "rb") as file:
            temp_reaction_data: Dict[int, int] = pickle.load(file)
            reaction_data.forward = temp_reaction_data
            reaction_data.backward = {value: key for key, value in temp_reaction_data.items()}

        reaction_channel:  Dict[int, int]
        with open(f"data/{server_id}/reaction_channel.pkl", "rb") as file:
            reaction_channel = pickle.load(file)

        experience_leaderboard: Dict[int, Dict[int, int]]
        with open(f"data/{server_id}/experience_leaderboard.pkl", "rb") as file:
            experience_leaderboard = pickle.load(file)
        return StarboardServer(server_id, reaction_data, experience_leaderboard, reaction_channel)

    except Exception as exception:
        logging.log(logging.ERROR, exception)
        return StarboardServer(server_id, BiDict(), {}, {})
