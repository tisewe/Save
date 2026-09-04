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

# --- Seitenleiste: Deine Baseline-Regler (Neue Standard-Werte) ---
with st.sidebar:
    st.header("⚙️ Deine Baseline-Regler")
    st.caption("Dient als persönliche Referenzgröße (Weg 1). Die KI (Weg 2) bewertet unabhängig davon.")
    giro_puffer_ziel = st.number_input("Wunsch-Puffer Girokonto (€)", value=500, step=50)
    notgroschen_ziel = st.number_input("Notgroschen Ziel (€)", value=3000, step=250)
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
st.write("Lade Dokumente hoch (All-Time-Historie). Die KI glättet Schichtlöhne über einen 3-Monats-Schnitt, erfasst wiederkehrende Festbeträge und bereitet alle Buchungen transparent auf.")

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
            
        with st.spinner("Gemini analysiert Historie, berechnet 3-Monats-Schichtlohn, filtert Fixkosten & Zahlungsanbieter..."):
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
                Du bist ein hochpräziser forensischer Finanzanalyst und Chef-Anlagestratege nach Gerd Kommer.
                Heutiges Referenzdatum: {heute}.

                WICHTIGE PRÜF- UND FILTERREGELN:
                1. LOHN / GEHALT (SCHICHTARBEIT & DURCHSCHNITT):
                   - Der Nutzer arbeitet im Schichtdienst; das Gehalt schwankt monatlich.
                   - Ermittle die Netto-Gehaltseingänge der letzten 3 Monate.
                   - Berechne zwingend das mathematische Mittel (3-Monats-Durchschnitt). Verwende diesen geglätteten Durchschnitt als verbindliches Plan-Nettoeinkommen ("monatseinkommen_durchschnitt_3m").
                
                2. FIXKOSTEN-INTELLIGENZ & ZAHLUNGSANBIETER:
                   - Erfasse alle festen Monatsverpflichtungen sehr gründlich.
                   - ZAHLUNGSANBIETER: Analysiere PayPal, Klarna oder regelmäßige Abbuchungsdienste. Wenn hier wiederkehrende Fixposten (Abos, Raten) laufen, buche sie den Fixkosten zu.
                   - QUASI-FESTE ZAHLUNGEN: Erkenne Beträge, die jeden Monat in etwa gleicher Höhe anfallen (z.B. feste 500 € Überweisungen, Miete, Unterhalt, Verträge), selbst wenn der Kalendertag der Buchung variiert (z.B. mal am 1., mal am 10., mal am 28.). Buche diese zwingend zu den regulären Monatsfixkosten!
                
                3. JAHRES- & SONDER-INTERVALLE:
                   - Alle quartalsweisen, halbjährlichen oder jährlichen Fälligkeiten mit den entsprechenden Monaten (faellige_monate als Array 1..12).
                
                4. BUCHUNGSAUFSTELLUNG (Bank-Ersatz):
                   - Erstelle saubere Listen für:
                     a) Einnahmen (letzte Monate)
                     b) Reguläre Fixkosten (inkl. Empfänger, Betrag, Kategorie/Zahlungsdienstleister und kurzer Notiz)
                     c) Typische variable Monatsausgaben / Konsum

                5. PORTFOLIO & REBALANCING:
                   - Saldo Giro, Notgroschen, ETFs, Einzelaktien, Krypto.
                   - Zweitmeinung (Weg 2): Situativ, mit Sparplan-Glättung (Dauerläufer vs Top-Up) und Rebalancing-Ampel.

                Antworte AUSSCHLIESSLICH als valides JSON:
                {{
                    "analysierter_zeitraum": string,
                    "aktueller_monatsbezug": string,
                    "lohn_historie_3m": [
                        {{"monat": string, "betrag": float}}
                    ],
                    "monatseinkommen_durchschnitt_3m": float,
                    "monatseinkommen_letzter_monat": float,
                    "ausgaben_aktuell": float,
                    "regulaere_monatliche_fixkosten": float,
                    "saldo_giro": float,
                    "saldo_notgroschen": float,
                    "portfolio": {{
                        "etfs": float,
                        "einzelaktien": float,
                        "krypto": float
                    }},
                    "einnahmen_tabelle": [
                        {{"herkunft": string, "betrag": float, "zeitraum": string}}
                    ],
                    "fixkosten_tabelle": [
                        {{"empfaenger": string, "betrag": float, "kategorie": string, "erkennungsgrund": string}}
                    ],
                    "variable_ausgaben_tabelle": [
                        {{"bereich": string, "betrag": float, "beispiel_buchungen": string}}
                    ],
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

# --- Dashboard-Darstellung mit Reiter-Struktur ---
if "analyse_ergebnis" in st.session_state:
    data = st.session_state["analyse_ergebnis"]
    
    zeitraum = data.get("analysierter_zeitraum", "Historie")
    monatsbezug = data.get("aktueller_monatsbezug", "Aktueller Monat")
    
    # 3-Monats-Durchschnitt als stabiles Planungs-Einkommen
    einkommen_3m_schnitt = float(data.get("monatseinkommen_durchschnitt_3m", 0.0))
    einkommen_letzter = float(data.get("monatseinkommen_letzter_monat", 0.0))
    einkommen = einkommen_3m_schnitt if einkommen_3m_schnitt > 0 else einkommen_letzter

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

    # Reiter auf oberster Ebene anlegen
    tab_cockpit, tab_buchungen = st.tabs([
        "🧭 Planungs-Cockpit & Strategie", 
        "📑 Buchungs- & Kosten-Aufstellung (Bank-Ersatz)"
    ])

    # ==========================================
    # REITER 1: COCKPIT & STRATEGIE
    # ==========================================
    with tab_cockpit:
        # 1. Vermögensstatus & Rebalancing-Radar
        st.markdown("### 📊 Vermögensstatus & Rebalancing-Radar")
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.metric("Girokonto", f"{saldo_giro:,.2f} €")
        v2.metric("Notgroschen / Cash", f"{notgroschen_ist:,.2f} €")
        v3.metric("ETFs", f"{wert_etf:,.2f} €")
        v4.metric("Einzelaktien", f"{wert_aktien:,.2f} €")
        v5.metric("Kryptowährungen", f"{wert_krypto:,.2f} €")

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

            if quote_krypto > 15.0:
                st.warning(f"⚠️ **Rebalancing-Alarm (Krypto):** Krypto macht **{quote_krypto:.1f}%** deines Gesamtvermögens aus. Diesen Monat keine Nachkäufe bei Krypto empfohlen!")
            elif quote_aktien > 25.0:
                st.warning(f"⚠️ **Klumpenrisiko Einzelaktien:** Einzelaktien machen **{quote_aktien:.1f}%** aus. Vorzugsweise ETFs stärken.")
            else:
                st.success("🟢 **Portfolio-Balance gesund:** Keine kritischen Klumpenrisiken erkannt.")

        st.divider()

        # 2. Interaktiver Monats-Planer
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

        # 3. Cashflow mit geglättetem Schichtlohn
        st.markdown(f"### 💶 Cashflow-Kalkulation für {gewaehlter_monat_name}")
        c1, c2, c3 = st.columns(3)
        
        c1.metric("Plan-Netto (3-Monats-Schnitt)", f"{einkommen:,.2f} €")
        
        # Details zu den 3 Monaten als Tooltip/Caption
        lohn_historie = data.get("lohn_historie_3m", [])
        if lohn_historie:
            details_str = " | ".join([f"{x.get('monat')}: {float(x.get('betrag', 0.0)):,.0f}€" for x in lohn_historie])
            c1.caption(f"ℹ️ Schicht-Historie: {details_str}")

        basis_ausgaben = regulaere_fixkosten if regulaere_fixkosten > 0 else ausgaben_aktuell
        c2.metric(f"Reguläre Fixkosten (Monat)", f"{basis_ausgaben:,.2f} €")
        
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

        # 5. Duale Strategie
        col_links, col_rechts = st.columns(2)

        with col_links:
            st.subheader(f"📐 Weg 1: Nach deinen Reglern ({gewaehlter_monat_name})")
            st.caption("Fester Dauer-Sparplan + flexibles Top-Up.")
            
            if verfuegbares_kapital <= 0:
                st.warning(f"⚠️ **Kein freies Budget im {gewaehlter_monat_name}:** Dauer-Sparplan idealerweise pausieren.")
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
                * 🔄 **Fester ETF-Dauer-Sparplan (TR):** `{etf_dauer_w1:,.2f} €` *(Standard: {fester_basis_sparplan} €)*
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

        # 6. Aktionsplan Notizen
        st.divider()
        st.markdown(f"### 📋 Dein 1-Klick Aktionsplan für {gewaehlter_monat_name} (Apple Notizen)")
        aktionsplan_notiz = f"""# Finanz-Aktionsplan {gewaehlter_monat_name}
Erstellt am: {datetime.now().strftime('%d.%m.%Y')}
---------------------------------------------
1. GIROKONTO & RESERVIERUNG:
   - Mindestpuffer auf Giro belassen: {giro_puffer_ziel:,.2f} €
   - Reservierung für Sonderfälligkeiten ({gewaehlter_monat_name}): {sonderkosten_summe:,.2f} €
   {f'-> Posten: ' + ', '.join([x.get('posten') for x in faellig_in_auswahl]) if faellig_in_auswahl else '-> Keine Sonderfälligkeiten'}

2. TRADE REPUBLIC / BROKER (Empfehlung Weg 2):
   - Dauer-Sparplan (ETF): {ki_etf_dauer:,.2f} € (Standard weiterlaufen lassen)
   - Einmal-Order / Top-Up (ETF): {ki_etf_topup:,.2f} € ausführen
   - Einzelaktien Order: {ki_aktien:,.2f} €

3. NOTGROSCHEN & LIQUIDITÄT:
   - Überweisung auf Notgroschen: {ki_ng:,.2f} € (Ziel: {notgroschen_ziel:,.2f} €)
   - Zusätzlicher Zinsbaustein: {ki_zins:,.2f} €

4. KRYPTO-BÖRSE:
   - Zukauf Krypto: {ki_krypto:,.2f} €
---------------------------------------------
Freies Gesamtkapital umgesetzt: {verfuegbares_kapital_effektiv:,.2f} €
"""
        st.code(aktionsplan_notiz, language="markdown")

    # ==========================================
    # REITER 2: BUCHUNGS- & KOSTEN-AUFSTELLUNG (BANK-ERSATZ)
    # ==========================================
    with tab_buchungen:
        st.markdown("### 📑 Detaillierte Buchungs- & Kosten-Aufstellung")
        st.caption("Hier siehst du alle aus deinen Belegen extrahierten Positionen aufgeschlüsselt, ohne dich in deine Bank-App einloggen zu müssen.")

        # A. Einnahmen
        st.subheader("💵 1. Erfasste Gehalts- & Einnahmenströme")
        lohn_list = data.get("lohn_historie_3m", [])
        if lohn_list:
            df_lohn = pd.DataFrame(lohn_list)
            df_lohn.rename(columns={"monat": "Monat / Abrechnung", "betrag": "Netto-Auszahlung (€)"}, inplace=True)
            st.table(df_lohn)
            st.info(f"💡 **Berechneter 3-Monats-Durchschnitt:** `{einkommen_3m_schnitt:,.2f} €` (dient als verlässliche Planungsgrundlage)")
        else:
            einnahmen_tabelle = data.get("einnahmen_tabelle", [])
            if einnahmen_tabelle:
                st.table(pd.DataFrame(einnahmen_tabelle))

        st.divider()

        # B. Reguläre monatliche Fixkosten (inkl. Zahlungsanbieter & quasi-feste 500 €)
        st.subheader(f"🔒 2. Monatliche Fixkosten (Gesamtsumme: {regulaere_fixkosten:,.2f} €)")
        st.write("Enthält feste Verträge, erkannte Zahlungsdienstleister (z.B. PayPal-Abos) sowie regelmäßige Monatsbeträge:")
        fixkosten_list = data.get("fixkosten_tabelle", [])
        if fixkosten_list:
            df_fix = pd.DataFrame(fixkosten_list)
            df_fix.rename(columns={
                "empfaenger": "Empfänger / Dienstleister",
                "betrag": "Monatsbetrag (€)",
                "kategorie": "Kategorie",
                "erkennungsgrund": "Erkennungsgrundlage"
            }, inplace=True)
            st.dataframe(df_fix, use_container_width=True)
        else:
            st.info("Keine einzelnen Fixkosten-Posten aufgeschlüsselt.")

        st.divider()

        # C. Variable Ausgaben & Konsum
        st.subheader("🛒 3. Typische variable Ausgaben & Konsum")
        var_list = data.get("variable_ausgaben_tabelle", [])
        if var_list:
            df_var = pd.DataFrame(var_list)
            df_var.rename(columns={
                "bereich": "Ausgabenbereich",
                "betrag": "Monatssumme (€)",
                "beispiel_buchungen": "Typische Buchungen / Händler"
            }, inplace=True)
            st.dataframe(df_var, use_container_width=True)

        st.divider()

        # D. Fälligkeitskalender
        st.subheader("🗓️ 4. Vollständiger Fälligkeitskalender (Sonder-Intervalle)")
        if alle_intervalle:
            df_int = pd.DataFrame(alle_intervalle)
            st.dataframe(df_int, use_container_width=True)
