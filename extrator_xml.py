import os
import pandas as pd
from lxml import etree as ET
import logging
import re

class ExtratorXML:
    def __init__(self, diretorio_saida):
        self.diretorio_saida = diretorio_saida
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        if not os.path.exists(self.diretorio_saida):
            os.makedirs(self.diretorio_saida)

    def clean_xml_content(self, xml_content):
        try:
            parser = ET.XMLParser(remove_blank_text=True, recover=True)
            root = ET.fromstring(xml_content, parser=parser)

            root_tag = self.get_local_name(root.tag)
            logging.debug(f"Tag raiz do XML: {root_tag}")

            if root_tag == 'NFeLog':
                nfe_elements = root.xpath('.//*[local-name()="NFe"]')
                if nfe_elements:
                    logging.info("Elemento NFe encontrado dentro de NFeLog.")
                    return ET.tostring(nfe_elements[0], encoding='utf-8')
                else:
                    logging.error("Elemento NFe não encontrado dentro de NFeLog.")
                    return None
            elif root_tag in ['procNFe', 'nfeProc']:
                nfe_elements = root.xpath('.//*[local-name()="NFe"]')
                if nfe_elements:
                    logging.info("Elemento NFe encontrado dentro de procNFe/nfeProc.")
                    return ET.tostring(nfe_elements[0], encoding='utf-8')
                else:
                    logging.error("Elemento NFe não encontrado dentro de procNFe/nfeProc.")
                    return None
            elif root_tag == 'NFe':
                logging.info("Elemento NFe encontrado como raiz.")
                return xml_content
            else:
                nfe_elements = root.xpath('.//*[local-name()="NFe"]')
                if nfe_elements:
                    logging.info("Elemento NFe encontrado em estrutura desconhecida.")
                    return ET.tostring(nfe_elements[0], encoding='utf-8')
                else:
                    logging.error("Elemento NFe não encontrado no XML.")
                    return None
        except ET.XMLSyntaxError as e:
            logging.error(f"Erro de sintaxe durante a limpeza do conteúdo: {e}")
            return None

    def get_local_name(self, tag):
        return tag.split('}', 1)[-1] if '}' in tag else tag

    def extrair_informacoes_completas(self, xml_file):
        try:
            with open(xml_file, 'rb') as file:
                xml_content = file.read()
            if not xml_content.strip():
                logging.error(f"Arquivo XML vazio ou corrompido: {xml_file}")
                return []

            cleaned_content = self.clean_xml_content(xml_content)
            if cleaned_content is None:
                logging.error(f"Falha ao processar o arquivo {xml_file}: conteúdo XML inválido ou incompleto.")
                return []

            parser = ET.XMLParser(remove_blank_text=True, recover=True)
            root = ET.fromstring(cleaned_content, parser=parser)

            root_tag = self.get_local_name(root.tag)
            logging.debug(f"Tag raiz após limpeza: {root_tag}")

            if root_tag == 'NFe':
                data_extracao = self.extract_data(root)
            else:
                logging.error(f"Tipo de arquivo desconhecido ou não suportado: {xml_file}")
                return []

            return data_extracao
        except ET.XMLSyntaxError as e:
            logging.error(f"Erro de sintaxe XML no arquivo {xml_file}: {e}")
            return []
        except Exception as e:
            logging.error(f"Erro ao processar o arquivo {xml_file}: {e}")
            return []

    def convert_value(self, value):
        try:
            number = float(value)
            return f'{number:.6f}'.rstrip('0').rstrip('.').replace('.', ',')
        except ValueError:
            return value

    def extract_data(self, root):
        all_items_data = []

        infNFe_elements = root.xpath('.//*[local-name()="infNFe"]')
        if not infNFe_elements:
            logging.error("Não foi possível encontrar o elemento infNFe no XML.")
            return []
        infNFe = infNFe_elements[0]

        fixed_fields = {
            'Chave de Acesso da Nota Fiscal': infNFe.get('Id'),
            'Número da NF': self.find_text(infNFe, './/*[local-name()="nNF"]'),
            'Número de Série da NF': self.find_text(infNFe, './/*[local-name()="serie"]'),
            'Tipo de Operação': self.find_text(infNFe, './/*[local-name()="tpNF"]'),
            'Data Emissão': self.find_text(infNFe, './/*[local-name()="dhEmi"]') or self.find_text(infNFe, './/*[local-name()="dEmi"]'),
            'Data Saída da Mercadoria': self.find_text(infNFe, './/*[local-name()="dhSaiEnt"]') or self.find_text(infNFe, './/*[local-name()="dSaiEnt"]'),
            'Natureza da Operação': self.find_text(infNFe, './/*[local-name()="natOp"]'),
            'CNPJ/CPF Emitente': self.find_text(infNFe, './/*[local-name()="emit"]/*[local-name()="CNPJ"]') or self.find_text(infNFe, './/*[local-name()="emit"]/*[local-name()="CPF"]'),
            'Nome Emitente': self.find_text(infNFe, './/*[local-name()="emit"]/*[local-name()="xNome"]'),
            'CNPJ/CPF Destinatário': self.find_text(infNFe, './/*[local-name()="dest"]/*[local-name()="CNPJ"]') or self.find_text(infNFe, './/*[local-name()="dest"]/*[local-name()="CPF"]'),
            'Nome Destinatário': self.find_text(infNFe, './/*[local-name()="dest"]/*[local-name()="xNome"]'),
            'Estado de Origem': self.find_text(infNFe, './/*[local-name()="enderEmit"]/*[local-name()="UF"]'),
            'Estado de Destino': self.find_text(infNFe, './/*[local-name()="enderDest"]/*[local-name()="UF"]'),
            'Valor Contábil': self.find_text(infNFe, './/*[local-name()="ICMSTot"]/*[local-name()="vNF"]'),
            'Valor ST': self.find_text(infNFe, './/*[local-name()="ICMSTot"]/*[local-name()="vST"]'),
            'Outras Despesas': self.find_text(infNFe, './/*[local-name()="ICMSTot"]/*[local-name()="vOutro"]'),
            'Seguro': self.find_text(infNFe, './/*[local-name()="ICMSTot"]/*[local-name()="vSeg"]'),
            'Informações Complementares': self.find_text(infNFe, './/*[local-name()="infCpl"]'),
        }

        data = {}
        for field, value in fixed_fields.items():
            if value:
                extracted_text = value.strip()
                if field == 'Chave de Acesso da Nota Fiscal':
                    extracted_text = re.sub(r'\D', '', extracted_text)
                else:
                    extracted_text = self.convert_value(extracted_text)
                data[field] = extracted_text or '0,00'
            else:
                data[field] = '0'

        det_elements = infNFe.xpath('.//*[local-name()="det"]')
        for det in det_elements:
            item_data = data.copy()

            variable_fields = {
                'Descrição Produto': self.find_text(det, './/*[local-name()="xProd"]'),
                'NCM': self.find_text(det, './/*[local-name()="NCM"]'),
                'CFOP': self.find_text(det, './/*[local-name()="CFOP"]'),
                'Valor do Produto': self.find_text(det, './/*[local-name()="vProd"]'),
                'Valor Frete Produto': self.find_text(det, './/*[local-name()="vFrete"]'),
                'Valor Desconto Produto': self.find_text(det, './/*[local-name()="vDesc"]'),
                'Quantidade': self.find_text(det, './/*[local-name()="qCom"]'),
                'Unidade': self.find_text(det, './/*[local-name()="uCom"]'),
                'CST ICMS': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="CST"]'),
                'CSOSN': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="CSOSN"]'),
                'Origem da Mercadoria ICMS': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="orig"]'),
                'Base de ICMS': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="vBC"]'),
                'Valor do ICMS': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="vICMS"]'),
                'Alíquota de ICMS': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="pICMS"]'),
                'Valor Crédito ICMS': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="vCredICMSSN"]'),
                'Valor Crédito ICMS Simples': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="vCredICMSSN"]'),
                'Percentual Crédito ICMS Simples': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="pCredSN"]'),
                'CST IPI': self.find_text(det, './/*[local-name()="IPI"]//*[local-name()="CST"]'),
                'Valor do IPI': self.find_text(det, './/*[local-name()="IPI"]//*[local-name()="vIPI"]'),
                'Valor do IPI Devolvido': self.find_text(det, './/*[local-name()="IPIDevol"]//*[local-name()="vIPIDevol"]'),
                'CST PIS': self.find_text(det, './/*[local-name()="PIS"]//*[local-name()="CST"]'),
                'Valor do PIS': self.find_text(det, './/*[local-name()="PIS"]//*[local-name()="vPIS"]'),
                'Alíquota de PIS': self.find_text(det, './/*[local-name()="PIS"]//*[local-name()="pPIS"]'),
                'CST COFINS': self.find_text(det, './/*[local-name()="COFINS"]//*[local-name()="CST"]'),
                'Valor do COFINS': self.find_text(det, './/*[local-name()="COFINS"]//*[local-name()="vCOFINS"]'),
                'Alíquota de COFINS': self.find_text(det, './/*[local-name()="COFINS"]//*[local-name()="pCOFINS"]'),
                'MVA': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="pMVAST"]'),
                'Valor FCP': self.find_text(det, './/*[local-name()="ICMS"]//*[local-name()="vFCPST"]'),
                'Campo DI': self.find_text(det, './/*[local-name()="detExport"]'),
            }

            for field, value in variable_fields.items():
                if value:
                    extracted_text = value.strip()
                    extracted_text = self.convert_value(extracted_text)
                    item_data[field] = extracted_text or '0,00'
                else:
                    item_data[field] = '0'

            all_items_data.append(item_data)

        return all_items_data

    def find_text(self, element, xpath):
        try:
            result = element.xpath(xpath)
            if result:
                if isinstance(result, list):
                    return result[0].text if result[0].text else None
                else:
                    return result.text
            return None
        except Exception as e:
            logging.error(f"Erro ao executar XPath '{xpath}': {e}")
            return None

    def processar_completo(self, diretorio_xml, nome_arquivo):
        all_data = []
        total_arquivos = 0
        arquivos_processados = 0

        for filename in os.listdir(diretorio_xml):
            if filename.lower().endswith('.xml'):
                total_arquivos += 1
                filepath = os.path.join(diretorio_xml, filename)
                logging.info(f"Processando arquivo: {filename}")
                info = self.extrair_informacoes_completas(filepath)
                if info:
                    arquivos_processados += 1
                    all_data.extend(info)
                else:
                    logging.warning(f"Arquivo ignorado ou sem dados: {filename}")

        logging.info(f"Total de arquivos encontrados: {total_arquivos}")
        logging.info(f"Total de arquivos processados com sucesso: {arquivos_processados}")

        if all_data:
            logging.info(f"Dados extraídos com sucesso: {len(all_data)} registros.")
            try:
                df = pd.DataFrame(all_data)
                logging.info("DataFrame criado com sucesso.")
                output_filename = os.path.join(self.diretorio_saida, nome_arquivo)
                df.to_excel(output_filename, index=False)
                logging.info(f"Arquivo Excel salvo em: {output_filename}")
                return output_filename
            except Exception as e:
                logging.error(f"Erro ao criar DataFrame ou salvar arquivo Excel: {str(e)}")
                return None
        else:
            logging.info("Nenhum dado para salvar.")
            return None
