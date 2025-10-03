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

# CORREÇÃO CRÍTICA: Mapeamento de Parâmetros com os códigos curtos da URL de exemplo
PARAMETROS_ALMG = {
    'tp': 'Código do Tipo de Proposição (Ex: PL, PEC, REQ) - O código exato é gerado pelo Gemini', # siglaTipo
    'expr': 'Palavra-chave ou Expressão para pesquisa na Ementa', # palavraChave
    'p': 'Número da página (para paginação)', # pagina
    'sit': 'Código da Situação/Status da Proposição (Ex: 1=Em Tramitação)', 
    'ord': 'Código de Ordenação (Ex: 1=Mais Recente)',
    'dataInicial': 'Data de apresentação inicial (formato YYYY-MM-DD)',
    'dataFinal': 'Data de apresentação final (formato YYYY-MM-DD)',
    'itensPorPagina': 'Limite de resultados (padrão 100, máximo 500)'
    # Remoção de 'ano' daqui para forçar o Gemini a usar datas ou o 'ano' será convertido internamente
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
    3. Para o parâmetro 'tp' (Tipo de Proposição), converta a sigla (PL, PEC) para a sigla, não para um código numérico. O servidor da ALMG deve aceitar a sigla no lugar do código.
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
        # Formato YYYY-MM-DD é o padrão para a API
        params['dataInicial'] = f'{ano}-01-01'
        params['dataFinal'] = f'{ano}-12-31'
        st.info(f"Convertendo ano={ano} para o intervalo: {params['dataInicial']} a {params['dataFinal']}")


    # 2. SOLUÇÃO DO ERRO 500: Garante que haja um filtro de pesquisa restritivo
    
    # Filtros de restrição (usando os códigos curtos)
    filtros_restritivos = ['dataInicial', 'dataFinal', 'expr', 'tp', 'sit']
    
    # Verifica se a consulta não tem NENHUM filtro de restrição de período ou conteúdo
    if not any(f in params for f in filtros_restritivos):
        
        # Filtros mais restritivos para evitar o erro 500 do servidor da ALMG
        ano_padrao = 2023
        params['dataInicial'] = f'{ano_padrao}-01-01'
        params['dataFinal'] = f'{ano_padrao}-12-31'
        params['tp'] = 'PL' # Código curto para Tipo de Proposição
        params['expr'] = 'lei' # Código curto para Palavra-chave
        
        st.info(f"Nenhum filtro de pesquisa gerado. Adicionando filtro padrão (restritivo): **dataInicial={params['dataInicial']}, tp='PL', expr='lei'**")
    
    try:
        st.info(f"Buscando dados na API da ALMG com filtros: {params}")
        
        response = requests.get(url, params=params) 
        
        response.raise_for_status() 
        dados = response.json()
        
        df = pd.DataFrame(dados.get('list', []))
        
        if not df.empty:
             df = df[['siglaTipo', 'numero', 'ano', 'ementa', 'apresentacao']]
        return df
        
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro no servidor da API: {e}. A URL que causou o erro 500 pode ser a única forma de contornar a instabilidade da API.")
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
