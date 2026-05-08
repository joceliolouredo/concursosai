import streamlit as st
from groq import Groq
import json
import sqlite3
import pandas as pd
import random
import plotly.express as px # Para os gráficos de desempenho

# ==============================================================================
# 1. CONFIGURAÇÃO DE SEGURANÇA E IA (GROQ)
# ==============================================================================
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("⚠️ Erro: Chave de API não encontrada nos Secrets.")

# ==============================================================================
# 2. SISTEMA DE BANCO DE DADOS
# ==============================================================================
def init_db():
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS simulados (id INTEGER PRIMARY KEY, concurso TEXT, dificuldade TEXT, data TEXT)')
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

def get_questoes(simulado_id):
    conn = sqlite3.connect('hub_simulados.db')
    c = conn.cursor()
    c.execute('SELECT * FROM questoes WHERE simulado_id = ?', (simulado_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "materia": r[2], "pergunta": r[3], "opcoes": json.loads(r[4]), "correta": r[5], "justificativa": r[6]} for r in rows]

# ==============================================================================
# 3. MOTOR de GERAÇÃO (GROQ)
# ==============================================================================
def ai_generate_questions(concurso, qtd_total, dificuldade):
    prompt = f"""
    Você é um professor especialista em concursos. 
    Crie um simulado para o concurso: {concurso}, com {qtd_total} questões.
    NÍVEL DE DIFICULDADE: {dificuldade}.
    
    Siga estas regras:
    1. Distribua as questões proporcionalmente entre as matérias mais cobradas deste concurso.
    2. Se o nível for 'Difícil', foque em pegadinhas, jurisprudência e detalhes técnicos.
    3. Se for 'Fácil', foque em conceitos fundamentais e letra da lei.
    4. Retorne EXCLUSIVAMENTE um JSON de lista.
    
    Modelo do JSON:
    {{
      "questoes": [
        {{
          "materia": "Nome da Matéria",
          "pergunta": "Texto da pergunta",
          "opcoes": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
          "correta": "A",
          "justificativa": "Justificativa técnica curta."
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
st.set_page_config(page_title="Coach AI Simulado", layout="wide", page_icon="🎯")

st.sidebar.title("🚀 Menu Hub Coach")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "🎯 Gerar Simulado", "📜 Histórico"])

if menu == "🏠 Home":
    st.title("🎯 Coach AI Simulado")
    st.markdown(" la IA que não apenas testa, mas analisa onde você precisa melhorar.")
    st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", width=500)

elif menu == "🎯 Gerar Simulado":
    st.title("🎯 Novo Simulado Personalizado")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        concurso = st.text_input("Nome do Concurso", placeholder="Ex: PF, Banco do Brasil...")
    with col2:
        dificuldade = st.selectbox("Nível de Dificuldade", ["Fácil", "Média", "Difícil"])
    with col3:
        qtd_total = st.number_input("Total de Questões", min_value=5, max_value=100, value=10)
    
    if st.button("Gerar Simulado ⚡"):
        if not concurso:
            st.error("Digite o nome do concurso.")
        else:
            with st.spinner("A IA está montando seu edital..."):
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
            
            stats = {} # Dicionário para contar acertos por matéria
            
            for i, q in enumerate(questoes):
                materia = q['materia']
                if materia not in stats:
                    stats[materia] = {"corretas": 0, "total": 0}
                
                stats[materia]["total"] += 1
                if st.session_state.respostas_usuario.get(i) == q['correta']:
                    stats[materia]["corretas"] += 1
            
            # Transformando em DataFrame para o gráfico
            df_stats = pd.DataFrame([
                {"Matéria": k, "Aproveitamento (%)": (v["corretas"]/v["total"])*100} 
                for k, v in stats.items()
            ])
            
            # GRÁFICO DE BARRAS
            fig = px.bar(df_stats, x="Matéria", y="Aproveitamento (%)", 
                         color="Aproveitamento (%)", 
                         color_continuous_scale="RdYlGn",
                         title="Desempenho por Matéria")
            st.plotly_chart(fig)
            
            # Identificar onde melhorar
            materias_fracas = [m for m, v in stats.items() if (v["corretas"]/v["total"]) < 0.7]
            
            if materias_fracas:
                st.warning(f"🚨 **Atenção:** Você precisa de reforço em: {', '.join(materias_fracas)}")
                if st.button("Gerar Questões de Reforço agora! 📚"):
                    st.info("A IA está criando questões focadas apenas nos seus erros...")
                    # Aqui ele gera um novo simulado focado nas matérias fracas
                    ref_concurso = f"Reforço {concurso}"
                    ref_materia = " e ".join(materias_fracas)
                    # Chamamos a IA novamente para reforço
                    questoes_ref = ai_generate_questions(ref_materia, 5, "Média")
                    st.write("### Questões de Reforço Sugeridas:")
                    for qr in questoes: # Simplificado para exemplo, poderia salvar no banco
                         st.write(f"**{qr['materia']}**: {qr['pergunta']}")
            else:
                st.success("🌟 Parabéns! Você teve um desempenho excelente em todas as matérias!")

            st.divider()
            st.subheader("Certo/Errado e Justificativas")
            for i, q in enumerate(questoes):
                user_ans = st.session_state.respostas_usuario.get(i, "N/A")
                correct = q['correta']
                color = "green" if user_ans == correct else "red"
                st.markdown(f"**{q['materia']} | Q{i+1}**")
                st.markdown(f"Sua resposta: :{color}[{user_ans}] | Correta: :green[{correct}]")
                st.markdown(f"**✅ Justificativa:** {q['justificativa']}")
                st.write("---")
            
            if st.button("Fazer outro simulado"):
                st.session_state.simulado_atual_id = None
                st.session_state.simulado_concluido = False
                st.rerun()

elif menu == "📜 Histórico":
    st.title("📜 Meus Simulados")
    # ... (mesmo código do histórico anterior)
