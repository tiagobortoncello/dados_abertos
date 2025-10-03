import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import json 
import altair as alt 
import datetime 

st.set_page_config(layout="wide")

# --- CONFIGURAÇÕES E CONSTANTES ---

CHAVE_GEMINI_CONFIGURADA = False 

if "GEMINI_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        CHAVE_GEMINI_CONFIGURADA = True
    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini: {e}")
else:
    st.warning("Chave da API do Gemini não encontrada nos segredos do Streamlit.")

url_api = "https://dadosabertos.almg.gov.br/api/v2/proposicoes/pesquisa/avancada"

# CORREÇÃO FINAL: Mapeamento de Parâmetros com os códigos curtos e 
# instruindo o Gemini a usar códigos numéricos (exemplo '10' para PL)
PARAMETROS_ALMG = {
    'tp': 'CÓDIGO NUMÉRICO do Tipo de Proposição (Ex: 10 para PL, 100 para PEC). O Gemini deve gerar o código numérico.',
    'expr': 'Palavra-chave ou Expressão para pesquisa na Ementa',
    'p': 'Número da página (para paginação)',
    'sit': 'Código NUMÉRICO da Situação/Status da Proposição (Ex: 1=Em Tramitação)', 
    'ord': 'Código NUMÉRICO de Ordenação (Ex: 1=Mais Recente)',
    'dataInicial': 'Data de apresentação inicial (formato YYYY-MM-DD)',
    'dataFinal': 'Data de apresentação final (formato YYYY-MM-DD)',
    'itensPorPagina': 'Limite de resultados (padrão 100, máximo 500)'
}

# --- FUNÇÕES ---

def gerar_parametros_com_gemini(pergunta_usuario, parametros_validos):
    """Usa o Gemini para converter a pergunta em um JSON de parâmetros da API."""
    
    if not CHAVE_GEMINI_CONFIGURADA:
        return {}
        
    lista_de_parametros = "\n".join([f"- {k} ({v})" for k, v in parametros_validos.items()])

    prompt = f"""
    Sua tarefa é converter a pergunta do usuário em um **objeto JSON** contendo os parâmetros de consulta válidos para a API de Proposições da ALMG. Use os **códigos curtos** fornecidos.

    Parâmetros Válidos:
    {lista_de_parametros}
    
    Instruções:
    1. Responda **APENAS** com o objeto JSON. Não inclua texto, explicação ou formatação Markdown (ex: ```json).
    2. O JSON deve conter apenas os parâmetros que foram explicitamente pedidos ou sugeridos na pergunta.
    3. Para o parâmetro 'tp' (Tipo de Proposição), converta a sigla (PL, PEC, REQ) para o **código numérico** mais provável (Ex: PL -> 10, PEC -> 100).
    4. Se o usuário perguntar por algo que a API não pode filtrar, retorne um JSON vazio: {{}}.

    Pergunta do Usuário: "{pergunta_usuario}"
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        response = model.generate_content(
            prompt, 
            stream=False     
        )
        
        return json.loads(response.text.strip())
        
    except json.JSONDecodeError:
        st.error(f"Erro: O Gemini não retornou um JSON válido. Resposta recebida: {response.text}")
        return {}
    except Exception as e:
        st.error(f"Erro ao gerar JSON de parâmetros: {e}. Verifique o log do Streamlit.")
        return {}


def carregar_dados_da_api_dinamico(url, params=None):
    """Faz a chamada à API com os parâmetros de filtro e retorna um DataFrame."""
    
    if params is None:
        params = {}
    
    if 'itensPorPagina' not in params:
        params['itensPorPagina'] = 100 
    
    # 1. CONVERSÃO: Tratar o parâmetro 'ano' (se gerado pelo Gemini)
    if 'ano' in params:
        ano = params.pop('ano')
        # A API pode exigir filtros de data
        params['dataInicial'] = f'{ano}-01-01'
        params['dataFinal'] = f'{ano}-12-31'
        st.info(f"Convertendo ano={ano} para o intervalo: {params['dataInicial']} a {params['dataFinal']}")


    # 2. REMOÇÃO DO FILTRO PADRÃO: Removido o bloco de código que adicionava filtros rígidos.
    # Se o Gemini não gerou filtros (ex: pergunta sobre a quantidade), a chamada será feita
    # com o que foi gerado, e se falhar, o usuário será alertado.
    
    if not params:
        st.warning("Nenhum filtro de pesquisa foi gerado pelo Gemini. A API será chamada sem restrições (o que pode causar Erro 500).")

    try:
        st.info(f"Buscando dados na API da ALMG com filtros: {params}")
        
        response = requests.get(url, params=params) 
        
        response.raise_for_status() 
        dados = response.json()
        
        df = pd.DataFrame(dados.get('list', []))
        
        if not df.empty:
             # Manter nomes de colunas em português
             df = df[['siglaTipo', 'numero', 'ano', 'ementa', 'apresentacao']]
        return df
        
    except requests.exceptions.HTTPError as e:
        # Erro 400 (Bad Request) ou 500 (Server Error)
        st.error(f"Erro no servidor da API: {e}. Isso indica que a API rejeitou os filtros. Verifique se o Gemini gerou os códigos numéricos corretos (tp, sit, ord).")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a API: {e}. Verifique sua conexão com a internet.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar os dados da API: {e}. Verifique a estrutura JSON da resposta.")
        return pd.DataFrame()


# --- LÓGICA PRINCIPAL DA APLICAÇÃO ---

st.title("Assistente de Pesquisa e Análise de Proposições da ALMG (Beta)")
st.subheader("Use linguagem natural para filtrar e analisar os dados.")

user_query = st.text_input("Sua pergunta ou filtro:", placeholder="Ex: Quero as proposições PL de 2023 com a palavra 'saúde' e depois me diga o tipo mais comum")

if user_query:
    st.markdown("---")
    
    if not CHAVE_GEMINI_CONFIGURADA: 
        st.error("Por favor, configure sua chave da API do Gemini nos segredos do Streamlit para continuar com a geração de filtros.")
    
    else:
        # 1. GERA OS PARÂMETROS COM O GEMINI
        api_params = gerar_parametros_com_gemini(user_query, PARAMETROS_ALMG)
        
        # 2. CARREGA OS DADOS COM OS PARÂMETROS (DINAMICAMENTE)
        df_proposicoes = carregar_dados_da_api_dinamico(url_api, params=api_params)

        # 3. ANALISA OS DADOS FILTRADOS
        if not df_proposicoes.empty:
            
            st.success(f"Foram carregados **{len(df_proposicoes)}** proposições com os filtros aplicados.")
            
            st.info("Passo 3: Analisando os dados filtrados e gerando a resposta e o gráfico...")
            
            # Sua lógica de análise (segundo prompt do Gemini) deve ser reinserida aqui.
            
            st.dataframe(df_proposicoes)
        else:
            st.warning("Nenhuma proposição foi encontrada com os filtros gerados. Tente refinar a sua pergunta.")
