import streamlit as st
import google.generativeai as genai
import PyPDF2
import json
import sqlite3
import pandas as pd

# ==============================================================================
# 1. CONFIGURAÇÃO DE SEGURANÇA E IA
# ==============================================================================
try:
    # A chave GEMINI_API_KEY deve ser configurada nos "Secrets" do Streamlit Cloud
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("⚠️ Erro: Chave de API não encontrada. Vá em 'Advanced Settings' -> 'Secrets' e adicione: GEMINI_API_KEY = 'SUA_CHAVE'")

model = genai.GenerativeModel('gemini-1.5-flash')

# ==============================================================================
# 2. SISTEMA DE BANCO DE DADOS (HUB)
# ==============================================================================
def init_db():
    """Cria as tabelas do banco de dados se elas não existirem"""
    conn = sqlite3.connect('hub_concursos.db')
    c = conn.cursor()
    # Tabela para armazenar as apostilas subidas
    c.execute('CREATE TABLE IF NOT EXISTS apostilas (id INTEGER PRIMARY KEY, nome TEXT)')
    # Tabela para armazenar as questões vinculadas a cada apostila
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
        # Salvamos as opções como uma string JSON para facilitar o armazenamento
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
# 3. PROCESSAMENTO DE DOCUMENTOS E IA
# ==============================================================================
def extract_text_from_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def ai_extract_questions(text, filename):
    """Usa a IA para ler o PDF e gerar questões estruturadas"""
    prompt = f"""
    Você é um professor especialista em concursos. Analise o conteúdo da apostila '{filename}' e extraia ou crie questões de múltipla escolha.
    
    REGRAS RÍGIDAS:
    1. Retorne EXCLUSIVAMENTE um formato JSON de lista.
    2. A justificativa deve ser curta, técnica e objetiva, focando apenas em POR QUE a alternativa correta está certa.
    3. NÃO mencione erros do aluno ou frases como 'você errou'.
    
    Modelo do JSON:
    [
      {{
        "pergunta": "Texto da pergunta",
        "opcoes": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
        "correta": "A",
        "justificativa": "Justificativa técnica e objetiva baseada no texto."
      }}
    ]
    
    Conteúdo: {text[:30000]}
    """
    response = model.generate_content(prompt)
    # Limpeza para remover marcações de Markdown ```json ... ```
    json_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(json_text)

# ==============================================================================
# 4. INTERFACE DO USUÁRIO (STREAMLIT UI)
# ==============================================================================
init_db()
st.set_page_config(page_title="Hub de Simulados IA", layout="wide", page_icon="📚")

# Menu Lateral
st.sidebar.title("🚀 Menu Hub")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "📁 Gerenciar Apostilas", "📝 Fazer Simulado"])

if menu == "🏠 Home":
    st.title("📚 Hub de Simulados Inteligente")
    st.markdown("""
    Bem-vindo ao seu centro de estudos automatizado.
    
    **Como utilizar o sistema:**
    1. Vá em **Gerenciar Apostilas** e suba seus arquivos PDF.
    2. A IA processará o conteúdo e criará questões automaticamente.
    3. Vá em **Fazer Simulado**, escolha a matéria e responda.
    4. Ao final, você verá a resposta correta com a justificativa técnica.
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
                st.success(f"Apostila '{uploaded_file.name}' cadastrada com sucesso! {len(questoes)} questões geradas.")
            except Exception as e:
                st.error(f"Erro ao processar PDF: {e}")

    st.divider()
    st.subheader("Apostilas já cadastradas")
    df_apostilas = get_apostilas()
    if not df_apostilas.empty:
        st.table(df_apostilas)
    else:
        st.info("Nenhuma apostila cadastrada ainda.")

elif menu == "📝 Fazer Simulado":
    st.title("📝 Simulado de Conhecimentos")
    df_apostilas = get_apostilas()
    
    if df_apostilas.empty:
        st.warning("Nenhuma apostila cadastrada. Por favor, cadastre materiais em 'Gerenciar Apostilas'.")
    else:
        lista_nomes = df_apostilas['nome'].tolist()
        escolha = st.selectbox("Selecione a apostila para o simulado:", lista_nomes)
        apostila_id = df_apostilas[df_apostilas['nome'] == escolha]['id'].values[0]
        
        if st.button("Iniciar Simulado"):
            st.session_state.questoes_simulado = get_questoes(apostila_id)
            st.session_state.respostas_usuario = {}
            st.rerun()

        if 'questoes_simulado' in st.session_state:
            # Usamos st.form para que a página não recarregue a cada opção marcada
            with st.form("simulado_form"):
                for i, q in enumerate(st.session_state.questoes_simulado):
                    st.markdown(f"**Questão {i+1}**")
                    st.write(q['pergunta'])
                    resp = st.radio(f"Selecione a opção para a Q{i+1}:", options=q['opcoes'].keys(), key=f"q_{i}")
                    st.session_state.respostas_usuario[i] = resp
                    st.write("---")
                
                submitted = st.form_submit_button("Finalizar e Ver Resultados")
                
                if submitted:
                    st.divider()
                    st.header("✅ Resultado do Simulado")
                    
                    for i, q in enumerate(st.session_state.questoes_simulado):
                        user_ans = st.session_state.respostas_usuario.get(i, "Não respondida")
                        correct_ans = q['correta']
                        
                        # Cor verde se acertou, vermelha se errou
                        color = "green" if user_ans == correct_ans else "red"
                        
                        st.markdown(f"**Questão {i+1}**")
                        st.markdown(f"Sua resposta: :{color}[{user_ans}] | Resposta correta: :green[{correct_ans}]")
                        st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                        st.write("---")
