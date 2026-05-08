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
    c.execute('CREATE TABLE IF NOT EXISTS simulados (id INTEGER PRIMARY KEY, concurso TEXT, data TEXT)')
    # Adicionamos a coluna 'materia' na tabela de questões
    c.execute('''CREATE TABLE IF NOT EXISTS questoes 
                 (id INTEGER PRIMARY KEY, simulado_id INTEGER, materia TEXT, pergunta TEXT, 
                 opcoes TEXT, correta TEXT, justificativa TEXT)''')
    conn.commit()
    conn.close()

def save_simulado(concurso):
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    from datetime import datetime
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute('INSERT INTO simulados (concurso, data) VALUES (?, ?)', (concurso, data_atual))
    id_simulado = c.lastrowid
    conn.commit()
    conn.close()
    return id_simulado

def save_questoes(simulado_id, questoes):
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    for q in questoes:
        c.execute('INSERT INTO questoes (simulado_id, materia, pergunta, opcoes, correta, justificativa) VALUES (?, ?, ?, ?, ?, ?)',
                  (simulado_id, q.get('materia', 'Geral'), q['pergunta'], json.dumps(q['opcoes']), q['correta'], q['justificativa']))
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
    return [{"id": r[0], "materia": r[2], "pergunta": r[3], "opcoes": json.loads(r[4]), "correta": r[5], "justificativa": r[6]} for r in rows]

# ==============================================================================
# 3. MOTOR DE GERAÇÃO (DISTRIBUIÇÃO AUTOMÁTICA)
# ==============================================================================
def ai_generate_complete_exam(concurso, qtd_total):
    prompt = f"""
    Você é um consultor de editais de concursos públicos.
    Sua tarefa é criar um simulado COMPLETO para o concurso: {concurso}, com um total de {qtd_total} questões.
    
    PASSO A PASSO:
    1. Analise a estrutura comum do edital para o concurso {concurso}.
    2. Distribua as {qtd_total} questões entre as matérias mais importantes (ex: Português, Direito, Raciocínio Lógico, etc) de forma proporcional ao peso real do concurso.
    3. Crie as questões de múltipla escolha (A, B, C, D).
    
    REGRAS:
    - Retorne EXCLUSIVAMENTE um JSON no formato de lista.
    - Cada objeto de questão DEVE conter o campo "materia".
    - As alternativas devem ser completas e plausíveis.
    - A justificativa deve ser técnica e objetiva.
    
    Modelo do JSON:
    {{
      "questoes": [
        {{
          "materia": "Nome da Matéria",
          "pergunta": "Texto da pergunta",
          "opcoes": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
          "correta": "A",
          "justificativa": "Explicação técnica."
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
# 4. INTERFACE DO USUÁRIO
# ==============================================================================
init_db()
st.set_page_config(page_title="AI Simulado Expert", layout="wide", page_icon="🎯")

st.sidebar.title("🚀 Menu Hub AI")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "🎯 Gerar Simulado Completo", "📜 Meus Simulados"])

if menu == "🏠 Home":
    st.title("🎯 AI Simulado Expert")
    st.markdown("""
    **O sistema mais inteligente para concurseiros.**
    
    Agora você não precisa nem escolher a matéria! 
    Basta digitar o nome do concurso e a quantidade de questões.
    
    **A IA faz tudo:**
    1. Analisa o edital do concurso.
    2. Divide a quantidade de questões por matéria proporcionalmente.
    3. Gera as questões no padrão da banca.
    """)
    st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", width=500)

elif menu == "🎯 Gerar Simulado Completo":
    st.title("🎯 Gerador Automático de Editais")
    
    col1, col2 = st.columns(2)
    with col1:
        concurso = st.text_input("Nome do Concurso", placeholder="Ex: Banco do Brasil, Polícia Federal, TJSP...")
    with col2:
        qtd_total = st.number_input("Total de Questões do Simulado", min_value=5, max_value=100, value=20)
    
    if st.button("Gerar Simulado Completo ⚡"):
        if not concurso:
            st.error("Por favor, digite o nome do concurso.")
        else:
            with st.spinner(f"Analisando edital de {concurso} e distribuindo {qtd_total} questões..."):
                try:
                    questoes = ai_generate_complete_exam(concurso, qtd_total)
                    if questoes:
                        simulado_id = save_simulado(concurso)
                        save_questoes(simulado_id, questoes)
                        st.success(f"Simulado gerado com sucesso! {len(questoes)} questões distribuídas por matéria.")
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
                # EXIBE A MATÉRIA ACIMA DA QUESTÃO
                st.markdown(f"**{q['materia']}**") 
                st.markdown(f"**Questão {i+1}**")
                st.write(q['pergunta'])
                
                opcoes_formatadas = [f"{k}) {v}" for k, v in q['opcoes'].items()]
                resp = st.radio(f"Selecione a alternativa:", options=opcoes_formatadas, key=f"q_{i}")
                st.session_state.respostas_usuario[i] = resp[0]
                st.write("---")
            
            if st.form_submit_button("Finalizar e Ver Justificativas"):
                st.divider()
                st.header("✅ Resultado")
                for i, q in enumerate(questoes):
                    user_ans = st.session_state.respostas_usuario.get(i, "N/A")
                    correct = q['correta']
                    color = "green" if user_ans == correct else "red"
                    st.markdown(f"**{q['materia']} | Questão {i+1}**")
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
        nomes = [f"ID {id} - {row['concurso']} - {row['data']}" for id, row in zip(df['id'], df.to_dict('records'))]
        escolha = st.selectbox("Escolha um simulado para revisar:", opcoes, format_func=lambda x: nomes[df[df['id']==x].index[0]])
        
        if st.button("Revisar Questões"):
            questoes = get_questoes(escolha)
            for i, q in enumerate(questoes):
                st.markdown(f"**{q['materia']} | Questão {i+1}**")
                st.write(q['pergunta'])
                st.markdown(f"**Resposta Correta:** :green[{q['correta']}]")
                st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                st.write("---")
