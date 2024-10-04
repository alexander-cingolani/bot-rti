from pydantic import BaseModel, Field
from pydantic.alias_generators import to_pascal


class RaceRoomSessionLap(BaseModel):
    time: int
    sector_times: list[int]
    position_in_class: int
    valid: bool
    position: int
    pit_stop_occurred: bool = Field(alias="PitStopOccured")

    class Config:
        alias_generator = to_pascal


class RaceRoomPlayer(BaseModel):
    rre_id: int = Field(alias="UserId")
    position: int
    position_in_class: int
    start_position: int
    start_position_in_class: int
    best_lap_time: int
    total_time: int
    finish_status: str
    fast_lap: bool
    laps: list[RaceRoomSessionLap] = Field(alias="RaceSessionLaps")

    class Config:
        alias_generator = to_pascal


class RaceRoomSession(BaseModel):
    session_type: str = Field(alias="Type")
    players: list[RaceRoomPlayer] = Field(alias="Players")

    def remove_wild_cards(self, expected_player_ids: list[int]) -> None:
        non_wildcard_players: list[RaceRoomPlayer] = []
        wild_card_counter = 0
        for player in self.players:
            if player.rre_id in expected_player_ids:
                player.position_in_class -= wild_card_counter
                player.position -= wild_card_counter
                non_wildcard_players.append(player)
            else:
                wild_card_counter += 1
        self.players = non_wildcard_players

    def fastest_lap_scorer(self) -> int:
        fastest_lap = float("inf")
        driver_with_fastest_lap = 0
        for player in self.players:
            for lap in player.laps:
                if lap.time <= 0:
                    continue

                if lap.time > 0 and lap.time < fastest_lap:
                    driver_with_fastest_lap = player.rre_id
                    fastest_lap = lap.time

        return driver_with_fastest_lap

    def gap_to_winner(self, player: RaceRoomPlayer) -> int:
        gap_to_first = 0
        for winners_lap, players_lap in zip(self.players[0].laps, player.laps):
            if players_lap.time > 0:
                gap_to_first += players_lap.time - winners_lap.time
                continue

            for winner_sector, player_sector in zip(
                reversed(winners_lap.sector_times),
                reversed(players_lap.sector_times),
            ):
                if player_sector > 0:
                    gap_to_first += player_sector - winner_sector
        return gap_to_first


class RaceRoomResultsSchema(BaseModel):
    server_id: str = Field(alias="ID")
    server: str
    time: int
    championship_id: int = Field(alias="IdCampionato")
    sessions: list[RaceRoomSession]

    class Config:
        alias_generator = to_pascal
