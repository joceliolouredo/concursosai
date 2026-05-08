import streamlit as st
from groq import Groq
import json
import sqlite3
import pandas as pd
import random
import plotly.express as px
import plotly.graph_objects as go

# ==============================================================================
# 1. CONFIGURAÇÃO de SEGURANÇA E IA (GROQ)
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
    from datetime import datetime
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
# 4. INTERFACE DO USUÁRIO (COACH AI)
# ==============================================================================
init_db()
st.set_page_config(page_title="Coach AI", layout="wide", page_icon="🎯")

st.sidebar.title("🚀 Coach AI")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "🎯 Gerar Simulado", "📜 Histórico"])

if menu == "🏠 Home":
    st.title("🎯 Coach AI")
    st.markdown("""
    **Sua inteligência artificial para aprovação em concursos.**
    
    O **Coach AI** analisa editais, distribui matérias de forma proporcional ao cargo e avalia seu desempenho com dashboards interativos.
    """)
    st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", width=500)

elif menu == "🎯 Gerar Simulado":
    st.title("🎯 Novo Simulado Coach AI")
    
    col1, col2 = st.columns(2)
    with col1:
        concurso = st.text_input("Nome do Concurso", placeholder="Ex: Banco do Brasil, PF...")
        cargo = st.text_input("Cargo/Função", placeholder="Ex: Escriturário, Agente...")
    with col2:
        dificuldade = st.selectbox("Nível de Dificuldade", ["Fácil", "Média", "Difícil"])
        qtd_total = st.number_input("Total de Questões", min_value=5, max_value=100, value=10)
    
    if st.button("Gerar Simulado ⚡"):
        if not concurso or not cargo:
            st.error("Por favor, preencha o Concurso e o Cargo.")
        else:
            with st.spinner(f"Coach AI analisando edital para {cargo}..."):
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
            with st.form("simulado_form"):
                for i, q in enumerate(questoes):
                    st.markdown(f"**{q['materia']}** | Questão {i+1}")
                    st.write(q['pergunta'])
                    opcoes_formatadas = [f"{k}) {v}" for k, v in q['opcoes'].items()]
                    resp = st.radio(f"Escolha a alternativa:", options=opcoes_formatadas, key=f"q_{i}")
                    st.session_state.respostas_usuario[i] = resp[0]
                    st.write("---")
                
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
            
            color_map = {"Sólido": "#2ecc71", "Atenção": "#f1c40f", "Crítico": "#e74c3c"}
            df_stats['Cor'] = df_stats['Status'].map(color_map)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_stats['Matéria'], y=df_stats['Aproveitamento'], marker_color=df_stats['Cor'],
                text=df_stats['Aproveitamento'].apply(lambda x: f"{x:.1f}%"), textposition='outside',
                customdata=df_stats[['Corretas', 'Total']],
                hovertemplate="<b>%{x}</b><br>Aproveitamento: %{y:.1f}%<br>Acertos: %{customdata[0]}/%{customdata[1]}<extra></extra>"
            ))
            fig.add_hline(y=70, line_dash="dash", line_color="gray", annotation_text="Meta de Aprovação (70%)")
            fig.update_layout(title="Aproveitamento por Matéria (%)", yaxis=dict(range=[0, 110]), template="plotly_dark", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            materias_fracas = [m for m, v in stats.items() if (v["corretas"]/v["total"]) < 0.7]
            if materias_fracas:
                st.warning(f"🚨 **Coach AI detectou fraquezas em:** {', '.join(materias_fracas)}")
                if st.button("Gerar Questões de Reforço Agora! 📚"):
                    st.info("O Coach AI está criando questões focadas nos seus erros...")
                    ref_materia = " e ".join(materias_fracas)
                    questoes_ref = ai_generate_questions(f"Reforço {concurso}", 5, "Média")
                    for qr in questoes_ref:
                        st.markdown(f"**{qr['materia']}**: {qr['pergunta']}")
                        st.write(f"Correta: {qr['correta']} | {qr['justificativa']}")
                        st.write("---")
            else:
                st.success("🌟 Desempenho excelente!")

            st.divider()
            st.subheader("Revisão Detalhada")
            for i, q in enumerate(questoes):
                user_ans = st.session_state.respostas_usuario.get(i, "N/A")
                correct = q['correta']
                color = "green" if user_ans == correct else "red"
                st.markdown(f"**{q['materia']} | Q{i+1}**")
                st.markdown(f"Sua resposta: :{color}[{user_ans}] | Correta: :green[{correct}]")
                st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                st.write("---")
            
            if st.button("Sair e Voltar ao Início"):
                st.session_state.simulado_atual_id = None
                st.session_sC_concluido = False
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
                st.markdown(f"**{q['materia']} | Questão {i+1}**")
                st.write(q['pergunta'])
                st.markdown(f"**Resposta Correta:** :green[{q['correta']}]")
                st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                st.write("---")
