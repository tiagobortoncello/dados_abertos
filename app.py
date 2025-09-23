import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import altair as alt

st.set_page_config(layout="wide")

# Configura a chave da API do Gemini de forma segura
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"Erro na configuração da API do Gemini: {e}")
    st.info("Por favor, adicione sua chave de API nas configurações do aplicativo no Streamlit Cloud.")

# URL da API de Teste (Open Library API)
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
            # Lista de colunas que queremos. O código lidará com colunas ausentes.
            colunas_desejadas = ['title', 'first_publish_year', 'author_name', 'subject']
            
            # Filtra as colunas que realmente existem no DataFrame
            colunas_existentes = [col for col in colunas_desejadas if col in df.columns]
            
            # Reorganiza o DataFrame com apenas as colunas existentes
            df = df[colunas_existentes]
            
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao carregar os dados da API: {e}. Verifique o link.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar os dados da API: {e}.")
        return pd.DataFrame()

# Carrega os dados da API
df_proposicoes = carregar_dados_da_api()

st.title("Assistente de Dados (Modo de Teste)")
st.subheader("Faça perguntas sobre os livros listados")

# O assistente só é exibido se os dados e a chave do Gemini estão ok
if not df_proposicoes.empty and genai.api_key:
    user_query = st.text_input("Sua pergunta:", placeholder="Ex: Qual o ano de publicação mais comum?")
    
    if user_query:
        st.info("Buscando a resposta e gerando o resultado...")
        
        data_string = df_proposicoes.to_string(index=False)
        
        prompt = f"""
        Você é um assistente de dados sobre livros.
        Analise os dados fornecidos abaixo e responda à pergunta do usuário.

        Se a pergunta for sobre contagens ou anos, inclua um bloco de código Python com um gráfico para complementar a informação.

        Dados de livros:
        {data_string}

        Instruções para gráficos:
        - Use a biblioteca `altair`. O DataFrame se chama `df_proposicoes`.
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
            
            if "```python" in response_text:
                parts = response_text.split("```python")
                text_part = parts[0].strip()
                code_part = parts[1].split("```")[0].strip()
                
                if text_part:
                    st.markdown(text_part)

                st.code(code_part, language='python')
                exec(code_part)
            else:
                st.markdown(response_text)
            
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")
            st.caption("Verifique se sua chave da API está correta ou se a pergunta é clara.")

else:
    st.warning("Dados não carregados. Não é possível usar o assistente.")
