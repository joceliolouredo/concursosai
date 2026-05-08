import streamlit as st
from groq import Groq
import json
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# ==============================================================================
# 1. CONFIGURAÇÃO DE SEGURANÇA E IA (GROQ)
# ==============================================================================
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("⚠️ Erro: Chave de API não encontrada nos Secrets do Streamlit Cloud.")

# ==============================================================================
# 2. SISTEMA de BANCO de DADOS (Coach AI Database)
# ==============================================================================
DB_NAME = 'coach_ai_v3.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS simulados (id INTEGER PRIMARY KEY, concurso TEXT, cargo TEXT, dificuldade TEXT, data TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS questoes 
                 (id INTEGER PRIMARY KEY, simulado_id INTEGER, materia TEXT, pergunta TEXT, 
                 opcoes TEXT, correta TEXT, justificativa TEXT)''')
    conn.commit()
    conn.close()

def save_simulado(concurso, cargo, dificuldade):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute('INSERT INTO simulados (concurso, cargo, dificuldade, data) VALUES (?, ?, ?, ?)', (concurso, cargo, dificuldade, data_atual))
    id_simulado = c.lastrowid
    conn.commit()
    conn.close()
    return id_simulado

def save_questoes(simulado_id, questoes):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for q in questoes:
        c.execute('INSERT INTO questoes (simulado_id, materia, pergunta, opcoes, correta, justificativa) VALUES (?, ?, ?, ?, ?, ?)',
                  (simulado_id, q.get('materia', 'Geral'), q['pergunta'], json.dumps(q['opcoes']), q['correta'], q['justificativa']))
    conn.commit()
    conn.close()

def get_simulados():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM simulados ORDER BY id DESC", conn)
    conn.close()
    return df

def get_questoes(simulado_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM questoes WHERE simulado_id = ?', (simulado_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "materia": r[2], "pergunta": r[3], "opcoes": json.loads(r[4]), "correta": r[5], "justificativa": r[6]} for r in rows]

# ==============================================================================
# 3. MOTOR de GERAÇÃO de QUESTÕES (IA GROQ)
# ==============================================================================
def ai_generate_questions(concurso, cargo, qtd_total, dificuldade):
    prompt = f"""
    Você é o Coach AI, um professor especialista em concursos públicos.
    Crie um simulado para o concurso: {concurso}, especificamente para o cargo de: {cargo}.
    QUANTIDADE TOTAL: {qtd_total} questões.
    NÍVEL DE DIFICULDADE: {dificuldade}.
    
    Siga rigorosamente:
    1. Distribua as questões entre as matérias que REALMENTE caem para este cargo.
    2. Crie alternativas completas e plausíveis (A, B, C, D).
    3. Retorne EXCLUSIVAMENTE um JSON no formato de lista.
    
    Modelo do JSON:
    {{
      "questoes": [
        {{
          "materia": "Nome da Matéria",
          "pergunta": "Texto da pergunta",
          "opcoes": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
          "correta": "A",
          "justificativa": "Explicação técnica curta."
        }}
      ]
    }}
    """
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile", 
        response_format={"type": "json_object"} 
    )
    res = json.loads(chat_completion.choices[0].message.content)
    return res.get("questoes", [])

# ==============================================================================
# 4. INTERFACE DO USUÁRIO (HARMONIZED LIGHT THEME)
# ==============================================================================
init_db()
st.set_page_config(page_title="Coach AI | Mentor de Concursos", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA; color: #212529; }
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E0E0E0; }
    .q-card { background-color: #FFFFFF; padding: 25px; border-radius: 12px; border: 1px solid #E0E0E0; margin-bottom: 20px; color: #212529; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { background-color: #0056b3 !important; color: white !important; font-weight: 600 !important; border-radius: 8px !important; border: none !important; transition: 0.2s; }
    .stButton>button:hover { background-color: #004494 !important; transform: translateY(-1px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input { background-color: #FFFFFF !important; color: #212529 !important; border: 1px solid #CED4DA !important; }
    h1, h2, h3 { color: #004085 !important; font-weight: 700 !important; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.title("🚀 Coach AI")
st.sidebar.markdown("---")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "🎯 Gerar Simulado", "📜 Histórico"])

if menu == "🏠 Home":
    st.title("🎯 Coach AI")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""
        ### Seu Mentor Inteligente para Aprovação.
        O **Coach AI** utiliza inteligência artificial de última geração para criar simulados precisos, 
        analisar seu desempenho e sugerir reforços nos pontos onde você mais erra.
        """)
        st.info("💡 **Dica:** Para melhores resultados, especifique bem o nome do cargo.")
    with col2:
        st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", use_container_width=True)

elif menu == "🎯 Gerar Simulado":
    st.title("🎯 Novo Simulado")
    
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            concurso = st.text_input("Nome do Concurso", placeholder="Ex: Banco do Brasil...")
            cargo = st.text_input("Cargo/Função", placeholder="Ex: Escriturário...")
        with col2:
            dificuldade = st.selectbox("Nível de Dificuldade", ["Fácil", "Média", "Difícil"])
            qtd_total = st.number_input("Total de Questões", min_value=5, max_value=100, value=10)
    
    if st.button("Gerar Simulado ⚡"):
        if not concurso or not cargo:
            st.error("Por favor, preencha o Concurso e o Cargo.")
        else:
            with st.spinner(f"🤖 Coach AI analisando edital para {cargo}..."):
                try:
                    questoes = ai_generate_questions(concurso, cargo, qtd_total, dificuldade)
                    if questoes:
                        simulado_id = save_simulado(concurso, cargo, dificuldade)
                        save_questoes(simulado_id, questoes)
                        st.session_state.simulado_atual_id = simulado_id
                        st.session_state.respostas_usuario = {}
                        st.session_state.simulado_concluido = False
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    if 'simulado_atual_id' in st.session_state:
        sim_id = st.session_state.simulado_atual_id
        questoes = get_questoes(sim_id)
        
        if not st.session_state.get('simulado_concluido', False):
            st.markdown("### 📝 Responda às Questões")
            with st.form("simulado_form"):
                for i, q in enumerate(questoes):
                    st.markdown(f"""<div class="q-card">
                        <small style="color: #6c757d;">{q['materia'].upper()}</small><br>
                        <strong style="font-size:1.1em;">Questão {i+1}</strong><br>{q['pergunta']}
                    </div>""", unsafe_allow_html=True)
                    opcoes_formatadas = [f"{k}) {v}" for k, v in q['opcoes'].items()]
                    resp = st.radio(f"Sua resposta para a Q{i+1}:", options=opcoes_formatadas, key=f"q_{i}")
                    st.session_state.respostas_usuario[i] = resp[0]
                    st.write("")
                if st.form_submit_button("Finalizar e Analisar Desempenho"):
                    st.session_state.simulado_concluido = True
                    st.rerun()
        else:
            st.header("📊 Dashboard de Desempenho")
            stats = {} 
            for i, q in enumerate(questoes):
                materia = q['materia']
                if materia not in stats: stats[materia] = {"corretas": 0, "total": 0}
                stats[materia]["total"] += 1
                if st.session_state.respostas_usuario.get(i) == q['correta']:
                    stats[materia]["corretas"] += 1
            
            df_stats = pd.DataFrame([{"Matéria": k, "Aproveitamento": (v["corretas"]/v["total"])*100, "Corretas": v["corretas"], "Total": v["total"], "Status": "Sólido" if (v["corretas"]/v["total"]) >= 0.7 else "Atenção" if (v["corretas"]/v["total"]) >= 0.5 else "Crítico"} for k, v in stats.items()])
            color_map = {"Sólido": "#28a745", "Atenção": "#ffc107", "Crítico": "#dc3545"}
            df_stats['Cor'] = df_stats['Status'].map(color_map)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_stats['Matéria'], y=df_stats['Aproveitamento'], marker_color=df_stats['Cor'],
                                text=df_stats['Aproveitamento'].apply(lambda x: f"{x:.1f}%"), textposition='outside',
                                customdata=df_stats[['Corretas', 'Total']],
                                hovertemplate="<b>%{x}</b><br>Aproveitamento: %{y:.1f}%<br>Acertos: %{customdata[0]}/%{customdata[1]}<extra></extra>"))
            fig.add_hline(y=70, line_dash="dash", line_color="#6c757d", annotation_text="Meta (70%)")
            fig.update_layout(title="Aproveitamento por Matéria (%)", yaxis=dict(range=[0, 110]), template="plotly_white", showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            
            materias_fracas = [m for m, v in stats.items() if (v["corretas"]/v["total"]) < 0.7]
            if materias_fracas:
                st.warning(f"🚨 **Coach AI detectou fraquezas em:** {', '.join(materias_fracas)}")
                if st.button("Gerar Questões de Reforço Agora! 📚"):
                    with st.spinner("Criando reforço..."):
                        # CORREÇÃO AQUI: Passando concurso, cargo, qtd e dificuldade (4 argumentos)
                        questoes_ref = ai_generate_questions(concurso, cargo, 5, "Média")
                        for qr in questoes_ref:
                            st.markdown(f"""<div class="q-card">
                                <strong style="color:#0056b3;">{qr['materia']} (Reforço)</strong><br>{qr['pergunta']}<br>
                                <span style="color:#28a745"><b>Correta: {qr['correta']}</b></span><br>
                                <small><i>{qr['justificativa']}</i></small>
                            </div>""", unsafe_allow_html=True)
            else:
                st.success("🌟 Desempenho excelente!")

            st.divider()
            st.subheader("🔍 Revisão Detalhada")
            for i, q in enumerate(questoes):
                user_ans = st.session_state.respostas_usuario.get(i, "N/A")
                correct = q['correta']
                color = "#28a745" if user_ans == correct else "#dc3545"
                st.markdown(f"""<div class="q-card" style="border-left: 6px solid {color}">
                    <strong style="color:#495057;">{q['materia']} | Q{i+1}</strong><br>{q['pergunta']}<br><br>
                    Sua resposta: <span style="color:{color}; font-weight:bold;">{user_ans}</span> | 
                    Correta: <span style="color:#28a745; font-weight:bold;">{correct}</span><br>
                    <small><b style="color:#495057;">✅ Justificativa:</b> {q['justificativa']}</small>
                </div>""", unsafe_allow_html=True)
            
            if st.button("Sair e Voltar ao Início"):
                st.session_state.simulado_atual_id = None
                st.session_state.simulado_concluido = False
                st.rerun()

elif menu == "📜 Histórico":
    st.title("📜 Meus Simulados")
    df = get_simulados()
    if df.empty:
        st.info("Nenhum simulado registrado.")
    else:
        opcoes = df['id'].tolist()
        nomes = [f"ID {id} - {row['concurso']} ({row['cargo']}) - {row['data']}" for id, row in zip(df['id'], df.to_dict('records'))]
        escolha = st.selectbox("Escolha um simulado para revisar:", opcoes, format_func=lambda x: nomes[df[df['id']==x].index[0]])
        if st.button("Revisar Questões"):
            questoes = get_questoes(escolha)
            for i, q in enumerate(questoes):
                st.markdown(f"""<div class="q-card">
                    <strong style="color:#495057;">{q['materia']} | Questão {i+1}</strong><br>{q['pergunta']}<br><br>
                    <span style="color:#28a745"><b>Resposta Correta: {q['correta']}</b></span><br>
                    <small><b style="color:#495057;">✅ Justificativa:</b> {q['justificativa']}</small>
                </div>""", unsafe_allow_html=True)
