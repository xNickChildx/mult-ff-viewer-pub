import configparser
import os
import sys
from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Collapsible, Label, DataTable, ListItem, ListView, Rule, Pretty
from textual.reactive import reactive

# try:
# 	from espn_api.football import League
# except ImportError:
# 	subprocess.call("cd espn-api; python3 setup.py install", shell=True)
# 	#exec('python3 espn-api/setup.py install')
# 	from espn_api.football import League

import importlib
if not os.path.exists('espn-api/espn_api/football'):
	print("No path espn-api/espn_api/football. Run `git submodule update --init --recursive`")
	sys.exit(1)

ff = importlib.import_module('espn-api.espn_api.football.league')
def get_team_under_name(league, user_name):
	for t in league.teams:
		for o in t.owners:
			if f"{o['firstName']} {o['lastName']}" in user_name:
				return t

	return None

def read_league(league, user_name):
	team = get_team_under_name(league, user_name)
	box_score = [x for x in league.box_scores() if x.home_team == team or x.away_team == team][0]
	is_away = team == box_score.away_team
	box_me = sorted(box_score.away_lineup if is_away else box_score.home_lineup, \
				key = lambda x: x.game_date if not x.on_bye_week else 0)
	box_them = sorted(box_score.home_lineup if is_away else box_score.away_lineup, \
				key = lambda x: x.game_date if not x.on_bye_week else 0)
	them = box_score.home_team if is_away else box_score.away_team 
	week = team.ties + team.losses + team.wins + 1
	return team.team_name, {'me': team, 'them': them, 'box_me': box_me, 'box_them': box_them, 'is_away': is_away, 'box': box_score, 'week': week}


class FFAPP(App):
	BINDINGS = [
	('q', 'quit', 'quit'),
	('n', 'next_user', 'next_user'),
	('r', 'refresh', 'refresh')]
	CSS_PATH = "fancay.tcss"
	data = reactive({}, recompose=True)
	def __init__(self, config):
		self.config = config
		tmp = self.config["team_info"]["user_name"].split()
		self.users = [f"{tmp[i]} {tmp[i+1]}" for i in range(0, len(tmp), 2) ]
		self.curr_user = 0
		super().__init__()
		self.update_data()

	def action_quit(self) -> None:
		sys.exit(0)
	def on_mount(self) -> None:
		self.title = self.users[self.curr_user]
	def compose(self) -> ComposeResult:
		"""Create child widgets for the app."""
		yield Header()
		# get unique timeslots
		slots = []
		for v in self.data.values():
			for players in v['box_me'] + v['box_them']:
				if players.game_date not in slots:
					slots.append(players.game_date)
		cols = ['name', 'points', 'projected']
		slots.sort()
		for t in slots:
			with Collapsible(title = t.strftime("%a %m/%d/%Y, %I:%M:%S") if t != 0 else "BYE"):
				for teams in self.data.keys():
					# who is winning this matchup?
					box = self.data[teams]['box']
					if self.data[teams]['is_away']:
						score_me = box.away_score
						score_them = box.home_score
						proj_me = box.away_projected
						proj_them = box.home_projected
					else:
						score_me = box.home_score
						score_them = box.away_score
						proj_me = box.home_projected
						proj_them =box.away_projected

					if score_me > score_them + 10:
						styles = "winning"
					elif score_them > score_me + 10:
						styles = "losing"
					else:
						styles = "tied"
					# horizontal per matchup at this timeslot
					with Horizontal(classes = styles):
						# vertical for my team + theirs
						# similar logic of displaying stuff my team vs theirs so loop it [title, box_players]
						matchup = [
							[f"{teams} - {score_me}/{proj_me}", self.data[teams]["box_me"]],
							[f"{self.data[teams]['them'].team_name} - {score_them}/{proj_them}", self.data[teams]["box_them"]]
						]
						for m in matchup:
							with VerticalScroll():
								yield Label(m[0], classes = "team")
								for player in filter(lambda p: p.game_date == t, m[1]):
									short_name = f"{player.name.split()[0][0]}. {player.name.split()[-1]}"
									points = player.points
									proj = player.projected_points
									is_benched = player.slot_position == "BE" or player.slot_position == "IR"
									player_css = "player benched" if is_benched else "player"
									# yield ListItem(Label(short_name, classes = "autosize"))
									p = Collapsible(title = f"{short_name} - {points}", classes = player_css)
									if proj and points:
										pct = min(1.0, round(points, 0) / (round(max(1, proj),0)*1.5))
										pct_diff = 1.0 - pct
										red_color = min(255, pct_diff*2 * 255)
										green_color = min(255, pct*2 * 255)
										print(f"for {player.name} got {red_color}, {green_color} {pct}, {points}/{proj}")
										p.styles.background = Color(red_color, green_color, 0, 0.2)
									with p:
										del player.stats[self.data[teams]["week"]]["projected_breakdown"]
										yield Pretty(str(player.stats[self.data[teams]["week"]]))

		yield Footer()

	
	def update_data(self):
		data_new = {}
		for l in self.config["team_info"]["league_ids"].split():
			k, v = read_league(ff.League(league_id=l, \
					year=int(self.config['team_info']['year']), \
					espn_s2 = self.config["secrets"]["espn_s2"], \
					swid = self.config["secrets"]["swid"]), \
				self.users[self.curr_user])
			while k in data_new.keys():
				k = k +"."
			data_new[k] = v
		self.data = data_new
	
	def action_refresh(self):
		self.update_data()

	def action_next_user(self):
		self.curr_user = (self.curr_user + 1 ) % len(self.users)
		self.on_mount()
		self.update_data()

config = configparser.RawConfigParser()
config.read('config')

app = FFAPP(config)
app.run()
