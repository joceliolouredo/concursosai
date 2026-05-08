import streamlit as st
import google.generativeai as genai
import PyPDF2
import json
import sqlite3
import pandas as pd

# --- CONFIGURAÇÃO DE SEGURANÇA E IA ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("Erro: Chave de API não encontrada nos Secrets. Por favor, configure a GEMINI_API_KEY nas configurações do Streamlit Cloud.")

model = genai.GenerativeModel('gemini-1.5-flash')

# --- FUNÇÕES DO BANCO DE DADOS ---
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

# --- PROCESSAMENTO ---
def extract_text_from_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def ai_extract_questions(text, filename):
    prompt = f"""
    Você é um especialista em concursos. Analise o conteúdo da apostila '{filename}' e extraia ou crie questões de múltipla escolha baseadas rigorosamente no texto.
    Retorne EXCLUSIVAMENTE um JSON no formato de lista:
    [
      {{
        "pergunta": "Texto da pergunta",
        "opcoes": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
        "correta": "A",
        "justificativa": "Justificativa técnica e objetiva de por que a alternativa correta está certa, baseada no conteúdo."
      }}
    ]
    Conteúdo: {text[:30000]}
    """
    response = model.generate_content(prompt)
    json_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(json_text)

# --- INTERFACE ---
init_db()
st.set_page_config(page_title="Hub de Simulados IA", layout="wide", page_icon="📚")

st.sidebar.title("🚀 Menu Hub")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "📁 Gerenciar Apostilas", "📝 Fazer Simulado"])

if menu == "🏠 Home":
    st.title("📚 Hub de Simulados Inteligente")
    st.markdown("""
    Bem-vindo ao seu centro de estudos automatizado.
    
    **Como funciona:**
    1. Vá em **Gerenciar Apostilas** e suba seus PDFs.
    2. A IA lerá o conteúdo e criará um banco de questões automaticamente.
    3. Vá em **Fazer Simulado**, escolha a matéria e teste seus conhecimentos.
    4. Receba a resposta correta e a justificativa técnica imediata.
    """)
    st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", width=500)

elif menu == "📁 Gerenciar Apostilas":
    st.title("📁 Cadastro de Materiais")
    uploaded_file = st.file_uploader("Subir Nova Apostila (PDF)", type="pdf")
    
    if uploaded_file and st.button("Processar e Salvar no Hub"):
        with st.spinner("A IA está analisando o PDF e gerando questões..."):
            try:
                text = extract_text_from_pdf(uploaded_file)
                questoes = ai_extract_questions(text, uploaded_file.name)
                apostila_id = save_apostila(uploaded_file.name)
                save_questoes(apostila_id, questoes)
                st.success(f"Apostila '{uploaded_file.name}' cadastrada! {len(questoes)} questões adicionadas.")
            except Exception as e:
                st.error(f"Erro ao processar PDF: {e}")

    st.divider()
    st.subheader("Apostilas Cadastradas")
    df_apostilas = get_apostilas()
    if not df_apostilas.empty:
        st.table(df_apostilas)
    else:
        st.info("Nenhuma apostila cadastrada ainda.")

elif menu == "📝 Fazer Simulado":
    st.title("📝 Simulado de Conhecimentos")
    df_apostilas = get_apostilas()
    
    if df_apostilas.empty:
        st.warning("Nenhuma apostila cadastrada. Vá em 'Gerenciar Apostilas' primeiro.")
    else:
        lista_nomes = df_apostilas['nome'].tolist()
        escolha = st.selectbox("Selecione a apostila para o simulado:", lista_nomes)
        apostila_id = df_apostilas[df_apostilas['nome'] == escolha]['id'].values[0]
        
        if st.button("Iniciar Simulado"):
            st.session_state.questoes_simulado = get_questoes(apostila_id)
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
                
                submitted = st.form_submit_button("Finalizar e Ver Justificativas")
                
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
