import streamlit as st
import pandas as pd
from google import genai

# --- Konfiguration & Design ---
st.set_page_config(page_title="Finanz-Allokator & KI-Advisor", page_icon="💰", layout="centered")

# --- Authentifizierung (Passwort-Schutz) ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

master_pwd = st.secrets.get("APP_PASSWORD", "admin")

if not st.session_state.authenticated:
    st.title("🔒 Anmelden")
    pwd_input = st.text_input("Master-Passwort", type="password")
    if st.button("Einloggen", use_container_width=True):
        if pwd_input == master_pwd:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Ungültiges Passwort.")
    st.stop()

# --- Hauptbereich der Anwendung ---
st.title("📊 Mein Finanz- & Vermögens-Allokator")

# --- Seitenleiste: Parameter & Strategie ---
with st.sidebar:
    st.header("⚙️ Strategie-Einstellungen")
    giro_puffer = st.number_input("Girokonto-Sicherheitspuffer (€)", value=2200, step=100)
    notgroschen_ziel = st.number_input("Notgroschen Zielbetrag (€)", value=6000, step=500)
    notgroschen_ist = st.number_input("Notgroschen Aktueller Stand (€)", value=5000, step=500)
    
    st.divider()
    st.subheader("Überschuss-Aufteilung")
    etf_quote = st.slider("Aktien-ETFs Quote (%)", min_value=0, max_value=100, value=75, step=5)
    zins_quote = 100 - etf_quote
    st.caption(f"Verbleibender Zinsbaustein (Tages-/Festgeld): **{zins_quote}%**")
    
    if st.button("Abmelden"):
        st.session_state.authenticated = False
        st.rerun()

# --- Daten-Upload oder manuelle Cashflow-Eingabe ---
tab_manual, tab_csv = st.tabs(["📝 Monatszahlen (Schnelleingabe)", "📂 CSV-Kontoauszug Upload"])

with tab_manual:
    col_in, col_out = st.columns(2)
    with col_in:
        einnahmen = st.number_input("Einnahmen diesen Monat (€)", value=3450.0, step=50.0)
    with col_out:
        ausgaben = st.number_input("Ausgaben / Fixkosten (€)", value=2150.0, step=50.0)

with tab_csv:
    uploaded_files = st.file_uploader(
        "Kontoauszüge (CSV von DKB, Hausbank, Trade Republic)", 
        accept_multiple_files=True, 
        type=["csv"]
    )
    if uploaded_files:
        st.info("CSV-Daten werden automatisch zusammengeführt.")

# --- Berechnung der Allokation (Wasserfall-Prinzip) ---
monats_ueberschuss = max(0.0, einnahmen - ausgaben)
bedarf_notgroschen = max(0.0, float(notgroschen_ziel - notgroschen_ist))

# 1. Stufe: Notgroschen auffüllen
zufuehrung_notgroschen = min(monats_ueberschuss, bedarf_notgroschen)
rest_kapital = monats_ueberschuss - zufuehrung_notgroschen

# 2. Stufe: Zuteilung nach Quote
etf_betrag = rest_kapital * (etf_quote / 100.0)
zins_betrag = rest_kapital * (zins_quote / 100.0)

# --- Darstellung der Kennzahlen ---
st.divider()
st.subheader("💡 Deine Zuteilung für diesen Monat")

m1, m2, m3 = st.columns(3)
m1.metric("Freier Monatsüberschuss", f"{monats_ueberschuss:,.2f} €")
m2.metric("Giro-Puffer reserviert", f"{giro_puffer:,.2f} €")
m3.metric("Notgroschen-Bedarf", f"{bedarf_notgroschen:,.2f} €")

# Konkrete Handlungsanweisungen
st.markdown("### 🎯 Auszuführende Überweisungen & Käufe:")
c_not, c_etf, c_zins = st.columns(3)
c_not.success(f"🛡️ **Notgroschen:**\n\n**+{zufuehrung_notgroschen:,.2f} €**")
c_etf.info(f"📈 **Welt-ETF Sparplan:**\n\n**+{etf_betrag:,.2f} €**")
c_zins.warning(f"🏦 **Zinsbaustein:**\n\n**+{zins_betrag:,.2f} €**")

# Visuelle Aufteilung als Balken
chart_data = pd.DataFrame({
    "Baustein": ["Notgroschen", "ETFs", "Zinsbaustein"],
    "Betrag (€)": [zufuehrung_notgroschen, etf_betrag, zins_betrag]
}).set_index("Baustein")
st.bar_chart(chart_data)

# --- Gemini KI Strategieberater ---
st.divider()
st.subheader("🤖 Gemini KI-Vermögensberater & Sparring")

gemini_key = st.secrets.get("GEMINI_API_KEY", "")

if not gemini_key or gemini_key == "HIER_KEY_EINFUEGEN":
    st.warning("Trage deinen GEMINI_API_KEY in die Datei secrets.toml ein, um die KI-Analyse zu aktivieren.")
else:
    # Aggregierte Daten für den Prompt (strikt anonymisiert)
    daten_kontext = f"""
    Hier sind die aktuellen aggregierten Monatsfinanzdaten des Nutzers:
    - Einnahmen: {einnahmen:,.2f} €
    - Ausgaben: {ausgaben:,.2f} €
    - Netto-Cashflow-Überschuss: {monats_ueberschuss:,.2f} €
    - Girokonto-Sicherheitspuffer: {giro_puffer:,.2f} €
    - Notgroschen Ziel: {notgroschen_ziel:,.2f} € (Aktuell: {notgroschen_ist:,.2f} €, Zufuhr: {zufuehrung_notgroschen:,.2f} €)
    - Freies Anlagekapital: {rest_kapital:,.2f} €
    - Gewählte Strategie-Quote: {etf_quote}% Aktien-ETFs ({etf_betrag:,.2f} €), {zins_quote}% Zinsen ({zins_betrag:,.2f} €)
    """

    col_btn, _ = st.columns([1, 1])
    with col_btn:
        starte_analyse = st.button("🧠 Monats-Check durchführen", use_container_width=True)

    if starte_analyse:
        with st.spinner("Gemini analysiert deinen Cashflow und deine Allokation..."):
            try:
                client = genai.Client(api_key=gemini_key)
                system_instruction = (
                    "Du bist ein analytischer, pragmatischer und unabhängiger Vermögensberater nach dem "
                    "Gerd-Kommer- und Bogleheads-Prinzip. Bewerte die Finanzlage kurz, prägnant und auf den Punkt. "
                    "Gib 3 klare Abschnitte aus: 1. Feedback zum Cashflow & Sparquote, 2. Bewertung der aktuellen "
                    "Asset-Allokation, 3. Konkrete Optimierungsvorschläge oder Denkanstöße für die Zukunft. "
                    "Antworte direkt auf Deutsch, formatiere übersichtlich mit Aufzählungspunkten."
                )
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[system_instruction, daten_kontext]
                )
                st.session_state["letzte_ki_analyse"] = response.text
            except Exception as e:
                st.error(f"Fehler bei der Kommunikation mit Gemini: {e}")

    if "letzte_ki_analyse" in st.session_state:
        st.markdown(st.session_state["letzte_ki_analyse"])

    # Interaktiver Chat für Strategieanpassungen
    st.markdown("#### 💬 Strategie anpassen oder Fragen stellen")
    user_frage = st.chat_input("z. B.: Ich will in 2 Jahren ein Auto für 12.000 € kaufen. Wie passe ich die Quote an?")
    
    if user_frage:
        with st.chat_message("user"):
            st.write(user_frage)
        with st.chat_message("assistant"):
            with st.spinner("Gemini überlegt..."):
                try:
                    client = genai.Client(api_key=gemini_key)
                    prompt = f"{daten_kontext}\n\nNutzerfrage zur Strategie:\n{user_frage}"
                    chat_response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    st.markdown(chat_response.text)
                except Exception as e:
                    st.error(f"Fehler: {e}")