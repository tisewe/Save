import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime
from docx import Document
from google import genai
from google.genai import types

st.set_page_config(page_title="Finanz-Cockpit & KI-Stratege", page_icon="🧭", layout="wide")

# --- Authentifizierung ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

master_pwd = st.secrets.get("APP_PASSWORD", "admin")
gemini_key = st.secrets.get("GEMINI_API_KEY", "")

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

# --- Seitenleiste: Deine Baseline-Regler ---
with st.sidebar:
    st.header("⚙️ Deine Baseline-Regler")
    st.caption("Dient als persönliche Referenzgröße (Weg 1). Die KI (Weg 2) bewertet unabhängig davon.")
    giro_puffer_ziel = st.number_input("Wunsch-Puffer Girokonto (€)", value=2000, step=100)
    notgroschen_ziel = st.number_input("Notgroschen Ziel (€)", value=6000, step=500)
    fester_basis_sparplan = st.number_input("Fester Basis-Sparplan ETF (€/Monat)", value=150, step=25, 
                                            help="Dieser Sparplan läuft bei Trade Republic dauerhaft durch.")
    
    st.divider()
    st.subheader("Wunsch-Aufteilung freies Kapital")
    etf_quote = st.slider("Aktien-ETFs Quote (%)", min_value=0, max_value=100, value=75, step=5)
    zins_quote = 100 - etf_quote
    st.caption(f"Verbleibender Zinsbaustein: **{zins_quote}%**")
    
    st.divider()
    if st.button("Abmelden"):
        st.session_state.authenticated = False
        st.rerun()

st.title("🧭 Dein Autonomes All-Time Finanz-Cockpit")
st.write("Lade Dokumente hoch (All-Time-Historie möglich). Untersuche gezielt einzelne Monate, überwache Klumpenrisiken und kopiere deinen fertigen Aktionsplan.")

# --- Dokumenten-Upload ---
uploaded_files = st.file_uploader(
    "Dokumente ablegen (VR-Bank CSV/PDF, Trade Republic PDF, Krypto-Exchanges, Gehaltszettel, Verträge)", 
    type=["pdf", "csv", "docx"], 
    accept_multiple_files=True
)

def docx_to_text(file_bytes):
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in doc.paragraphs if p.text])

# --- Verarbeitungs-Engine ---
if uploaded_files:
    if st.button("🚀 Historie scannen & Cockpit berechnen", type="primary", use_container_width=True):
        if not gemini_key:
            st.error("Kein GEMINI_API_KEY in Secrets hinterlegt.")
            st.stop()
            
        with st.spinner("Gemini analysiert Historie, ordnet Fälligkeiten zu, prüft Risiken & berechnet Allokation..."):
            try:
                client = genai.Client(api_key=gemini_key)
                contents = []

                for f in uploaded_files:
                    file_bytes = f.read()
                    name = f.name.lower()
                    if name.endswith(".pdf"):
                        contents.append(types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"))
                    elif name.endswith(".csv"):
                        contents.append(f"--- DATEI: {f.name} (CSV) ---\n" + file_bytes.decode("utf-8", errors="ignore"))
                    elif name.endswith(".docx"):
                        text_content = docx_to_text(file_bytes)
                        contents.append(f"--- DATEI: {f.name} (Word) ---\n" + text_content)

                heute = datetime.now().strftime("%Y-%m-%d")
                system_prompt = f"""
                Du bist ein forensischer Finanzanalyst und unabhängiger Chef-Anlagestratege nach Gerd Kommer.
                Heutiges Referenzdatum: {heute}.

                AUFGABEN:
                1. JAHRES- & INTERVALL-KARTIERUNG (Historie):
                   - Identifiziere alle periodischen Kosten (monatlich, vierteljährlich, halbjährlich, jährlich).
                   - Ordne jedem Intervallposten zu, in welchen Kalendermonaten er fällig wird (faellige_monate als Array 1..12).
                   - Extrahiere die regulären monatlichen Fixkosten (die jeden Monat anfallen).

                2. GEGENWARTS-ANALYSE (Jüngster Monat / Stichtag):
                   - Nettoeinkommen des jüngsten Monats.
                   - Gesamtausgaben des jüngsten Monats.
                   - Letzter Stichtags-Saldo: Girokonto, Notgroschen/Tagesgeld, Depotwerte (ETFs, Einzelaktien, Krypto).

                3. STRATEGIE & EMPFEHLUNG (Weg 2):
                   - Berechne situative Euro-Verteilung.
                   - Berücksichtige die Sparplan-Glättung: Trenne das ETF-Investment in Dauer-Sparplan und flexible Einmal-Order.
                   - Analysiere das Klumpenrisiko (Krypto, Tech-Aktien).

                4. TURNAROUND-ANALYSE:
                   - Prüfe auf Cashflow-Engpässe oder Zielverfehlungen und gib konkrete Einsparhebel aus den Belegen an.

                Antworte AUSSCHLIESSLICH als valides JSON:
                {{
                    "analysierter_zeitraum": string,
                    "aktueller_monatsbezug": string,
                    "monatseinkommen_aktuell": float,
                    "ausgaben_aktuell": float,
                    "regulaere_monatliche_fixkosten": float,
                    "saldo_giro": float,
                    "saldo_notgroschen": float,
                    "portfolio": {{
                        "etfs": float,
                        "einzelaktien": float,
                        "krypto": float
                    }},
                    "alle_erkannten_intervalle": [
                        {{
                            "posten": string,
                            "betrag": float,
                            "turnus": string,
                            "faellige_monate": [int],
                            "letzte_buchung": string,
                            "begruendung": string
                        }}
                    ],
                    "ki_zweitmeinung": {{
                        "verteilung": {{
                            "notgroschen": float,
                            "etf_einmalkauf": float,
                            "einzelaktien": float,
                            "krypto": float,
                            "zinsbaustein": float
                        }},
                        "kommentar": string,
                        "krypto_aktien_fazit": string
                    }},
                    "turnaround_analyse": {{
                        "engpass_erkannt": bool,
                        "ursachen": string,
                        "konkrete_einsparhebel": [
                            {{"bereich": string, "sparpotenzial": float, "massnahme": string}}
                        ],
                        "fahrplan_kommender_monat": string
                    }}
                }}
                Alle Beträge als positive Zahlen. Kein Markdown, nur valides JSON.
                """
                
                contents.insert(0, system_prompt)
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                st.session_state["analyse_ergebnis"] = json.loads(response.text)

            except Exception as e:
                st.error(f"Fehler bei der Analyse: {e}")

# --- Dashboard-Darstellung ---
if "analyse_ergebnis" in st.session_state:
    data = st.session_state["analyse_ergebnis"]
    
    zeitraum = data.get("analysierter_zeitraum", "Historie")
    monatsbezug = data.get("aktueller_monatsbezug", "Aktueller Monat")
    
    einkommen = float(data.get("monatseinkommen_aktuell", 0.0))
    ausgaben_aktuell = float(data.get("ausgaben_aktuell", 0.0))
    regulaere_fixkosten = float(data.get("regulaere_monatliche_fixkosten", 0.0))
    saldo_giro = float(data.get("saldo_giro", 0.0))
    notgroschen_ist = float(data.get("saldo_notgroschen", 0.0))
    
    portfolio = data.get("portfolio", {})
    wert_etf = float(portfolio.get("etfs", 0.0))
    wert_aktien = float(portfolio.get("einzelaktien", 0.0))
    wert_krypto = float(portfolio.get("krypto", 0.0))
    
    gesamtvermoegen = saldo_giro + notgroschen_ist + wert_etf + wert_aktien + wert_krypto
    alle_intervalle = data.get("alle_erkannten_intervalle", [])

    st.info(f"📅 **Historischer Scan:** {zeitraum} | **Aktiver Beleg-Monat:** {monatsbezug}")

    # --- 1. Portfolio-Status & Rebalancing-Radar ---
    st.markdown("### 📊 Vermögensstatus & Rebalancing-Radar")
    v1, v2, v3, v4, v5 = st.columns(5)
    v1.metric("Girokonto", f"{saldo_giro:,.2f} €")
    v2.metric("Notgroschen / Cash", f"{notgroschen_ist:,.2f} €")
    v3.metric("ETFs", f"{wert_etf:,.2f} €")
    v4.metric("Einzelaktien", f"{wert_aktien:,.2f} €")
    v5.metric("Kryptowährungen", f"{wert_krypto:,.2f} €")

    # Quoten berechnen
    if gesamtvermoegen > 0:
        quote_krypto = (wert_krypto / gesamtvermoegen) * 100
        quote_aktien = (wert_aktien / gesamtvermoegen) * 100
        quote_etf = (wert_etf / gesamtvermoegen) * 100
        quote_cash = ((saldo_giro + notgroschen_ist) / gesamtvermoegen) * 100

        r1, r2, r3, r4 = st.columns(4)
        r1.caption(f"Liquiditäts-Quote: **{quote_cash:.1f}%**")
        r2.caption(f"ETF-Quote: **{quote_etf:.1f}%**")
        r3.caption(f"Einzelaktien-Quote: **{quote_aktien:.1f}%**")
        r4.caption(f"Krypto-Quote: **{quote_krypto:.1f}%**")

        # Klumpenrisiko-Ampel
        if quote_krypto > 15.0:
            st.warning(f"⚠️ **Rebalancing-Alarm (Krypto):** Krypto macht **{quote_krypto:.1f}%** deines Gesamtvermögens aus (Richtwert: max. 5–10%). Diesen Monat keine Zukäufe bei Krypto empfohlen!")
        elif quote_aktien > 25.0:
            st.warning(f"⚠️ **Klumpenrisiko Einzelaktien:** Einzelaktien machen **{quote_aktien:.1f}%** aus. Vorzugsweise breit gestreute ETFs aufstocken.")
        else:
            st.success("🟢 **Portfolio-Balance gesund:** Keine kritischen Klumpenrisiken bei Krypto oder Einzelaktien erkannt.")

    st.divider()

    # --- 2. Interaktiver Monats-Planer ---
    st.markdown("### 🗓️ Interaktiver Monats-Planer & Vorschau")
    
    monatsnamen = [
        "Januar", "Februar", "März", "April", "Mai", "Juni", 
        "Juli", "August", "September", "Oktober", "November", "Dezember"
    ]
    
    jetzt = datetime.now()
    naechster_monat_num = (jetzt.month % 12) + 1
    default_index = naechster_monat_num - 1

    dropdown_options = [
        f"{m} (👉 Folgemonat - Vorauswahl)" if i == default_index else m 
        for i, m in enumerate(monatsnamen)
    ]

    selected_option = st.selectbox(
        "Monat für die Detail-Vorschau:",
        options=dropdown_options,
        index=default_index
    )
    
    gewaehlter_monat_idx = dropdown_options.index(selected_option) + 1
    gewaehlter_monat_name = monatsnamen[gewaehlter_monat_idx - 1]

    # Fälligkeiten für gewählten Monat
    faellig_in_auswahl = [
        item for item in alle_intervalle 
        if gewaehlter_monat_idx in item.get("faellige_monate", [])
        and item.get("turnus", "").lower() != "monatlich"
    ]
    sonderkosten_summe = sum(float(x.get("betrag", 0.0)) for x in faellig_in_auswahl)

    if faellig_in_auswahl:
        st.warning(f"🔔 **Im {gewaehlter_monat_name} anstehende Sonder-Fälligkeiten: {sonderkosten_summe:,.2f} €**")
        warn_cols = st.columns(min(len(faellig_in_auswahl), 4))
        for idx, item in enumerate(faellig_in_auswahl):
            warn_cols[idx % 4].info(
                f"**{item.get('posten')}**\n\n"
                f"**{float(item.get('betrag', 0.0)):,.2f} €** ({item.get('turnus')})\n\n"
                f"*Zuletzt: {item.get('letzte_buchung', 'k.A.')}*"
            )
    else:
        st.success(f"✅ Für den **{gewaehlter_monat_name}** stehen keine unregelmäßigen Sonderkosten an.")

    # 3. Cashflow & Puffer-Schalter
    st.markdown(f"### 💶 Cashflow-Kalkulation für {gewaehlter_monat_name}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Veranschlagtes Nettoeinkommen", f"{einkommen:,.2f} €")
    basis_ausgaben = regulaere_fixkosten if regulaere_fixkosten > 0 else ausgaben_aktuell
    c2.metric(f"Reguläre Fixkosten ({gewaehlter_monat_name})", f"{basis_ausgaben:,.2f} €")
    
    ueberschuss_vor_sonder = max(0.0, einkommen - basis_ausgaben)
    c3.metric("Überschuss vor Sonderkosten", f"{ueberschuss_vor_sonder:,.2f} €")

    nutze_puffer = st.checkbox(
        f"🛡️ Sonderfälligkeiten für {gewaehlter_monat_name} ({sonderkosten_summe:,.2f} €) abziehen und auf Girokonto belassen", 
        value=True if sonderkosten_summe > 0 else False
    )

    verfuegbares_kapital = (ueberschuss_vor_sonder - sonderkosten_summe) if nutze_puffer else ueberschuss_vor_sonder
    verfuegbares_kapital_effektiv = max(0.0, verfuegbares_kapital)

    st.caption(f"Verfügbares freies Kapital zur Allokation im {gewaehlter_monat_name}: **{verfuegbares_kapital_effektiv:,.2f} €**")

    # 4. Turnaround-Modus
    turnaround = data.get("turnaround_analyse", {})
    ist_im_minus = (ueberschuss_vor_sonder - sonderkosten_summe) < 0
    engpass = turnaround.get("engpass_erkannt", False) or ist_im_minus

    if engpass:
        st.divider()
        st.error(f"🚨 **Minus-Spiralen-Bremse: Im {gewaehlter_monat_name} droht ein Engpass!**")
        with st.expander(f"🛠️ **KI-Notfallplan für {gewaehlter_monat_name}**", expanded=True):
            st.markdown(f"**Ursachen:**\n\n{turnaround.get('ursachen', 'Ausgaben übersteigen das Budget.')}")
            hebel = turnaround.get("konkrete_einsparhebel", [])
            if hebel:
                st.markdown("#### 🎯 Konkrete Hebel aus deinen Belegen:")
                cols_hebel = st.columns(min(len(hebel), 3))
                for idx, h in enumerate(hebel):
                    cols_hebel[idx % 3].warning(
                        f"**{h.get('bereich', 'Ausgabe')}**\n\n"
                        f"Potenzial: **+{h.get('sparpotenzial', 0.0):,.2f} €**\n\n"
                        f"*{h.get('massnahme', '')}*"
                    )
            st.markdown(f"#### 📅 Fahrplan für {gewaehlter_monat_name}:\n{turnaround.get('fahrplan_kommender_monat', 'Sparpläne pausieren und Konsum drosseln.')}")

    st.divider()

    # --- 5. BEIDE WEGE NEBENEINANDER MIT SPARPLAN-GLÄTTUNG ---
    col_links, col_rechts = st.columns(2)

    with col_links:
        st.subheader(f"📐 Weg 1: Nach deinen Reglern ({gewaehlter_monat_name})")
        st.caption("Fester Dauer-Sparplan + flexibles Top-Up.")
        
        if verfuegbares_kapital <= 0:
            st.warning(f"⚠️ **Kein freies Budget im {gewaehlter_monat_name}:** Dauer-Sparplan idealerweise für 1 Monat pausieren.")
            zufuhr_ng_w1 = 0.0
            etf_dauer_w1 = 0.0
            etf_topup_w1 = 0.0
            zins_w1 = 0.0
        else:
            bedarf_ng = max(0.0, float(notgroschen_ziel - notgroschen_ist))
            zufuhr_ng_w1 = min(verfuegbares_kapital_effektiv, bedarf_ng)
            rest_anlage = verfuegbares_kapital_effektiv - zufuhr_ng_w1
            
            etf_gesamt = rest_anlage * (etf_quote / 100.0)
            zins_w1 = rest_anlage * (zins_quote / 100.0)
            
            etf_dauer_w1 = min(etf_gesamt, float(fester_basis_sparplan))
            etf_topup_w1 = max(0.0, etf_gesamt - etf_dauer_w1)

            st.markdown(f"""
            * 🛡️ **Notgroschen auffüllen:** `{zufuhr_ng_w1:,.2f} €`
            * 🔄 **Fester ETF-Dauer-Sparplan (TR):** `{etf_dauer_w1:,.2f} €` *(Dauerauftrag läuft weiter)*
            * ➕ **Flexibles ETF Top-Up (Einmalkauf):** `{etf_topup_w1:,.2f} €`
            * 🏦 **Zinsbaustein / Tagesgeld:** `{zins_w1:,.2f} €`
            * 🎯 **Einzelaktien / Krypto:** `0,00 €` *(starr)*
            """)

    with col_rechts:
        st.subheader(f"🧠 Weg 2: Freie KI-Zweitmeinung ({gewaehlter_monat_name})")
        st.caption("Situative Verteilung mit Rebalancing & Glättung.")
        
        ki_daten = data.get("ki_zweitmeinung", {})
        ki_vert = ki_daten.get("verteilung", {})
        
        if verfuegbares_kapital <= 0:
            st.info(f"💡 **KI-Rat für {gewaehlter_monat_name}:** Sparpläne pausieren, kein Krypto-Nachkauf, Liquidität sichern.")
            ki_ng = 0.0
            ki_etf_dauer = 0.0
            ki_etf_topup = 0.0
            ki_aktien = 0.0
            ki_krypto = 0.0
            ki_zins = 0.0
        else:
            summe_ki = sum(ki_vert.values()) if sum(ki_vert.values()) > 0 else 1.0
            skalierung = verfuegbares_kapital_effektiv / summe_ki if summe_ki > 0 else 1.0

            ki_ng = ki_vert.get("notgroschen", 0.0) * skalierung
            ki_etf_roh = ki_vert.get("etf_einmalkauf", 0.0) * skalierung
            ki_aktien = ki_vert.get("einzelaktien", 0.0) * skalierung
            ki_krypto = ki_vert.get("krypto", 0.0) * skalierung
            ki_zins = ki_vert.get("zinsbaustein", 0.0) * skalierung

            ki_etf_dauer = min(ki_etf_roh, float(fester_basis_sparplan))
            ki_etf_topup = max(0.0, ki_etf_roh - ki_etf_dauer)

            st.markdown(f"""
            * 🛡️ **Notgroschen Zufuhr:** `{ki_ng:,.2f} €`
            * 🔄 **Fester ETF-Dauer-Sparplan (TR):** `{ki_etf_dauer:,.2f} €`
            * ➕ **Flexibles ETF Top-Up (Einmalkauf):** `{ki_etf_topup:,.2f} €`
            * 🏦 **Zinsbaustein / Cash:** `{ki_zins:,.2f} €`
            * 🎯 **Einzelaktien (Chancen):** `{ki_aktien:,.2f} €`
            * 🪙 **Kryptowährungen:** `{ki_krypto:,.2f} €`
            """)
        
        st.markdown(f"**Strategisches Urteil:**\n\n{ki_daten.get('kommentar', 'Keine Begründung verfügbar.')}")
        if ki_daten.get("krypto_aktien_fazit"):
            st.caption(f"**Krypto- & Aktienstatus:** {ki_daten.get('krypto_aktien_fazit')}")

    # --- 6. 1-KLICK AKTIONSPLAN FÜR APPLE NOTIZEN ---
    st.divider()
    st.markdown(f"### 📋 Dein 1-Klick Aktionsplan für {gewaehlter_monat_name} (Apple Notizen)")
    st.write("Kopiere diesen Block mit dem Symbol oben rechts im grauen Kasten und füge ihn direkt in deine Apple Notizen ein:")

    aktionsplan_notiz = f"""# Finanz-Aktionsplan {gewaehlter_monat_name}
Erstellt am: {datetime.now().strftime('%d.%m.%Y')}
---------------------------------------------
1. GIROKONTO & RESERVIERUNG:
   - Mindestpuffer auf Giro belassen: {giro_puffer_ziel:,.2f} €
   - Reservierung für Sonderfälligkeiten ({gewaehlter_monat_name}): {sonderkosten_summe:,.2f} €
   {f'-> Posten: ' + ', '.join([x.get('posten') for x in faellig_in_auswahl]) if faellig_in_auswahl else '-> Keine Sonderfälligkeiten'}

2. TRADE REPUBLIC / BROKER (Empfehlung Weg 2):
   - Dauer-Sparplan (ETF): {ki_etf_dauer:,.2f} € (unverändert laufen lassen)
   - Einmal-Order / Top-Up (ETF): {ki_etf_topup:,.2f} € ausführen
   - Einzelaktien Order: {ki_aktien:,.2f} €

3. NOTGROSCHEN & LIQUIDITÄT:
   - Überweisung auf Tagesgeld/Notgroschen: {ki_ng:,.2f} €
   - Zusätzlicher Zinsbaustein: {ki_zins:,.2f} €

4. KRYPTO-BÖRSE:
   - Zukauf Krypto: {ki_krypto:,.2f} €
---------------------------------------------
Freies Gesamtkapital umgesetzt: {verfuegbares_kapital_effektiv:,.2f} €
"""
    st.code(aktionsplan_notiz, language="markdown")

    # 7. Gesamter Jahreskalender
    if alle_intervalle:
        st.divider()
        with st.expander("📋 Vollständige Jahresübersicht aller erfassten Intervallkosten"):
            df_int = pd.DataFrame(alle_intervalle)
            st.dataframe(df_int, use_container_width=True)
