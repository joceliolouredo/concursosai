import streamlit as st
from groq import Groq
import PyPDF2
import json
import sqlite3
import pandas as pd
import random # Importado para fazer o sorteio das questões

# ==============================================================================
# 1. CONFIGURAÇÃO DE SEGURANÇA E IA (GROQ)
# ==============================================================================
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("⚠️ Erro: Chave de API não encontrada. Vá em 'Advanced Settings' -> 'Secrets' e adicione: GROQ_API_KEY = 'SUA_CHAVE'")

# ==============================================================================
# 2. SISTEMA DE BANCO DE DADOS (HUB)
# ==============================================================================
def init_db():
    conn = sqlite3.connect('hub_concursos.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS apostilas (id INTEGER PRIMARY KEY, nome TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS questoes 
                 (id INTEGER PRIMARY KEY, apostila_id INTEGER, pergunta TEXT, 
                 opcoes TEXT, correta TEXT, justificativa TEXT)''')
    conn.commit()
    conn.close()

def save_apostila(nome):
    conn = sqlite3.connect('hub_concursos.db')
    c = conn.cursor()
    c.execute('INSERT INTO apostilas (nome) VALUES (?)', (nome,))
    id_apostila = c.lastrowid
    conn.commit()
    conn.close()
    return id_apostila

def save_questoes(apostila_id, questoes):
    conn = sqlite3.connect('hub_concursos.db')
    c = conn.cursor()
    for q in questoes:
        c.execute('INSERT INTO questoes (apostila_id, pergunta, opcoes, correta, justificativa) VALUES (?, ?, ?, ?, ?)',
                  (apostila_id, q['pergunta'], json.dumps(q['opcoes']), q['correta'], q['justificativa']))
    conn.commit()
    conn.close()

def get_apostilas():
    conn = sqlite3.connect('hub_concursos.db')
    df = pd.read_sql_query("SELECT * FROM apostilas", conn)
    conn.close()
    return df

def get_questoes(apostila_id):
    conn = sqlite3.connect('hub_concursos.db')
    c = conn.cursor()
    c.execute('SELECT * FROM questoes WHERE apostila_id = ?', (apostila_id,))
    rows = c.fetchall()
    conn.close()
    questoes = []
    for row in rows:
        questoes.append({
            "id": row[0],
            "pergunta": row[2],
            "opcoes": json.loads(row[3]),
            "correta": row[4],
            "justificativa": row[5]
        })
    return questoes

# ==============================================================================
# 3. PROCESSAMENTO DE DOCUMENTOS E IA (GROQ)
# ==============================================================================
def extract_text_from_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def ai_extract_questions(text, filename):
    prompt = f"""
    Você é um professor especialista em concursos. Analise o conteúdo da apostila '{filename}' e extraia ou crie questões de múltipla escolha.
    
    REGRAS RÍGIDAS:
    1. Retorne EXCLUSIVAMENTE um JSON no formato de lista.
    2. Não escreva nenhuma introdução ou conclusão, apenas o JSON.
    3. A justificativa deve ser curta, técnica e objetiva.
    
    Modelo do JSON:
    [
      {{
        "pergunta": "Texto da pergunta",
        "opcoes": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
        "correta": "A",
        "justificativa": "Justificativa técnica e objetiva."
      }}
    ]
    
    Conteúdo: {text[:12000]} 
    """
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile", 
        response_format={"type": "json_object"} 
    )
    content = chat_completion.choices[0].message.content
    res = json.loads(content)
    if isinstance(res, dict):
        for value in res.values():
            if isinstance(value, list):
                return value
    return res

# ==============================================================================
# 4. INTERFACE DO USUÁRIO (STREAMLIT UI)
# ==============================================================================
init_db()
st.set_page_config(page_title="Hub de Simulados Groq AI", layout="wide", page_icon="⚡")

st.sidebar.title("🚀 Menu Hub Groq")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "📁 Gerenciar Apostilas", "📝 Fazer Simulado"])

if menu == "🏠 Home":
    st.title("⚡ Hub de Simulados Ultra-Rápido")
    st.markdown("""
    Bem-vindo ao seu centro de estudos alimentado por **Groq LPU**.
    
    **Vantagens desta versão:**
    - Processamento quase instantâneo.
    - Inteligência do Llama 3.3.
    - Justificativas técnicas precisas.
    """)
    st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", width=500)

elif menu == "📁 Gerenciar Apostilas":
    st.title("📁 Cadastro de Materiais")
    uploaded_file = st.file_uploader("Subir Nova Apostila (PDF)", type="pdf")
    
    if uploaded_file and st.button("Processar e Salvar no Hub"):
        with st.spinner("Groq está gerando questões em alta velocidade..."):
            try:
                text = extract_text_from_pdf(uploaded_file)
                questoes = ai_extract_questions(text, uploaded_file.name)
                apostila_id = save_apostila(uploaded_file.name)
                save_questoes(apostila_id, questoes)
                st.success(f"Sucesso! {len(questoes)} questões adicionadas ao Hub.")
            except Exception as e:
                st.error(f"Erro ao processar: {e}")

    st.divider()
    st.subheader("Apostilas Cadastradas")
    df_apostilas = get_apostilas()
    if not df_apostilas.empty:
        st.table(df_apostilas)
    else:
        st.info("Nenhuma apostila cadastrada.")

elif menu == "📝 Fazer Simulado":
    st.title("📝 Simulado de Conhecimentos")
    df_apostilas = get_apostilas()
    
    if df_apostilas.empty:
        st.warning("Cadastre materiais primeiro.")
    else:
        lista_nomes = df_apostilas['nome'].tolist()
        escolha = st.selectbox("Selecione a apostila:", lista_nomes)
        apostila_id = df_apostilas[df_apostilas['nome'] == escolha]['id'].values[0]
        
        # --- NOVA OPÇÃO: QUANTIDADE DE QUESTÕES ---
        qtd_questoes = st.number_input("Quantas questões deseja no simulado?", min_value=1, value=10, step=1)
        
        if st.button("Iniciar Simulado"):
            all_questions = get_questoes(apostila_id)
            
            if not all_questions:
                st.error("Esta apostila não possui questões cadastradas.")
            else:
                # Embaralha as questões para ser um simulado real
                random.shuffle(all_questions)
                
                # Seleciona a quantidade pedida (ou o máximo disponível se for menor)
                final_count = min(len(all_questions), qtd_questoes)
                if final_count < qtd_questoes:
                    st.warning(f"A apostila possui apenas {final_count} questões. Usaremos todas elas.")
                
                st.session_state.questoes_simulado = all_questions[:final_count]
                st.session_state.respostas_usuario = {}
                st.rerun()

        if 'questoes_simulado' in st.session_state:
            with st.form("simulado_form"):
                for i, q in enumerate(st.session_state.questoes_simulado):
                    st.markdown(f"**Questão {i+1}**")
                    st.write(q['pergunta'])
                    resp = st.radio(f"Opção para Q{i+1}:", options=q['opcoes'].keys(), key=f"q_{i}")
                    st.session_state.respostas_usuario[i] = resp
                    st.write("---")
                
                submitted = st.form_submit_button("Finalizar e Ver Resultados")
                
                if submitted:
                    st.divider()
                    st.header("✅ Resultado do Simulado")
                    for i, q in enumerate(st.session_state.questoes_simulado):
                        user_ans = st.session_state.respostas_usuario.get(i, "Não respondida")
                        correct_ans = q['correta']
                        color = "green" if user_ans == correct_ans else "red"
                        st.markdown(f"**Questão {i+1}**")
                        st.markdown(f"Sua resposta: :{color}[{user_ans}] | Resposta correta: :green[{correct_ans}]")
                        st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                        st.write("---")
