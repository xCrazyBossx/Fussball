import streamlit as st
import pandas as pd
import data 
import simulation 
import time
from datetime import datetime

st.set_page_config(page_title="Europa Fußball KI", layout="wide")

# --- SICHERHEITS-KONFIGURATION ---
try:
    # ACHTUNG: Auf dem Server in Streamlit Secrets eintragen!
    API_KEY = st.secrets["API_KEY"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    st.error("⚠️ **Sicherheits-Fehler:** Die App konnte die API-Schlüssel nicht finden.")
    st.info("Bitte trage `API_KEY` und `ADMIN_PASSWORD` in die Streamlit Cloud Secrets ein.")
    st.stop()

LEAGUES = {
    "Bundesliga": {"id": 2002, "logo": "🇩🇪", "color": "#FF0000"},
    "Premier League": {"id": 2021, "logo": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "color": "#38003c"},
    "La Liga": {"id": 2014, "logo": "🇪🇸", "color": "#ee8707"},
    "Serie A": {"id": 2019, "logo": "🇮🇹", "color": "#008fd7"},
    "Ligue 1": {"id": 2015, "logo": "🇫🇷", "color": "#dae025"},
    "Champions League": {"id": 2001, "logo": "🇪🇺", "color": "#0e1e5b"},
}

# --- STATE INITIALISIERUNG ---
# Wir nutzen den Session State nur für UI-Einstellungen, nicht für Daten
if 'selected_league' not in st.session_state:
    st.session_state.selected_league = "Dashboard"

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# --- HELPER (Team-Namen Übersetzer) ---
TEAM_TRANSLATION = {
    "Bayern Munich": "FC Bayern München", "Bayer Leverkusen": "Bayer 04 Leverkusen", "Borussia Dortmund": "Borussia Dortmund",
    "RB Leipzig": "RB Leipzig", "Union Berlin": "1. FC Union Berlin", "Freiburg": "SC Freiburg",
    "Eintracht Frankfurt": "Eintracht Frankfurt", "Wolfsburg": "VfL Wolfsburg", "Mainz": "1. FSV Mainz 05",
    "Augsburg": "FC Augsburg", "Stuttgart": "VfB Stuttgart", "Hoffenheim": "TSG 1899 Hoffenheim",
    "Werder Bremen": "SV Werder Bremen", "Bochum": "VfL Bochum 1848", "Heidenheim": "1. FC Heidenheim 1846",
    "Darmstadt": "SV Darmstadt 98", "Koln": "1. FC Köln", "Borussia Monchengladbach": "Borussia Mönchengladbach",
    "St. Pauli": "FC St. Pauli", "Holstein Kiel": "Holstein Kiel", "Real Madrid": "Real Madrid",
    "Barcelona": "FC Barcelona", "Atletico Madrid": "Atlético Madrid", "Paris Saint-Germain": "Paris SG",
    "Marseille": "Olympique Marseille", "Inter Milan": "Inter Mailand", "AC Milan": "AC Mailand",
    "Juventus": "Juventus Turin", "Napoli": "SSC Neapel", "Manchester City": "Man City",
    "Manchester United": "Man United", "Liverpool": "FC Liverpool", "Arsenal": "FC Arsenal",
    "Chelsea": "FC Chelsea", "Brest": "Stade Brest", "Benfica": "Benfica Lissabon", "Sporting CP": "Sporting Lissabon",
    "PSV Eindhoven": "PSV Eindhoven", "Feyenoord Rotterdam": "Feyenoord", "Red Bull Salzburg": "RB Salzburg",
    "Sturm Graz": "Sturm Graz", "Young Boys": "Young Boys Bern", "Bayer 04 Leverkusen": "Bayer 04 Leverkusen",
    "Aston Villa": "Aston Villa", "Bologna": "FC Bologna", "Girona": "FC Girona", "Lille OSC": "OSC Lille"
}

def translate_team(name): return TEAM_TRANSLATION.get(name, name)

# --- ZENTRALE LADE-FUNKTION (GLOBAL CACHED) ---
@st.cache_data(ttl=3600) # Speichert die Daten 1 Stunde lang GLOBAL
def fetch_and_simulate_league(league_name):
    """
    Lädt Matches & Torschützen UND führt die Simulation durch.
    Dieses Ergebnis ist global (für alle Nutzer) gültig.
    """
    config = LEAGUES[league_name]
    matches, logo_mapping = data.fetch_matches_external(API_KEY, config["id"])
    
    # Defaults
    result = {
        "table": pd.DataFrame(), "prognose": pd.DataFrame(), "kicktipp": pd.DataFrame(),
        "scorers": pd.DataFrame(), "bracket": pd.DataFrame(), "leader": "-", "leader_logo": "",
        "champ_pred": "-", "top_scorer": "-", "last_updated": datetime.now().strftime("%d.%m. %H:%M")
    }
    
    if matches.empty: return result

    table = data.calculate_current_table(matches)
    is_cl = (league_name == "Champions League")
    
    # Leader Info
    if not table.empty:
        leader_raw = table.index[0]
        result["leader"] = translate_team(leader_raw)
        result["leader_logo"] = logo_mapping.get(leader_raw, "")

    try:
        prognose_raw = simulation.simulate_season(matches, table, n_simulations=500, is_cl=is_cl)
        
        # CL Bracket
        if is_cl:
            cl_bracket = simulation.generate_cl_bracket(matches, table)
            if not cl_bracket.empty:
                cl_bracket['Heim'] = cl_bracket['Heim'].apply(translate_team)
                cl_bracket['Gast'] = cl_bracket['Gast'].apply(translate_team)
                cl_bracket['Sieger'] = cl_bracket['Sieger'].apply(translate_team)
                result["bracket"] = cl_bracket

        # Prognose aufräumen
        cols = ['Titel', 'Top8', 'Playoff', 'Out', 'Meister', 'CL', 'EL', 'ConfL', 'Abstieg', 'AvgPoints']
        for c in cols:
            if c not in prognose_raw.columns: prognose_raw[c] = 0.0
        
        prognose_raw['AvgPoints'] = prognose_raw['AvgPoints'].round(0).astype(int)
        prognose_raw['Team'] = prognose_raw.index
        prognose_raw = prognose_raw.reset_index(drop=True)
        prognose_raw.insert(0, 'Platz', range(1, 1 + len(prognose_raw)))
        prognose_raw['Wappen'] = prognose_raw['Team'].map(lambda x: logo_mapping.get(x, ""))
        prognose_raw['DisplayTeam'] = prognose_raw['Team'].apply(translate_team)
        
        keep_cols = ['Platz', 'Wappen', 'DisplayTeam', 'AvgPoints']
        keep_cols += ['Titel', 'Top8', 'Playoff', 'Out'] if is_cl else ['Meister', 'CL', 'EL', 'ConfL', 'Abstieg']
        
        result["prognose"] = prognose_raw[keep_cols]
        
        # Meister/Sieger für Dashboard
        if not prognose_raw.empty:
            sort_col = 'Titel' if is_cl else 'Meister'
            champ_row = prognose_raw.sort_values(sort_col, ascending=False).iloc[0]
            result["champ_pred"] = champ_row['DisplayTeam']

    except Exception as e:
        print(f"Fehler Simulation {league_name}: {e}")

    # Kicktipp
    next_n = 18 if is_cl else (9 if league_name in ["Bundesliga", "Ligue 1"] else 10)
    kicktipp = simulation.predict_upcoming_matches(matches, next_n=next_n)
    if not kicktipp.empty:
        kicktipp['Anstoß'] = kicktipp['Datum'].dt.strftime('%d.%m. %H:%M')
        kicktipp['HeimWappen'] = kicktipp['Heim'].map(lambda x: logo_mapping.get(x, ""))
        kicktipp['GastWappen'] = kicktipp['Auswärts'].map(lambda x: logo_mapping.get(x, ""))
        kicktipp['Heim'] = kicktipp['Heim'].apply(translate_team)
        kicktipp['Auswärts'] = kicktipp['Auswärts'].apply(translate_team)
        kicktipp = kicktipp[['Anstoß', 'HeimWappen', 'Heim', 'GastWappen', 'Auswärts', 'Tipp', '1', 'X', '2']]
        result["kicktipp"] = kicktipp

    # Tabelle Finalisieren
    table.insert(0, 'Platz', range(1, 1 + len(table)))
    table['OriginalName'] = table.index
    table['Wappen'] = table['OriginalName'].map(lambda x: logo_mapping.get(x, ""))
    table['DisplayTeam'] = table['OriginalName'].apply(translate_team)
    result["table"] = table

    # Scorers
    scorers = data.fetch_scorers_external(API_KEY, config["id"])
    if not scorers.empty:
        scorers['Wappen'] = scorers['Team'].map(lambda x: logo_mapping.get(x, ""))
        scorers['Team'] = scorers['Team'].apply(translate_team)
        if not table.empty:
            max_games = 8 if is_cl else (34 if league_name == "Bundesliga" else 38)
            played_avg = table['Spiele'].max() if not table.empty else 1
            if played_avg > 0:
                scorers['Prognose'] = (scorers['Tore'] * (max_games / played_avg)).round(0).astype(int)
            else:
                scorers['Prognose'] = scorers['Tore']
        
        scorers = scorers.sort_values(by=['Prognose', 'Tore'], ascending=False).head(15)
        scorers.insert(0, 'Platz', range(1, 1 + len(scorers)))
        result["scorers"] = scorers[['Platz', 'Wappen', 'Spieler', 'Team', 'Tore', 'Prognose']]
        
        top = scorers.iloc[0]
        result["top_scorer"] = f"{top['Spieler']} ({top['Tore']})"

    return result

# --- INFO HEADER (GLOBAL) ---
st.info("ℹ️ **Hinweis:** Die Daten werden täglich aktualisiert. Die Simulationsergebnisse basieren auf Monte-Carlo-Berechnungen (500x) und können leicht variieren.", icon="🎲")

# --- SIDEBAR ---
with st.sidebar:
    st.title("Navigation")
    
    if st.button("🏠 Startseite"):
        st.session_state.selected_league = "Dashboard"
        st.rerun()
    
    st.caption("Ligen:")
    for league in LEAGUES.keys():
        label = f"{LEAGUES[league]['logo']} {league}"
        
        # Zeigt den Lade-Zustand an
        if fetch_and_simulate_league.is_cached(league):
            label += " (✅)"
        
        if st.button(label):
            st.session_state.selected_league = league
            st.rerun()
            
    st.divider()
    
    # RECHTLICHES NAVI
    st.caption("Rechtliches:")
    if st.button("⚖️ Impressum"):
        st.session_state.selected_league = "Impressum"
        st.rerun()
    if st.button("🔒 Datenschutz"):
        st.session_state.selected_league = "Datenschutz"
        st.rerun()

    st.divider()
    
    with st.expander("🔧 Admin Login"):
        if not st.session_state.is_admin:
            pwd = st.text_input("Passwort:", type="password")
            if st.button("Login"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.is_admin = True
                    st.success("Eingeloggt!")
                    st.rerun()
                else:
                    st.error("Falsches Passwort")
        else:
            st.success("Admin-Modus aktiv")
            if st.button("Logout"):
                st.session_state.is_admin = False
                st.rerun()
            st.write("---")
            for league in LEAGUES.keys():
                if st.button(f"🔄 Update {league}"):
                    # LÖSCHT DEN GLOBALEN CACHE FÜR DIESE LIGA
                    fetch_and_simulate_league.clear_cache(league)
                    st.toast(f"{league} wird neu geladen!", icon="✅")
                    # Die Daten werden beim nächsten Rerun automatisch neu geholt
                    st.rerun() 
            if st.button("🔴 Cache komplett leeren"):
                fetch_and_simulate_league.clear()
                st.rerun()

# --- VIEW: DASHBOARD ---
def show_dashboard():
    st.title("🇪🇺 Europa Fußball Dashboard")
    
    cols = st.columns(3)
    for i, (league_name, config) in enumerate(LEAGUES.items()):
        col_idx = i % 3
        with cols[col_idx]:
            with st.container(border=True):
                c_head1, c_head2 = st.columns([4, 1])
                with c_head1: st.markdown(f"#### {config['logo']} {league_name}")
                if st.session_state.is_admin:
                    with c_head2:
                        if st.button("🔄", key=f"dash_rl_{league_name}", help="Admin: Neu laden"):
                            fetch_and_simulate_league.clear_cache(league_name)
                            st.rerun()

                # Daten holzen (Cache wird genutzt!)
                data = fetch_and_simulate_league(league_name)
                
                if data and data.get('leader') != "-":
                    st.caption(f"Stand: {data.get('last_updated', '-')}")
                    c1, c2 = st.columns([1, 3])
                    with c1: 
                        if data.get('leader_logo'): st.image(data['leader_logo'])
                    with c2: st.metric("Führer", data.get('leader', '-'))
                    
                    st.divider()
                    lbl = "🔮 Turnier-Sieger" if league_name == "Champions League" else "🔮 Meister-Tipp"
                    st.caption(lbl)
                    pred = data.get('champ_pred')
                    if pred == data.get('leader'): st.success(f"**{pred}**")
                    else: st.warning(f"**{pred}**")
                    
                    st.caption("👟 Top-Torjäger")
                    st.write(f"**{data.get('top_scorer')}**")
                    
                    if st.button(f"Zur Analyse ➜", key=f"btn_{league_name}"):
                        st.session_state.selected_league = league_name; st.rerun()
                else:
                    st.info("Lade Daten...")


# --- VIEW: DETAILS ---
def show_league_detail(league_name):
    if st.button("⬅️ Zurück zur Übersicht"):
        st.session_state.selected_league = "Dashboard"; st.rerun()
    
    st.title(f"{LEAGUES[league_name]['logo']} {league_name} KI-Analyse")
    
    # Daten holen
    data = fetch_and_simulate_league(league_name)
    
    if data['table'].empty and data['scorers'].empty:
        st.error("Keine Daten verfügbar (API Fehler oder Saisonpause)."); return
        
    if st.session_state.is_admin:
        if st.button("🔄 Admin: Daten aktualisieren"):
            fetch_and_simulate_league.clear_cache(league_name)
            st.rerun()

    tabs = ["🏆 Tabelle & Prognose", "🎲 Kicktipp-Helfer", "👟 Torschützen"]
    if league_name == "Champions League": tabs.append("🏆 K.O.-Baum")
    active_tabs = st.tabs(tabs)

    # TAB 1
    with active_tabs[0]:
        if not data['prognose'].empty:
            c1, c2 = st.columns([1.5, 1])
            with c1:
                st.subheader("Saison-Ende Prognose")
                is_cl = (league_name == "Champions League")
                subset = ['Titel', 'Top8', 'Playoff', 'Out'] if is_cl else ['Meister', 'CL', 'Abstieg']
                if 'EL' in data['prognose'].columns and not is_cl: subset.append('EL')
                
                styler = data['prognose'].style.format("{:.1f}%", subset=subset).format("{:.0f}", subset=['AvgPoints']) \
                    .background_gradient(cmap='Greens', subset=[subset[0]]) \
                    .background_gradient(cmap='Reds', subset=[subset[-1]])
                
                t_height = (len(data['prognose']) + 1) * 35 + 3
                st.dataframe(styler, hide_index=True, use_container_width=True, height=t_height,
                             column_config={"Wappen": st.column_config.ImageColumn("", width="small"), "DisplayTeam": "Verein", "AvgPoints": "Ø Pkt"})
            with c2:
                st.subheader("Aktuelle Live-Tabelle")
                t_height_real = (len(data['table']) + 1) * 35 + 3
                st.dataframe(data['table'][['Platz', 'Wappen', 'DisplayTeam', 'Spiele', 'Punkte', 'Tore']], 
                             hide_index=True, use_container_width=True, height=t_height_real,
                             column_config={"Wappen": st.column_config.ImageColumn("", width="small"), "DisplayTeam": "Verein"})
        else: st.info("Keine Prognose möglich.")

    with active_tabs[1]:
        st.subheader("Vorhersage kommende Spiele")
        if not data['kicktipp'].empty:
            def highlight_max(s):
                is_max = s == s.max(); return ['background-color: #d4edda; color: green' if v else '' for v in is_max]
            k_height = (len(data['kicktipp']) + 1) * 35 + 3
            st.dataframe(data['kicktipp'].style.format("{:.1f}%", subset=['1', 'X', '2']).apply(highlight_max, axis=1, subset=['1', 'X', '2']),
                         hide_index=True, use_container_width=False, height=k_height,
                         column_config={"HeimWappen": st.column_config.ImageColumn("", width="small"), "GastWappen": st.column_config.ImageColumn("", width="small")})
        else: st.info("Keine Spiele gefunden.")

    with active_tabs[2]:
        st.subheader("Torjäger")
        if not data['scorers'].empty:
            s_height = (len(data['scorers']) + 1) * 35 + 3
            st.dataframe(data['scorers'], hide_index=True, use_container_width=False, height=s_height,
                         column_config={"Wappen": st.column_config.ImageColumn("", width="small"), "Prognose": st.column_config.NumberColumn("Saison-Ziel", format="%d")})
        else: st.warning("Keine Daten.")

    if league_name == "Champions League":
        with active_tabs[3]:
            st.subheader("🏆 Simulierter K.O.-Baum")
            bracket = data.get('bracket')
            if bracket is not None and not bracket.empty:
                final_match = bracket[bracket['Runde'] == 'Finale']
                if not final_match.empty:
                    winner = final_match.iloc[0]['Sieger']
                    st.markdown(f"<div style='text-align: center; padding: 20px; background: #f0f2f6; border-radius: 10px; margin-bottom: 20px; color: #333;'><h3>🏆 Sieger: {winner}</h3></div>", unsafe_allow_html=True)

                rounds = ["Finale", "Halbfinale", "Viertelfinale", "Achtelfinale", "Playoffs"]
                for r in rounds:
                    rg = bracket[bracket['Runde'] == r]
                    if not rg.empty:
                        with st.expander(f"{r}", expanded=(r=="Finale" or r=="Halbfinale")):
                            for _, match in rg.iterrows():
                                c1, c2, c3, c4 = st.columns([3, 1, 1, 3])
                                with c1: 
                                    align = "right"; color = "green" if match['Sieger'] == match['Heim'] else "grey"
                                    font = "bold" if match['Sieger'] == match['Heim'] else "normal"
                                    st.markdown(f"<div style='text-align: {align}; font-weight: {font}; color: {color};'>{match['Heim']}</div>", unsafe_allow_html=True)
                                with c2: st.markdown(f"<div style='text-align: center; background-color: #f0f2f6; color: #333; border-radius: 5px; font-weight: bold;'>{match['Ergebnis']}</div>", unsafe_allow_html=True)
                                with c4:
                                    color = "green" if match['Sieger'] == match['Gast'] else "grey"
                                    font = "bold" if match['Sieger'] == match['Gast'] else "normal"
                                    st.markdown(f"<div style='font-weight: {font}; color: {color};'>{match['Gast']}</div>", unsafe_allow_html=True)
            else: st.warning("K.O.-Baum konnte noch nicht simuliert werden.")

# --- LEGAL PAGES ---
def show_legal_page(page_type):
    if st.button("⬅️ Zurück zur Startseite"):
        st.session_state.selected_league = "Dashboard"
        st.rerun()
        
    if page_type == "Impressum":
        st.title("⚖️ Impressum")
        st.markdown("""
        **Angaben gemäß § 5 TMG**

        Ihr Name  
        Ihre Adresse  
        Ihre Postleitzahl und Ort  

        **Kontakt:** E-Mail: Ihre@email.de  
        
        **Verantwortlich für den Inhalt nach § 55 Abs. 2 RStV:** Ihr Name  
        Ihre Adresse  
        Ihre Postleitzahl und Ort  
        """)
    
    elif page_type == "Datenschutz":
        st.title("🔒 Datenschutzerklärung & Disclaimer")
        st.markdown("""
        **1. Datenschutz**
        Diese Webseite nutzt die Dienste von Streamlit Community Cloud. Wir selbst speichern keine personenbezogenen Daten von Ihnen.
        
        Beim Aufruf der Webseite werden durch den Hosting-Anbieter (Streamlit Inc.) technisch notwendige Daten (Logfiles) erfasst.
        
        **2. Externe Dienste (APIs)**
        Diese App lädt Fußball-Daten von der externen Schnittstelle `football-data.org`. Dabei wird Ihre IP-Adresse technisch bedingt an den API-Provider übermittelt, um die Daten abzurufen.
        
        **3. Haftungsausschluss (Disclaimer)**
        Die auf dieser Webseite dargestellten Vorhersagen und Prognosen werden durch einen statistischen Algorithmus (Künstliche Intelligenz / Monte-Carlo-Simulation) generiert.
        
        * **Keine Wett-Beratung:** Diese Daten dienen ausschließlich der Unterhaltung und Information. Sie stellen keine Aufforderung zum Glücksspiel oder Finanzberatung dar.
        * **Keine Gewähr:** Wir übernehmen keine Haftung für die Richtigkeit, Vollständigkeit oder Aktualität der dargestellten Ergebnisse.
        """)

# --- ROUTER ---
if st.session_state.selected_league == "Dashboard":
    show_dashboard()
elif st.session_state.selected_league == "Impressum":
    show_legal_page("Impressum")
elif st.session_state.selected_league == "Datenschutz":
    show_legal_page("Datenschutz")
else:
    show_league_detail(st.session_state.selected_league)
