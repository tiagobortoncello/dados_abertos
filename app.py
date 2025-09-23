import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import altair as alt

st.set_page_config(layout="wide")

# Configura a chave da API do Gemini de forma segura
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Chave da API do Gemini não encontrada nos segredos do Streamlit.")

# URL da API de Teste (Open Library API)
# Você pode usar esta URL para testar a funcionalidade completa do seu app
url = "https://openlibrary.org/search.json?q=python"

@st.cache_data(ttl=3600)
def carregar_dados_da_api():
    """Faz a chamada à API de Teste e retorna um DataFrame."""
    try:
        st.info("Buscando dados da Open Library API...")
        response = requests.get(url)
        response.raise_for_status() 
        dados = response.json()
        
        # A chave de dados nesta API é 'docs'
        df = pd.DataFrame(dados.get('docs', []))
        
        if not df.empty:
            # Seleciona algumas colunas relevantes para o assistente
            df = df[['title', 'first_publish_year', 'author_name', 'subject']]
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao carregar os dados da API: {e}. Verifique o link.")
        return pd.DataFrame()

# Carrega os dados da API
df_proposicoes = carregar_dados_da_api()

st.title("Assistente de Dados (Modo de Teste)")
st.subheader("Faça perguntas sobre os livros listados")

# O assistente só é exibido se os dados e a chave do Gemini estão ok
if not df_proposicoes.empty and genai.api_key:
    user_query = st.text_input("Sua pergunta:", placeholder="Ex: Qual o ano de publicação mais comum?")
    
    if user_query:
        st.info("Buscando a resposta...")
        
        # Converte o DataFrame para um formato de texto para o Gemini
        data_string = df_proposicoes.to_string(index=False)
        
        # Constrói o prompt (instrução)
        prompt = f"""
        Você é um assistente de dados sobre livros.
        Analise os dados fornecidos abaixo e responda à pergunta do usuário.

        Se a pergunta for sobre contagens ou anos, inclua um bloco de código Python com um gráfico para complementar a informação.

        Dados de livros:
        {data_string}

        Instruções para gráficos:
        - Use `altair`. O DataFrame se chama `df_proposicoes`.
        - Use a formatação: ```python ... ```
        - Exemplo:
          ```python
          chart = alt.Chart(df_proposicoes).mark_bar().encode(
              x=alt.X('first_publish_year:O', title='Ano de Publicação'),
              y=alt.Y('count():Q', title='Quantidade')
          ).properties(
              title='Livros por Ano de Publicação'
          )
          st.altair_chart(chart, use_container_width=True)
          ```

        Pergunta do usuário: {user_query}
        """
        
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Lógica para executar o código
            if "```python" in response_text:
                parts = response_text.split("```python")
                text_part = parts[0].strip()
                code_part = parts[1].split("```")[0].strip()
                
                if text_part: st.markdown(text_part)
                st.code(code_part, language='python')
                exec(code_part)
            else:
                st.markdown(response_text)
            
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")
            st.caption("Verifique se sua chave da API está correta ou se a pergunta é clara.")

else:
    st.warning("Dados não carregados. Não é possível usar o assistente.")
