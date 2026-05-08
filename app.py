import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json
import pandas as pd
import random
import plotly.express as px
import plotly.graph_objects as go

# ==============================================================================
# 1. CONEXÕES DO HUB (IA E BANCO DE DADOS NUVEM)
# ==============================================================================
try:
    # Conexão Groq
    client_groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
    # Conexão Supabase
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("⚠️ Erro de conexão com o Hub. Verifique as chaves nos Secrets.")

# ==============================================================================
# 2. LÓGICA DE DADOS (SUPABASE)
# ==============================================================================
def save_simulado(concurso, cargo, dificuldade):
    from datetime import datetime
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    data = {"concurso": concurso, "cargo": cargo, "dificuldade": dificuldade, "data": data_atual}
    response = supabase.table("simulados").insert(data).execute()
    return response.data[0]['id']

def save_questoes(simulado_id, questoes):
    formatted = []
    for q in questoes:
        formatted.append({
            "simulado_id": simulado_id,
            "materia": q.get('materia', 'Geral'),
            "pergunta": q['pergunta'],
            "opcoes": json.dumps(q['opcoes']),
            "correta": q['correta'],
            "justificativa": q['justificativa']
        })
    supabase.table("questoes").insert(formatted).execute()

def get_simulados():
    response = supabase.table("simulados").select("*").order("id", ascending=False).execute()
    return pd.DataFrame(response.data)

def get_questoes(simulado_id):
    response = supabase.table("questoes").select("*").eq("simulado_id", simulado_id).execute()
    return [{"id": r['id'], "materia": r['materia'], "pergunta": r['pergunta'], "opcoes": json.loads(r['opcoes']), "correta": r['correta'], "justificativa": r['justificativa']} for r in response.data]

# ==============================================================================
# 3. MOTOR de GERAÇÃO (IA GROQ)
# ==============================================================================
def ai_generate_questions(concurso, cargo, qtd_total, dificuldade):
    prompt = f"""
    Você é o Coach AI, especialista em concursos. 
    Crie um simulado para: {concurso}, Cargo: {cargo}.
    QUANTIDADE: {qtd_total} questões. NÍVEL: {dificuldade}.
    
    Regras: 
    1. Distribua proporcionalmente por matéria.
    2. Alternativas completas (A, B, C, D).
    3. Retorne EXCLUSIVAMENTE um JSON de lista.
    
    Modelo: {{"questoes": [{{ "materia": "...", "pergunta": "...", "opcoes": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correta": "A", "justificativa": "..." }}]}}
    """
    chat_completion = client_groq.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile", 
        response_format={"type": "json_object"} 
    )
    res = json.loads(chat_completion.choices[0].message.content)
    return res.get("questoes", [])

# ==============================================================================
# 4. INTERFACE DO HUB (COACH AI)
# ==============================================================================
st.set_page_config(page_title="Coach AI Hub", layout="wide", page_icon="🎯")

# CSS Tema Dark
st.markdown("""
    <style>
    .stButton>button { background-color: #00FFB2; color: black; font-weight: bold; border-radius: 10px; }
    .stTextInput>div>div>input { background-color: #262730 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.title("🚀 Coach AI Hub")
menu = st.sidebar.radio("Navegação", ["🏠 Home", "🎯 Gerar Simulado", "📜 Histórico"])

if menu == "🏠 Home":
    st.title("🎯 Coach AI Hub")
    st.markdown("Sua plataforma de elite para aprovação. Dados permanentes, análise inteligente e reforço focado.")
    st.image("https://img.freepik.com/free-vector/online-library-concept-illustration_114360-3911.jpg", width=500)

elif menu == "🎯 Gerar Simulado":
    st.title("🎯 Novo Simulado")
    col1, col2 = st.columns(2)
    with col1:
        concurso = st.text_input("Concurso", placeholder="Ex: Banco do Brasil")
        cargo = st.text_input("Cargo", placeholder="Ex: Escriturário")
    with col2:
        dificuldade = st.selectbox("Dificuldade", ["Fácil", "Média", "Difícil"])
        qtd_total = st.number_input("Questões", min_value=5, max_value=100, value=10)
    
    if st.button("Lançar Simulado ⚡"):
        if not concurso or not cargo:
            st.error("Preencha Concurso e Cargo.")
        else:
            with st.spinner("Coach AI processando edital..."):
                try:
                    questoes = ai_generate_questions(concurso, cargo, qtd_total, dificuldade)
                    if questoes:
                        sim_id = save_simulado(concurso, cargo, dificuldade)
                        save_questoes(sim_id, questoes)
                        st.session_state.simulado_atual_id = sim_id
                        st.session_state.respostas_usuario = {}
                        st.session_state.simulado_concluido = False
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    if 'simulado_atual_id' in st.session_state:
        sim_id = st.session_state.simulado_atual_id
        questoes = get_questoes(sim_id)
        
        if not st.session_state.get('simulado_concluido', False):
            with st.form("sim_form"):
                for i, q in enumerate(questoes):
                    st.markdown(f"**{q['materia']}** | Q{i+1}")
                    st.write(q['pergunta'])
                    opcoes = [f"{k}) {v}" for k, v in q['opcoes'].items()]
                    resp = st.radio(f"Escolha:", options=opcoes, key=f"q_{i}")
                    st.session_state.respostas_usuario[i] = resp[0]
                    st.write("---")
                if st.form_submit_button("Finalizar"):
                    st.session_state.simulado_concluido = True
                    st.rerun()
        else:
            st.header("📊 Dashboard Coach AI")
            stats = {} 
            for i, q in enumerate(questoes):
                m = q['materia']
                if m not in stats: stats[m] = {"c": 0, "t": 0}
                stats[m]["t"] += 1
                if st.session_state.respostas_s_usuario.get(i) == q['correta']: stats[m]["c"] += 1
            
            df_stats = pd.DataFrame([{"Matéria": k, "Aproveitamento": (v["c"]/v["t"])*100} for k, v in stats.items()])
            fig = go.Figure(go.Bar(x=df_stats['Matéria'], y=df_stats['Aproveitamento'], marker_color="#00FFB2", text=df_stats['Aproveitamento'].apply(lambda x: f"{x:.1f}%"), textposition='outside'))
            fig.add_hline(y=70, line_dash="dash", line_color="gray")
            fig.update_layout(template="plotly_dark", yaxis=dict(range=[0, 110]))
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button("Sair"):
                st.session_state.simulado_atual_id = None
                st.session_state.simulado_concluido = False
                st.rerun()

elif menu == "📜 Histórico":
    st.title("📜 Meus Simulados")
    df = get_simulados()
    if df.empty:
        st.info("Nenhum registro.")
    else:
        opcoes = df['id'].tolist()
        nomes = [f"ID {id} - {row['concurso']} ({row['cargo']}) - {row['data']}" for id, row in zip(df['id'], df.to_dict('records'))]
        escolha = st.selectbox("Revisar:", opcoes, format_func=lambda x: nomes[df[df['id']==x].index[0]])
        if st.button("Abrir"):
            questoes = get_questoes(escolha)
            for q in questoes:
                st.markdown(f"**{q['materia']}**: {q['pergunta']}")
                st.markdown(f"Correta: :green[{q['correta']}] | {q['justificativa']}")
                st.write("---")
