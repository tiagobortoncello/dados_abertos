import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai

st.set_page_config(layout="wide")

# Configura a chave da API do Gemini de forma segura
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Chave da API do Gemini não encontrada nos segredos do Streamlit. Verifique a configuração.")

# URL da API da ALMG para Proposições
url = "https://dadosabertos.almg.gov.br/api/v2/proposicoes/pesquisa/avancada"

@st.cache_data(ttl=3600)
def carregar_dados_da_api():
    """Faz a chamada à API da ALMG e retorna um DataFrame do pandas."""
    try:
        response = requests.get(url, params={"formato": "json"})
        response.raise_for_status() 
        dados = response.json()
        df = pd.DataFrame(dados.get('list', []))
        if not df.empty:
            df = df[['siglaTipo', 'numero', 'ano', 'ementa', 'apresentacao']]
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao carregar os dados da API: {e}")
        return pd.DataFrame()

# Carrega os dados da API
df_proposicoes = carregar_dados_da_api()

# Título e barra de entrada
st.title("Assistente de Dados da ALMG (Beta)")
st.subheader("Faça uma pergunta sobre as proposições em tramitação")

# Verifica se os dados foram carregados antes de continuar
if not df_proposicoes.empty and genai.api_key:
    user_query = st.text_input("Sua pergunta:", placeholder="Ex: Quantos projetos de lei estão em tramitação?")
    
    if user_query:
        st.info("Buscando a resposta com a ajuda do Gemini...")
        
        # Converte o DataFrame para um formato de texto que o Gemini pode processar
        # Usamos to_string() para enviar os dados como uma tabela formatada em texto
        data_string = df_proposicoes.to_string(index=False)
        
        # Constrói o prompt (instrução) para o modelo Gemini
        prompt = f"""
        Você é um assistente de dados da Assembleia Legislativa de Minas Gerais. Sua função é analisar os dados fornecidos abaixo e responder à pergunta do usuário.
        
        Dados de proposições:
        {data_string}
        
        Pergunta do usuário: {user_query}
        
        Responda à pergunta do usuário com base apenas nos dados fornecidos. Se a resposta não puder ser encontrada nos dados, diga que a informação não está disponível.
        """
        
        try:
            # Envia a instrução e os dados para o modelo Gemini
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            
            # Exibe a resposta formatada
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Ocorreu um erro ao processar a resposta do Gemini: {e}")
            st.caption("Verifique se a sua chave da API está correta e se o serviço está ativo.")

else:
    st.warning("Dados não carregados. Não é possível usar o assistente de dados.")
