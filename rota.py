import streamlit as st
import requests
from lxml import etree
from datetime import datetime, timedelta
import os

# Função para remover namespaces do XML
def remove_namespaces(tree):
    """Remove namespaces de um elemento XML e seus filhos."""
    for elem in tree.getiterator():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]  # Remove namespace
    return tree

# Obter as credenciais de variáveis de ambiente
def autenticar_usuario():
    print("Autenticando usuário...")

    # Obtenha as credenciais do ambiente
    codigo_acesso = os.getenv("CODIGO_ACESSO")
    login = os.getenv("LOGIN")
    senha = os.getenv("SENHA")

    # Verifica se as credenciais foram configuradas corretamente
    if not codigo_acesso or not login or not senha:
        st.error("Credenciais não configuradas! Verifique suas variáveis de ambiente.")
        return None

    # Resto do código de autenticação...

    # URL do serviço SOAP de homologação para autenticação
    url = 'https://app.viafacil.com.br/wsvp/ValePedagio'
    
    # Cabeçalhos SOAP
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'autenticarUsuario'
    }
    
    # Criação do envelope SOAP
    envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
                             nsmap={
                                 'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                                 'xsd': 'http://www.w3.org/2001/XMLSchema',
                                 'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                                 'cgmp': 'http://cgmp.com'
                             })
    
    # Criação do corpo da requisição
    body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    autenticar_usuario = etree.SubElement(body, '{http://cgmp.com}autenticarUsuario',
                                          attrib={'{http://schemas.xmlsoap.org/soap/envelope/}encodingStyle': 'http://schemas.xmlsoap.org/soap/encoding/'})
    
    # Adicionando os elementos de autenticação
    etree.SubElement(autenticar_usuario, 'codigodeacesso').text = codigo_acesso
    etree.SubElement(autenticar_usuario, 'login').text = login
    etree.SubElement(autenticar_usuario, 'senha').text = senha
    
    # Converte o envelope SOAP para string
    soap_request = etree.tostring(envelope, pretty_print=True, xml_declaration=True, encoding='UTF-8')
    
    # Faz a requisição SOAP
    try:
        response = requests.post(url, data=soap_request, headers=headers)
        response.raise_for_status()  # Verifica erros de requisição HTTP
        
        # Processa a resposta
        response_content = etree.fromstring(response.content)
        ns = {
            'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns1': 'http://cgmp.com',
            'ns2': 'http://ws.dto.model.cgmp.com'
        }
        
        autenticar_usuario_response = response_content.find('.//ns1:autenticarUsuarioResponse', namespaces=ns)
        if autenticar_usuario_response is not None:
            autenticar_usuario_return = autenticar_usuario_response.find('.//autenticarUsuarioReturn')
            if autenticar_usuario_return is not None:
                sessao = autenticar_usuario_return.find('.//sessao').text
                status = autenticar_usuario_return.find('.//status').text
                
                if status == '0':
                    print(f"Autenticação bem-sucedida. Sessão: {sessao}")
                    return sessao  # Retorna a sessão para uso futuro
                else:
                    st.error(f"Erro na autenticação. Status: {status}")
                    return None
            else:
                st.error("Elemento 'autenticarUsuarioReturn' não encontrado.")
                return None
        else:
            st.error("Elemento 'autenticarUsuarioResponse' não encontrado.")
            return None
        
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na requisição SOAP: {e}")
        return None

# Função para consultar o custo da rota e dividir pelo número de eixos
def consultar_custo_rota(nomeRota, placa, nEixos, inicioVigencia, fimVigencia, sessao):
    # URL do serviço SOAP (o mesmo da autenticação)
    url = 'https://app.viafacil.com.br/wsvp/ValePedagio'
    
    # Cabeçalhos SOAP
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'obterCustoRota'
    }
    
    # Criação do envelope SOAP
    envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
                             nsmap={'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/'})
    body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    consulta_custo_rota = etree.SubElement(body, '{http://cgmp.com}obterCustoRota')
    
    # Adicionar parâmetros de entrada obrigatórios
    etree.SubElement(consulta_custo_rota, 'nomeRota').text = nomeRota
    etree.SubElement(consulta_custo_rota, 'placa').text = placa
    etree.SubElement(consulta_custo_rota, 'nEixos').text = str(nEixos)
    etree.SubElement(consulta_custo_rota, 'inicioVigencia').text = inicioVigencia
    etree.SubElement(consulta_custo_rota, 'fimVigencia').text = fimVigencia
    etree.SubElement(consulta_custo_rota, 'sessao').text = sessao
    
    # Converter o envelope para string
    soap_request = etree.tostring(envelope, pretty_print=True, xml_declaration=True, encoding='UTF-8')
    
    # Fazer a requisição SOAP
    try:
        response = requests.post(url, data=soap_request, headers=headers)
        response.raise_for_status()

        # Remover namespaces da resposta XML
        response_xml = remove_namespaces(etree.fromstring(response.content))
        
        # Buscar apenas o valor da rota
        valor = response_xml.find('.//valor')
        if valor is not None:
            # Calcular o valor por eixo
            valor_total = float(valor.text)
            valor_por_eixo = valor_total / nEixos
            return valor_total, valor_por_eixo
        else:
            st.error("Erro: Não foi possível encontrar o valor na resposta.")
            return None, None
    
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na requisição SOAP: {e}")
        return None, None

# Função para calcular a data de hoje e adicionar 5 dias
def calcular_datas():
    hoje = datetime.now()
    fim_vigencia = hoje + timedelta(days=5)
    return hoje.strftime('%Y-%m-%d'), fim_vigencia.strftime('%Y-%m-%d')


# Defina a placa como um valor fixo
placa = "CUE3J55"  # Valor fixo da placa
# Interface do Streamlit
st.title("Consulta de Custo de Rotas - Vale Pedágio")

# Input para o nome da fazenda
fazenda = st.text_input("Digite o nome da fazenda (ex: AGUA SANTA):")

# Input para os eixos de ida e volta
nEixosIda = st.number_input("Número de eixos na ida:", min_value=2, max_value=10, value=5)
nEixosVolta = st.number_input("Número de eixos na volta:", min_value=2, max_value=10, value=5)

# Botão para processar
if st.button("Consultar custo da rota"):
    # Construir nomes das rotas
    nomeRotaIda = f"FAZ {fazenda} - IDA"
    nomeRotaVolta = f"FAZ {fazenda} - VOLTA"
    
    # Autenticação
    sessao = autenticar_usuario()
    
    if sessao:
        # Datas de vigência
        inicioVigencia, fimVigencia = calcular_datas()
        
        # Consultar rota de ida
        st.write(f"Consultando a rota: {nomeRotaIda}")
        valor_ida, valor_por_eixo_ida = consultar_custo_rota(nomeRotaIda, placa, nEixosIda, inicioVigencia, fimVigencia, sessao)
        if valor_ida is not None:
            st.success(f"Valor total da rota (ida): R$ {valor_ida:.2f}")
            st.success(f"Valor por eixo (ida): R$ {valor_por_eixo_ida:.2f}")
        
        # Consultar rota de volta
        st.write(f"Consultando a rota: {nomeRotaVolta}")
        valor_volta, valor_por_eixo_volta = consultar_custo_rota(nomeRotaVolta, placa, nEixosVolta, inicioVigencia, fimVigencia, sessao)
        if valor_volta is not None:
            st.success(f"Valor total da rota (volta): R$ {valor_volta:.2f}")
            st.success(f"Valor por eixo (volta): R$ {valor_por_eixo_volta:.2f}")

