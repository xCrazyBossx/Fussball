import numpy as np
import pandas as pd
import math

def calculate_smart_strengths(df_matches):
    played = df_matches[df_matches['Finished'] == True].copy()
    if played.empty: return {}, 3.0 
    
    played['CalcHomeGoals'] = played['HomeGoals']
    played['CalcAwayGoals'] = played['AwayGoals']
    played = played.sort_values(by='Date')
    total_games = len(played)
    played['Weight'] = 1.0
    if total_games > 5:
        played.iloc[-int(total_games*0.3):, played.columns.get_loc('Weight')] = 2.0
    
    weighted_goals = (played['CalcHomeGoals'] * played['Weight']).sum() + (played['CalcAwayGoals'] * played['Weight']).sum()
    weighted_count = played['Weight'].sum() * 2 
    avg_goals = weighted_goals / weighted_count if weighted_count > 0 else 3.0
    
    stats = {}
    # Filtert None/Empty Teams raus
    all_teams = pd.concat([played['HomeTeam'], played['AwayTeam']])
    teams = all_teams[all_teams.notna() & (all_teams != "")].unique()
    
    for team in teams:
        home = played[played['HomeTeam'] == team]
        away = played[played['AwayTeam'] == team]
        scored = (home['CalcHomeGoals'] * home['Weight']).sum() + (away['CalcAwayGoals'] * away['Weight']).sum()
        conceded = (home['CalcAwayGoals'] * home['Weight']).sum() + (away['CalcHomeGoals'] * away['Weight']).sum()
        weighted_games = home['Weight'].sum() + away['Weight'].sum()
        
        if weighted_games > 0:
            att = (scored / weighted_games) / avg_goals
            defn = (conceded / weighted_games) / avg_goals
        else:
            att, defn = 1.0, 1.0
        stats[team] = {'attack': att, 'defense': defn}
    return stats, avg_goals

def simulate_match_poisson(team1, team2, stats, avg_goals, home_advantage=1.2, performance_boost=None):
    """
    Simuliert ein Spiel mit Performance-Boosts aus der Ligaphase.
    """
    t1_s = stats.get(team1, {'attack': 1, 'defense': 1})
    t2_s = stats.get(team2, {'attack': 1, 'defense': 1})
    
    # Boost anwenden (falls vorhanden)
    boost1 = performance_boost.get(team1, 1.0) if performance_boost else 1.0
    boost2 = performance_boost.get(team2, 1.0) if performance_boost else 1.0
    
    # Lambda berechnen (Stärke * Boost * Heimvorteil)
    lam1 = t1_s['attack'] * t2_s['defense'] * avg_goals * home_advantage * boost1
    lam2 = t2_s['attack'] * t1_s['defense'] * avg_goals * boost2 # Gast hat keinen Heimvorteil
    
    return np.random.poisson(lam1), np.random.poisson(lam2)

def generate_cl_bracket(matches, current_table):
    """
    Simuliert EINEN kompletten Turnierbaum für die Anzeige im UI.
    Nutzt Form-Boosts basierend auf der Ligatabelle.
    """
    stats, avg_goals = calculate_smart_strengths(matches)
    
    # 1. Ligaphase zu Ende simulieren (einmalig für dieses Szenario)
    future = matches[matches['Finished'] == False]
    sim_table = current_table.copy()
    
    # Tabelle bereinigen
    sim_table = sim_table[sim_table.index.notna() & (sim_table.index != "")]
    
    for _, match in future.iterrows():
        h, a = match['HomeTeam'], match['AwayTeam']
        if not h or not a: continue
        g1, g2 = simulate_match_poisson(h, a, stats, avg_goals)
        if g1 > g2: sim_table.loc[h, 'Punkte'] += 3
        elif g2 > g1: sim_table.loc[a, 'Punkte'] += 3
        else: 
            sim_table.loc[h, 'Punkte'] += 1; sim_table.loc[a, 'Punkte'] += 1
            
    # Ranking finalisieren
    sim_table = sim_table.sort_values(by=['Punkte', 'Diff', 'Tore'], ascending=False)
    ranking = sim_table.index.tolist()
    
    # --- PERFORMANCE BOOST BERECHNEN ---
    # Wer viele Punkte/Tore geholt hat, geht gestärkt in die K.O. Runde
    performance_boost = {}
    max_points = sim_table['Punkte'].max() if not sim_table.empty else 1
    
    for team in ranking:
        points = sim_table.loc[team, 'Punkte']
        # Faktor: 1.0 (Basis) + bis zu 0.2 Bonus für Punkte
        boost = 1.0 + (points / max_points) * 0.2
        performance_boost[team] = boost

    # --- K.O. PHASE SIMULIEREN ---
    scenario = [] # Liste der Matches für UI
    
    # A) Playoffs (9-24)
    playoff_winners = []
    seeded = ranking[8:16]
    unseeded = ranking[16:24]
    
    # Wir nehmen an: Seeded spielt Rückspiel Heim
    for i in range(len(seeded)):
        t1 = unseeded[i]
        t2 = seeded[i]
        
        # Hinspiel
        h1, a1 = simulate_match_poisson(t1, t2, stats, avg_goals, home_advantage=1.2, performance_boost=performance_boost)
        # Rückspiel
        h2, a2 = simulate_match_poisson(t2, t1, stats, avg_goals, home_advantage=1.2, performance_boost=performance_boost)
        
        agg1 = h1 + a2
        agg2 = a1 + h2
        winner = t1 if agg1 > agg2 else t2
        if agg1 == agg2: winner = np.random.choice([t1, t2]) # Elfer
        
        playoff_winners.append(winner)
        scenario.append({
            "Runde": "Playoffs", 
            "Heim": t2, "Gast": t1, 
            "Ergebnis": f"{h2}:{a2} ({a1}:{h1})", 
            "Sieger": winner
        })
        
    # B) Achtelfinale
    top8 = ranking[0:8]
    r16_winners = []
    # Top 8 gesetzt vs Playoff Winner
    np.random.shuffle(playoff_winners)
    
    for i in range(8):
        t1 = playoff_winners[i]
        t2 = top8[i]
        
        h1, a1 = simulate_match_poisson(t1, t2, stats, avg_goals, 1.2, performance_boost)
        h2, a2 = simulate_match_poisson(t2, t1, stats, avg_goals, 1.2, performance_boost)
        
        agg1 = h1 + a2
        agg2 = a1 + h2
        winner = t1 if agg1 > agg2 else t2
        if agg1 == agg2: winner = np.random.choice([t1, t2])
        
        r16_winners.append(winner)
        scenario.append({"Runde": "Achtelfinale", "Heim": t2, "Gast": t1, "Ergebnis": f"{h2}:{a2} ({a1}:{h1})", "Sieger": winner})

    # C) Viertelfinale bis Finale (Standard KO)
    current_round_teams = r16_winners
    rounds = ["Viertelfinale", "Halbfinale", "Finale"]
    
    for r_name in rounds:
        next_round_teams = []
        np.random.shuffle(current_round_teams)
        
        for i in range(0, len(current_round_teams), 2):
            if i+1 >= len(current_round_teams): break
            t1 = current_round_teams[i]
            t2 = current_round_teams[i+1]
            
            is_final = (r_name == "Finale")
            home_adv = 1.0 if is_final else 1.2 # Kein Heimvorteil im Finale
            
            if is_final:
                h, a = simulate_match_poisson(t1, t2, stats, avg_goals, home_adv, performance_boost)
                winner = t1 if h > a else t2
                if h == a: winner = np.random.choice([t1, t2])
                res_str = f"{h}:{a}"
            else:
                h1, a1 = simulate_match_poisson(t1, t2, stats, avg_goals, home_adv, performance_boost)
                h2, a2 = simulate_match_poisson(t2, t1, stats, avg_goals, home_adv, performance_boost)
                agg1 = h1 + a2
                agg2 = a1 + h2
                winner = t1 if agg1 > agg2 else t2
                if agg1 == agg2: winner = np.random.choice([t1, t2])
                res_str = f"{h1}:{a1} / {h2}:{a2}"
                
            next_round_teams.append(winner)
            scenario.append({"Runde": r_name, "Heim": t1, "Gast": t2, "Ergebnis": res_str, "Sieger": winner})
            
        current_round_teams = next_round_teams

    return pd.DataFrame(scenario)

def simulate_season(df_matches, current_table, n_simulations=500, is_cl=False):
    # Basis-Simulation für Wahrscheinlichkeiten (bleibt wie gehabt)
    if not current_table.empty:
        current_table = current_table[current_table.index.notna() & (current_table.index != "")]

    stats, avg_goals = calculate_smart_strengths(df_matches)
    future = df_matches[df_matches['Finished'] == False]
    
    if is_cl:
        results = {team: {'Titel': 0, 'Top8': 0, 'Playoff': 0, 'Out': 0, 'TotalPoints': 0} for team in current_table.index}
    else:
        results = {team: {'Meister': 0, 'CL': 0, 'EL': 0, 'ConfL': 0, 'Abstieg': 0, 'TotalPoints': 0} for team in current_table.index}
    
    for _ in range(n_simulations):
        sim_table = current_table.copy()
        current_sim_stats = {}
        for team, values in stats.items():
            form_factor = np.random.normal(1.0, 0.10)
            current_sim_stats[team] = {'attack': values['attack']*form_factor, 'defense': values['defense']*(2-form_factor)}
        
        for _, match in future.iterrows():
            h, a = match['HomeTeam'], match['AwayTeam']
            if not h or not a: continue
            h_s = current_sim_stats.get(h, {'attack': 1, 'defense': 1})
            a_s = current_sim_stats.get(a, {'attack': 1, 'defense': 1})
            hg = np.random.poisson(h_s['attack'] * a_s['defense'] * avg_goals * 1.2)
            ag = np.random.poisson(a_s['attack'] * h_s['defense'] * avg_goals)
            if hg > ag: sim_table.loc[h, 'Punkte'] += 3
            elif ag > hg: sim_table.loc[a, 'Punkte'] += 3
            else: sim_table.loc[h, 'Punkte'] += 1; sim_table.loc[a, 'Punkte'] += 1
        
        for team in sim_table.index: results[team]['TotalPoints'] += sim_table.loc[team, 'Punkte']
        ranking = sim_table.sort_values(by=['Punkte', 'Diff', 'Tore'], ascending=False).index.tolist()
        
        if is_cl:
            # Einfache Zählung für Statistik
            for t in ranking[0:8]: results[t]['Top8'] += 1
            for t in ranking[8:24]: results[t]['Playoff'] += 1
            # Titelchance simulieren wir hier vereinfacht über Tabellenplatz 1 als Proxy für Favoriten
            # Echte KO Simulation ist zu teuer für 500 Runs, dafür haben wir generate_cl_bracket
            results[ranking[0]]['Titel'] += 1 
        else:
            if ranking: results[ranking[0]]['Meister'] += 1
            for t in ranking[0:4]: results[t]['CL'] += 1
            if len(ranking) >= 18:
                for t in ranking[-3:]: results[t]['Abstieg'] += 1

    df_res = pd.DataFrame.from_dict(results, orient='index')
    df_res['AvgPoints'] = df_res['TotalPoints'] / n_simulations
    for col in df_res.columns:
        if col != 'AvgPoints': df_res[col] = (df_res[col] / n_simulations) * 100
        
    return df_res.sort_values(by='AvgPoints', ascending=False)

def predict_upcoming_matches(df_matches, next_n=9):
    # (Bleibt unverändert wie zuvor)
    stats, avg_goals = calculate_smart_strengths(df_matches)
    if 'Date' in df_matches.columns:
        future = df_matches[df_matches['Finished'] == False].dropna(subset=['HomeTeam', 'AwayTeam']).sort_values(by='Date').head(next_n)
    else: return pd.DataFrame()
    
    predictions = []
    def poisson_prob(k, lam): return (lam**k * np.exp(-lam)) / math.factorial(k)

    for _, match in future.iterrows():
        h, a = match['HomeTeam'], match['AwayTeam']
        h_s = stats.get(h, {'attack': 1, 'defense': 1})
        a_s = stats.get(a, {'attack': 1, 'defense': 1})
        lam_h = h_s['attack'] * a_s['defense'] * avg_goals * 1.2
        lam_a = a_s['attack'] * h_s['defense'] * avg_goals
        
        probs = np.zeros((10, 10))
        for i in range(10):
            for j in range(10):
                probs[i][j] = poisson_prob(i, lam_h) * poisson_prob(j, lam_a)
        
        p1 = np.sum(np.tril(probs, -1))
        px = np.trace(probs)
        p2 = np.sum(np.triu(probs, 1))
        
        idx = np.unravel_index(np.argmax(probs), probs.shape)
        predictions.append({'Datum': match['Date'], 'Heim': h, 'Auswärts': a, 'Tipp': f"{idx[0]}:{idx[1]}", '1': p1*100, 'X': px*100, '2': p2*100})
    return pd.DataFrame(predictions)