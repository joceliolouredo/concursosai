import streamlit as st
from groq import Groq
import json
import sqlite3
import pandas as pd
import random
import plotly.express as px

# ==============================================================================
# 1. CONFIGURAÇÃO de SEGURANÇA E IA (GROQ)
# ==============================================================================
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("⚠️ Erro: Chave de API não encontrada nos Secrets do Streamlit Cloud.")

# ==============================================================================
# 2. SISTEMA de BANCO DE DADOS (MEMÓRIA DO HUB)
# ==============================================================================
def init_db():
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    
    # RESET DE TABELAS: Para evitar o erro "no column named dificuldade"
    # Isso garante que a estrutura do banco esteja sempre atualizada com as novas colunas
    try:
        c.execute('DROP TABLE IF EXISTS questoes')
        c.execute('DROP TABLE IF NOT EXISTS simulados')
    except:
        pass

    # Tabela de Simulados (Estrutura Atualizada)
    c.execute('CREATE TABLE IF NOT EXISTS simulados (id INTEGER PRIMARY KEY, concurso TEXT, dificuldade TEXT, data TEXT)')
    
    # Tabela de Questões (Estrutura Atualizada com Matéria)
    c.execute('''CREATE TABLE IF NOT EXISTS questoes 
                 (id INTEGER PRIMARY KEY, simulado_id INTEGER, materia TEXT, pergunta TEXT, 
                 opcoes TEXT, correta TEXT, justificativa TEXT)''')
    conn.commit()
    conn.close()

def save_simulado(concurso, dificuldade):
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    from datetime import datetime
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute('INSERT INTO simulados (concurso, dificuldade, data) VALUES (?, ?, ?)', (concurso, dificuldade, data_atual))
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
# 3. MOTOR de GERAÇÃO de QUESTÕES (IA GROQ)
# ==============================================================================
def ai_generate_questions(concurso, qtd_total, dificuldade):
    prompt = f"""
    Você é um consultor de editais e professor especialista em concursos.
    Sua tarefa é criar um simulado para o concurso: {concurso}, com um total de {qtd_total} questões.
    NÍVEL DE DIFICULDADE: {dificuldade}.
    
    Siga rigorosamente:
    1. Distribua as {qtd_total} questões proporcionalmente entre as matérias mais cobradas deste concurso.
    2. Se o nível for 'Difícil', foque em pegadinhas e detalhes técnicos. Se for 'Fácil', foque em conceitos base.
    3. Cada questão deve ter exatamente 4 opções (A, B, C, D) completas.
    4. Retorne EXCLUSIVAMENTE um JSON no formato de lista.
    
    Modelo do JSON:
    {{
      "questoes": [
        {{
          "materia": "Nome da Matéria",
          "pergunta": "Texto da pergunta",
          "opcoes": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
          "correta": "A",
          "justificativa": "Explicação técnica curta e objetiva."
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
# 4. INTERFACE DO USUÁRIO (STREAMLIT)
# ==============================================================================
init_db()
st.set_page_config(page_title="Coach AI Simulado", layout="wide", page_icon="🎯")

st.sidebar.title("🚀 Menu Hub Coach")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "🎯 Gerar Simulado", "📜 Histórico"])

if menu == "🏠 Home":
    st.title("🎯 Coach AI Simulado")
    st.markdown("""
    **O simulador mais inteligente para sua aprovação.**
    
    A IA analisa o edital, distribui as matérias e avalia seu desempenho com gráficos precisos.
    
    **Como funciona:**
    1. Escolha o concurso e a quantidade de questões.
    2. Selecione a dificuldade (Fácil, Média ou Difícil).
    3. Responda ao simulado.
    4. Veja seu gráfico de acertos e receba dicas de onde melhorar.
    """)
    st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", width=500)

elif menu == "🎯 Gerar Simulado":
    st.title("🎯 Novo Simulado Personalizado")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        concurso = st.text_input("Nome do Concurso", placeholder="Ex: Banco do Brasil, PF...")
    with col2:
        dificuldade = st.selectbox("Nível de Dificuldade", ["Fácil", "Média", "Difícil"])
    with col3:
        qtd_total = st.number_input("Total de Questões", min_value=5, max_value=100, value=10)
    
    if st.button("Gerar Simulado ⚡"):
        if not concurso:
            st.error("Digite o nome do concurso.")
        else:
            with st.spinner("IA analisando edital e gerando questões..."):
                try:
                    questoes = ai_generate_questions(concurso, qtd_total, dificuldade)
                    if questoes:
                        simulado_id = save_simulado(concurso, dificuldade)
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
            # ==========================================================================
            # ANÁLISE DE RESULTADOS E GRÁFICOS
            # ==========================================================================
            st.header("📊 Análise de Desempenho")
            
            stats = {} 
            for i, q in enumerate(questoes):
                materia = q['materia']
                if materia not in stats:
                    stats[materia] = {"corretas": 0, "total": 0}
                stats[materia]["total"] += 1
                if st.session_state.respostas_usuario.get(i) == q['correta']:
                    stats[materia]["corretas"] += 1
            
            df_stats = pd.DataFrame([
                {"Matéria": k, "Aproveitamento (%)": (v["corretas"]/v["total"])*100} 
                for k, v in stats.items()
            ])
            
            fig = px.bar(df_stats, x="Matéria", y="Aproveitamento (%)", 
                         color="Aproveitamento (%)", color_continuous_scale="RdYlGn",
                         title="Seu Aproveitamento por Matéria")
            st.plotly_chart(fig)
            
            materias_fracas = [m for m, v in stats.items() if (v["corretas"]/v["total"]) < 0.7]
            if materias_fracas:
                st.warning(f"🚨 **Atenção:** Você precisa de reforço em: {', '.join(materias_fracas)}")
                if st.button("Gerar Questões de Reforço Agora! 📚"):
                    st.info("A IA está criando questões focadas nos seus erros...")
                    # Lógica de reforço simples: gera 5 questões das matérias fracas
                    ref_materia = " e ".join(materias_fracas)
                    questoes_ref = ai_generate_questions(f"Reforço {concurso}", 5, "Média")
                    # Exibimos as questões de reforço logo abaixo
                    for qr in questoes_ref:
                        st.markdown(f"**{qr['materia']}**: {qr['pergunta']}")
                        st.write(f"Correta: {qr['correta']} | {qr['justificativa']}")
                        st.write("---")
            else:
                st.success("🌟 Desempenho excelente em todas as matérias!")

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
                st.session_state.simulado_concluido = False
                st.rerun()

elif menu == "📜 Histórico":
    st.title("📜 Meus Simulados")
    df = get_simulados()
    if df.empty:
        st.info("Nenhum simulado registrado.")
    else:
        opcoes = df['id'].tolist()
        nomes = [f"ID {id} - {row['concurso']} ({row['dificuldade']}) - {row['data']}" for id, row in zip(df['id'], df.to_dict('records'))]
        escolha = st.selectbox("Escolha um simulado para revisar:", opcoes, format_func=lambda x: nomes[df[df['id']==x].index[0]])
        if st.button("Revisar Questões"):
            questoes = get_questoes(escolha)
            for i, q in enumerate(questoes):
                st.markdown(f"**{q['materia']} | Questão {i+1}**")
                st.write(q['pergunta'])
                st.markdown(f"**Resposta Correta:** :green[{q['correta']}]")
                st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                st.write("---")
