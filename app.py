import os
import logging
from flask import Flask, request, jsonify, session, url_for, send_from_directory, render_template
from werkzeug.utils import secure_filename
import pandas as pd
from extrator_xml import ExtratorXML

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

PREVIEW_LIMIT = 500

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

extrator = ExtratorXML(app.config['PROCESSED_FOLDER'])

# Funções auxiliares para limpar e inicializar a sessão
def limpar_sessao():
    session.pop('dados_upload', None)

def inicializar_sessao_dados():
    if 'dados_upload' not in session:
        session['dados_upload'] = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_xml', methods=['POST'])
def upload_xml():
    try:
        limpar_sessao()
        inicializar_sessao_dados()

        files = request.files
        if len(files) == 0:
            return jsonify({'status': 'error', 'message': 'Nenhum arquivo enviado.'})

        total_files = len(files)
        logging.info(f"Total de arquivos recebidos: {total_files}")

        all_data = []
        for file_key in files:
            try:
                file = files[file_key]
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                logging.info(f"Processando arquivo: {filename}")

                file.save(file_path)

                data = extrator.extrair_informacoes_completas(file_path)
                if not data:
                    logging.error(f"Falha ao extrair dados do arquivo {filename}, arquivo ignorado.")
                    continue

                all_data.extend(data)

                # Remover arquivo após processamento
                os.remove(file_path)

            except Exception as e:
                logging.error(f"Erro ao processar o arquivo {filename}: {e}")
                continue

        logging.info(f"Total de arquivos processados com sucesso: {len(all_data)}")

        if not all_data:
            return jsonify({'status': 'error', 'message': 'Nenhum dado processado. Verifique os arquivos XML.'})

        session['dados_upload'].extend(all_data)
        session.modified = True

        # Enviar apenas os primeiros 500 registros para o front-end
        preview_data = session['dados_upload'][:PREVIEW_LIMIT]

        return jsonify({
            'status': 'success',
            'items': preview_data,
            'message': 'Arquivos processados com sucesso!'
        })

    except Exception as e:
        logging.error(f"Erro ao processar os uploads: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/exportar_excel', methods=['POST'])
def exportar_excel():
    try:
        # Verifica se há dados na sessão
        if 'dados_upload' not in session or len(session['dados_upload']) == 0:
            return jsonify({'error': 'Nenhum dado processado para exportar'}), 400

        # Nome do arquivo Excel a ser gerado
        nome_arquivo_excel = 'dados_processados.xlsx'
        output_filename = os.path.join(app.config['PROCESSED_FOLDER'], nome_arquivo_excel)

        colunas_ordenadas = [
            'Chave de Acesso da Nota Fiscal', 'Número da NF', 'Número de Série da NF', 'Tipo de Operação',
            'Data Emissão', 'Data Saída da Mercadoria', 'Natureza da Operação', 'CNPJ/CPF Emitente',
            'Nome Emitente', 'CNPJ/CPF Destinatário', 'Nome Destinatário', 'Estado de Origem', 'Estado de Destino',
            'Descrição Produto', 'NCM', 'CFOP', 'Valor do Produto', 'Valor Frete Produto',
            'Valor Desconto Produto', 'Outras Despesas', 'Seguro', 'Valor Contábil', 'Quantidade',
            'Unidade', 'CST ICMS', 'CSOSN', 'Base de ICMS', 'Valor do ICMS', 'Alíquota de ICMS',
            'Valor Crédito ICMS', 'Valor Crédito ICMS Simples', 'Percentual Crédito ICMS Simples',
            'Origem da Mercadoria ICMS', 'CST IPI', 'Valor do IPI', 'Valor do IPI Devolvido',
            'CST PIS', 'Valor do PIS', 'Alíquota de PIS', 'CST COFINS', 'Valor do COFINS',
            'Alíquota de COFINS', 'MVA', 'Valor FCP', 'Valor ST', 'Campo DI', 'Informações Complementares'
        ]

        # Cria o DataFrame com os dados da sessão
        df = pd.DataFrame(session['dados_upload'], columns=colunas_ordenadas)
        df['CNPJ/CPF Emitente'] = df['CNPJ/CPF Emitente'].astype(str)
        df['CNPJ/CPF Destinatário'] = df['CNPJ/CPF Destinatário'].astype(str)

        # Adiciona a coluna "Classificação" após "Descrição Produto"
        classificacao_options = [
            'REVENDA',
            'INSUMO',
            'USO E CONSUMO',
            'COMPRA PARA PRESTAÇÃO DE SERVIÇO',
            'DEVOLUÇÃO',
            'REMESSA',
            'ATIVO IMOBILIZADO',
            'TRANSFERENCIA'
        ]

        # Encontrar o índice da coluna "Descrição Produto"
        descricao_produto_index = colunas_ordenadas.index('Descrição Produto') + 1
        colunas_ordenadas.insert(descricao_produto_index, 'Classificação')

        # Inserir a coluna "Classificação" no DataFrame com valores vazios
        df.insert(descricao_produto_index, 'Classificação', '')

        # Reordenar as colunas conforme a nova lista
        df = df[colunas_ordenadas]

        # Extrai as chaves de acesso únicas
        chaves_unicas = df['Chave de Acesso da Nota Fiscal'].drop_duplicates().reset_index(drop=True)
        df_chaves = pd.DataFrame({'Chave de Acesso': chaves_unicas})

        # Cria o arquivo Excel com xlsxwriter
        with pd.ExcelWriter(output_filename, engine='xlsxwriter') as writer:
            # Salva os DataFrames em diferentes abas
            df.to_excel(writer, sheet_name='Dados', index=False)
            df_chaves.to_excel(writer, sheet_name='Chaves', index=False)

            # Adiciona o dropdown de validação de dados
            workbook = writer.book
            worksheet = writer.sheets['Dados']

            # Adiciona as opções de classificação em um intervalo oculto
            hidden_sheet_name = 'Opcoes'
            hidden_worksheet = workbook.add_worksheet(hidden_sheet_name)
            hidden_worksheet.hide()

            # Escreve as opções na aba oculta
            for row, option in enumerate(classificacao_options):
                hidden_worksheet.write(row, 0, option)

            # Define o intervalo de validação para o dropdown
            first_row = 1  # Linha inicial (2 no Excel, índice 0-based)
            last_row = len(df) + 1  # Última linha dos dados
            col_letter = chr(65 + descricao_produto_index)  # Converte índice para letra (A, B, ...)

            dropdown_range = f"{hidden_sheet_name}!$A$1:$A${len(classificacao_options)}"
            for row in range(first_row, last_row):
                worksheet.data_validation(
                    row, descricao_produto_index, row, descricao_produto_index,
                    {
                        'validate': 'list',
                        'source': dropdown_range,
                        'input_message': 'Selecione uma classificação',
                        'error_message': 'Valor inválido. Escolha uma das opções.'
                    }
                )

        return jsonify({
            'message': 'Arquivo Excel criado com sucesso!',
            'filename': url_for('download_file', filename=nome_arquivo_excel)
        })
    except Exception as e:
        logging.exception("Erro ao exportar para Excel: %s", str(e))
        return jsonify({'error': str(e)}), 500

# Rota para download do arquivo Excel gerado
@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': 'Arquivo não encontrado'}), 404

# Rota de logout genérica (a ser implementada conforme a autenticação utilizada)
@app.route('/logout', methods=['GET'])
def logout():
    limpar_sessao()
    session.clear()
    return jsonify({'message': 'Logout realizado com sucesso!'}), 200

if __name__ == '__main__':
    # Cria as pastas de upload e processamento se não existirem
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
    app.run(debug=True)
