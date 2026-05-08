import streamlit as st
from groq import Groq
import json
import sqlite3
import pandas as pd
import random

# ==============================================================================
# 1. CONFIGURAÇÃO DE SEGURANÇA E IA (GROQ)
# ==============================================================================
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("⚠️ Erro: Chave de API não encontrada nos Secrets.")

# ==============================================================================
# 2. SISTEMA DE BANCO DE DADOS (HUB)
# ==============================================================================
def init_db():
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS simulados (id INTEGER PRIMARY KEY, concurso TEXT, materia TEXT, data TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS questoes 
                 (id INTEGER PRIMARY KEY, simulado_id INTEGER, pergunta TEXT, 
                 opcoes TEXT, correta TEXT, justificativa TEXT)''')
    conn.commit()
    conn.close()

def save_simulado(concurso, materia):
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    from datetime import datetime
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute('INSERT INTO simulados (concurso, materia, data) VALUES (?, ?, ?)', (concurso, materia, data_atual))
    id_simulado = c.lastrowid
    conn.commit()
    conn.close()
    return id_simulado

def save_questoes(simulado_id, questoes):
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    for q in questoes:
        c.execute('INSERT INTO questoes (simulado_id, pergunta, opcoes, correta, justificativa) VALUES (?, ?, ?, ?, ?)',
                  (simulado_id, q['pergunta'], json.dumps(q['opcoes']), q['correta'], q['justificativa']))
    conn.commit()
    conn.close()

def get_simulados():
    conn = sqlite3.connect('hub_simulados.db')
    df = pd.read_sql_query("SELECT * FROM simulados ORDER BY id DESC", conn)
    conn.close()
    return df

def get_questoes(simulado_id):
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    c.execute('SELECT * FROM questoes WHERE simulado_id = ?', (simulado_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "pergunta": r[2], "opcoes": json.loads(r[3]), "correta": r[4], "justificativa": r[5]} for r in rows]

# ==============================================================================
# 3. MOTOR DE GERAÇÃO de QUESTÕES (GROQ)
# ==============================================================================
def ai_generate_questions(concurso, materia, quantidade):
    prompt = f"""
    Você é um professor especialista em concursos públicos. 
    Crie {quantidade} questões de múltipla escolha para o concurso: {concurso}, focado na matéria: {materia}.
    
    REGRAS CRÍTICAS:
    1. Crie alternativas COMPLETAS e plausíveis. Não deixe opções vazias.
    2. Cada questão deve ter exatamente 4 opções (A, B, C, D).
    3. Retorne EXCLUSIVAMENTE um JSON no formato de lista.
    4. A justificativa deve ser técnica e objetiva.
    
    Modelo do JSON:
    {{
      "questoes": [
        {{
          "pergunta": "Texto da pergunta",
          "opcoes": {{"A": "Texto da opção A", "B": "Texto da opção B", "C": "Texto da opção C", "D": "Texto da opção D"}},
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
# 4. INTERFACE DO USUÁRIO (HUB AI)
# ==============================================================================
init_db()
st.set_page_config(page_title="AI Simulado Expert", layout="wide", page_icon="🎯")

st.sidebar.title("🚀 Menu Hub AI")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "🎯 Gerar Novo Simulado", "📜 Meus Simulados"])

if menu == "🏠 Home":
    st.title("🎯 AI Simulado Expert")
    st.markdown("""
    **O simulador de concursos mais rápido do mundo.**
     la IA gera questões inéditas e precisas baseadas no padrão das bancas.
    """)
    st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", width=500)

elif menu == "🎯 Gerar Novo Simulado":
    st.title("🎯 Gerar Simulado Inteligente")
    
    col1, col2 = st.columns(2)
    with col1:
        concurso = st.text_input("Nome do Concurso", placeholder="Ex: Banco do Brasil, PF, TJSP...")
        materia = st.text_input("Matéria/Tópico", placeholder="Ex: Direito Constitucional, Português...")
    with col2:
        qtd = st.number_input("Quantidade de Questões", min_value=1, max_value=30, value=5)
    
    if st.button("Gerar Simulado Agora ⚡"):
        if not concurso or not materia:
            st.error("Por favor, preencha o concurso e a matéria.")
        else:
            with st.spinner(f"IA criando {qtd} questões..."):
                try:
                    questoes = ai_generate_questions(concurso, materia, qtd)
                    if questoes:
                        simulado_id = save_simulado(concurso, materia)
                        save_questoes(simulado_id, questoes)
                        st.success("Simulado gerado com sucesso!")
                        st.session_state.simulado_atual_id = simulado_id
                        st.session_state.respostas_usuario = {}
                        st.rerun()
                    else:
                        st.error("A IA não conseguiu gerar as questões.")
                except Exception as e:
                    st.error(f"Erro técnico: {e}")

    if 'simulado_atual_id' in st.session_state:
        st.divider()
        sim_id = st.session_state.simulado_atual_id
        questoes = get_questoes(sim_id)
        
        with st.form("simulado_form"):
            for i, q in enumerate(questoes):
                st.markdown(f"**Questão {i+1}**")
                st.write(q['pergunta'])
                
                # CORREÇÃO AQUI: Criamos labels como "A) Texto da Opção"
                opcoes_formatadas = [f"{k}) {v}" for k, v in q['opcoes'].items()]
                
                # O usuário escolhe a frase, mas nós guardamos apenas a letra (primeiro caractere)
                resp = st.radio(f"Selecione a alternativa correta:", options=opcoes_formatadas, key=f"q_{i}")
                st.session_state.respostas_usuario[i] = resp[0] # Pega apenas a letra 'A', 'B', etc.
                st.write("---")
            
            if st.form_submit_button("Finalizar e Ver Justificativas"):
                st.divider()
                st.header("✅ Resultado")
                for i, q in enumerate(questoes):
                    user_ans = st.session_state.respostas_usuario.get(i, "N/A")
                    correct = q['correta']
                    color = "green" if user_ans == correct else "red"
                    st.markdown(f"**Questão {i+1}**")
                    st.markdown(f"Sua resposta: :{color}[{user_ans}] | Correta: :green[{correct}]")
                    st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                    st.write("---")

elif menu == "📜 Meus Simulados":
    st.title("📜 Histórico de Simulados")
    df = get_simulados()
    
    if df.empty:
        st.info("Você ainda não gerou nenhum simulado.")
    else:
        opcoes = df['id'].tolist()
        nomes = [f"ID {id} - {row['concurso']} ({row['materia']}) - {row['data']}" for id, row in zip(df['id'], df.to_dict('records'))]
        escolha = st.selectbox("Escolha um simulado para revisar:", opcoes, format_func=lambda x: nomes[df[df['id']==x].index[0]])
        
        if st.button("Revisar Questões"):
            questoes = get_questoes(escolha)
            for i, q in enumerate(questoes):
                st.markdown(f"**Questão {i+1}**")
                st.write(q['pergunta'])
                st.markdown(f"**Resposta Correta:** :green[{q['correta']}]")
                st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                st.write("---")
