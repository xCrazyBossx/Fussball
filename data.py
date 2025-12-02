import requests
import pandas as pd
import streamlit as st
import time

# Basis-URL Football-Data.org
FD_BASE_URL = "https://api.football-data.org/v4/competitions"

def make_api_request(url, headers, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                wait_time = 2 ** (i + 1)
                time.sleep(wait_time)
                continue
            else:
                return None
        except:
            return None
    return None

def fetch_matches_external(api_key, competition_id, season_year=None):
    if not api_key: return pd.DataFrame(), {}
        
    headers = { 'X-Auth-Token': api_key }
    url = f"{FD_BASE_URL}/{competition_id}/matches"
    if season_year: url += f"?season={season_year}"
    
    data = make_api_request(url, headers)
    if not data: return pd.DataFrame(), {}
        
    matches = []
    team_logos = {}
    
    for match in data.get('matches', []):
        home = match.get('homeTeam', {})
        away = match.get('awayTeam', {})
        
        # FIX: Matches ohne Teamnamen überspringen (verhindert 'None' in Tabelle)
        if not home.get('name') or not away.get('name'):
            continue

        score = match.get('score', {}).get('fullTime', {})
        
        if 'crest' in home: team_logos[home['name']] = home['crest']
        if 'crest' in away: team_logos[away['name']] = away['crest']
        
        is_finished = match.get('status') == 'FINISHED'
        home_goals = score.get('home')
        away_goals = score.get('away')
        
        matches.append({
            'Date': match.get('utcDate'),
            'HomeTeam': home.get('name'),
            'AwayTeam': away.get('name'),
            'HomeGoals': int(home_goals) if home_goals is not None else 0,
            'AwayGoals': int(away_goals) if away_goals is not None else 0,
            'Finished': is_finished,
            'Stage': match.get('stage') # Wichtig für CL Filterung
        })
        
    df = pd.DataFrame(matches)
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'])
        
    return df, team_logos

def calculate_current_table(df):
    if df.empty: return pd.DataFrame(columns=['Punkte', 'Tore', 'Spiele', 'Diff'])

    teams = {}
    all_teams = pd.concat([df['HomeTeam'], df['AwayTeam']]).unique()
    for team in all_teams:
        teams[team] = {'Punkte': 0, 'Tore': 0, 'Gegentore': 0, 'Spiele': 0}
        
    played = df[df['Finished'] == True]
    
    for _, row in played.iterrows():
        h = row['HomeTeam']
        a = row['AwayTeam']
        hg = row['HomeGoals']
        ag = row['AwayGoals']
        
        teams[h]['Spiele'] += 1; teams[a]['Spiele'] += 1
        teams[h]['Tore'] += hg; teams[a]['Tore'] += ag
        teams[h]['Gegentore'] += ag; teams[a]['Gegentore'] += hg
        
        if hg > ag: teams[h]['Punkte'] += 3
        elif ag > hg: teams[a]['Punkte'] += 3
        else: teams[h]['Punkte'] += 1; teams[a]['Punkte'] += 1
            
    table_df = pd.DataFrame.from_dict(teams, orient='index')
    if not table_df.empty:
        table_df['Diff'] = table_df['Tore'] - table_df['Gegentore']
        return table_df.sort_values(by=['Punkte', 'Diff', 'Tore'], ascending=False)
    return table_df

def fetch_scorers_external(api_key, competition_id):
    if not api_key: return pd.DataFrame()
    headers = { 'X-Auth-Token': api_key }
    url = f"{FD_BASE_URL}/{competition_id}/scorers?limit=25"
    data = make_api_request(url, headers)
    
    if not data: return pd.DataFrame()
    
    scorers_list = []
    for item in data.get('scorers', []):
        player = item.get('player', {})
        team = item.get('team', {})
        scorers_list.append({
            'Spieler': player.get('name'),
            'Team': team.get('name'),
            'Tore': item.get('goals'),
            'Assists': item.get('assists'),
            'Elfmeter': item.get('penalties')
        })
    return pd.DataFrame(scorers_list)