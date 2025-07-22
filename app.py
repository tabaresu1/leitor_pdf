from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import camelot
import re
from collections import defaultdict

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def parse_pdf_data(raw_data):
    vendedores = defaultdict(lambda: {
        'vendedor': None,
        'vendaMedEtico': 0,
        'descontoEticoPercent': 0,  # Já em formato decimal (ex: 15.5% = 0.155)
        'descontoMedGene': 0,       # Valor absoluto do desconto para genéricos
        'descontoMedSimil': 0,      # Valor absoluto do desconto para similares
        'vendaMedGene': 0,
        'vendaMedSimil': 0,
        'totalVenda': 0,
        'metaPontos': 100000
    })

    current_vendedor = None

    for row in raw_data:
        # Garante que todos os elementos da linha são strings e remove espaços em branco extras
        row_str_list = [str(x).strip() for x in row]
        row_str = '|'.join(row_str_list)

        # Atualiza o vendedor atual
        if 'Usuário:' in row_str:
            match = re.search(r'Usuário:\s*([A-Za-zÀ-ú\s\-0-9]+)', row_str)
            if match:
                current_vendedor = match.group(1).strip()
                # Ajuste na condição para não pular KELLY PEREIRA se ALDO-37 não estiver na mesma linha
                # Se ALDO-37 for um usuário separado, ele será processado individualmente
                if current_vendedor.upper() == 'ALDO-37' or current_vendedor.upper() == '16-KELLY PEREIRA':
                     vendedores[current_vendedor]['vendedor'] = current_vendedor
                else:
                    vendedores[current_vendedor]['vendedor'] = current_vendedor
            continue

        # Processa as linhas de dados se um vendedor estiver definido
        if current_vendedor and 'PRINCIPAL >' in row_str:
            try:
                # Usa regex para extrair a categoria de forma mais flexível
                categoria_match = re.search(r'PRINCIPAL > (MED ETI(?:CO)?|MED GEN(?:E)?|MED SIMI(?:L)?)', row_str)
                if not categoria_match:
                    continue # Pula linhas que não correspondem a uma categoria esperada

                categoria_completa = categoria_match.group(1).strip()

                # Normaliza a categoria para facilitar a lógica
                if 'ETI' in categoria_completa:
                    categoria_normalizada = 'MED ETICO'
                elif 'GEN' in categoria_completa:
                    categoria_normalizada = 'MED GENE'
                elif 'SIMI' in categoria_completa:
                    categoria_normalizada = 'MED SIMIL'
                else:
                    continue # Pula se não for uma das categorias conhecidas

                # Encontra a venda: Tenta pegar o terceiro elemento que pode ser um número
                # A coluna de venda é sempre a terceira (índice 2)
                venda_str = row_str_list[2]
                venda_valor = float(venda_str.replace('.', '').replace(',', '.'))
                
                valor_desconto = 0.0
                percentual_desconto = 0.0

                # A maior dificuldade está em como o camelot lida com a fusão de células.
                # No PDF de 21/07, a coluna de desconto tem dois valores na mesma célula
                # para a linha de "MED SIMI" para ALDO-37.
                # Precisamos de uma lógica mais robusta para extrair o percentual.

                # Tenta extrair o percentual de desconto da coluna que contém "% Tot." ou "%"
                # A posição pode variar, mas geralmente está à direita da venda.
                # Vamos procurar a coluna que contém o '%' no cabeçalho ou no valor
                
                # Tenta encontrar o percentual de desconto. Pode ser row[4] ou row[5] dependendo do PDF.
                # É crucial que o camelot tenha extraído a tabela corretamente para que os índices funcionem.
                # A estratégia 'stream' com edge_tol=500 pode agrupar células.

                # Para MED ETICO, o percentual de desconto vem na coluna 5 (índice 4 no PDF de 19/07, ou pode ser diferente no 21/07)
                # Para MED GENE e MED SIMIL, o valor do desconto vem na coluna 4 (índice 3 no PDF de 19/07)
                
                # Vamos tentar uma abordagem mais flexível para as colunas de desconto,
                # procurando por padrões de números e porcentagens.
                
                # Para o PDF 21/07, a coluna de 'Desconto %' (índice 4 no dataframe) contém dois valores,
                # e a coluna de 'Custo %' (índice 5 no dataframe) também.
                # No PDF de 19/07, a coluna 'Desconto' (índice 4) tem valor e percentual.
                
                # Ajuste: No PDF 19/07, a coluna 4 é 'Desconto' (valor + percentual), coluna 5 é 'Custo %', coluna 6 é 'Lucro %'
                # No PDF 21/07, a coluna 4 é 'Desconto %', coluna 5 é 'Custo %'.

                # VAMOS ASSUMIR A ESTRUTURA MAIS CONSISTENTE DO PDF 21/07
                # Onde Desconto (%) está na coluna 4 (índice 3 do DF do Camelot) e Custo (%) na coluna 5 (índice 4)
                # E o percentual de desconto para 'MED ETICO' parece vir da coluna 'Desconto %'
                # E o valor do desconto para 'MED GENE'/'MED SIMIL' também da coluna 'Desconto %'
                
                if categoria_normalizada == 'MED ETICO':
                    # No PDF de 21/07, o percentual de desconto do ético parece vir da coluna 4 (índice 3)
                    if len(row_str_list) > 3 and row_str_list[3].strip(): # Verifica se a coluna de 'Desconto %' existe e não está vazia
                        desconto_etico_str = row_str_list[3].strip().replace(',', '.')
                        # Extrai apenas o valor percentual, que geralmente é o segundo número
                        match_percent = re.search(r'([\d\.]+)[\s%]*$', desconto_etico_str)
                        if match_percent:
                            percentual_desconto = float(match_percent.group(1)) / 100.0
                    vendedores[current_vendedor]['vendaMedEtico'] = venda_valor
                    vendedores[current_vendedor]['descontoEticoPercent'] = percentual_desconto
                
                elif categoria_normalizada == 'MED GENE':
                    # No PDF de 21/07, o valor do desconto (absoluto) para genéricos/similares
                    # também vem na coluna 4 (índice 3) para ALDO-37
                    if len(row_str_list) > 3 and row_str_list[3].strip():
                        # Pode ter o percentual e o valor absoluto juntos, ou apenas um.
                        # Vamos procurar pelo valor absoluto.
                        valor_desconto_str = row_str_list[3].strip().replace('.', '').replace(',', '.')
                        # Extrai o primeiro número que parece ser o valor absoluto
                        match_valor = re.search(r'^([\d\.]+)', valor_desconto_str)
                        if match_valor:
                            valor_desconto = float(match_valor.group(1))
                    vendedores[current_vendedor]['vendaMedGene'] = venda_valor
                    vendedores[current_vendedor]['descontoMedGene'] = valor_desconto
                
                elif categoria_normalizada == 'MED SIMIL':
                    # Similar ao MED GENE
                    if len(row_str_list) > 3 and row_str_list[3].strip():
                        valor_desconto_str = row_str_list[3].strip().replace('.', '').replace(',', '.')
                        match_valor = re.search(r'^([\d\.]+)', valor_desconto_str)
                        if match_valor:
                            valor_desconto = float(match_valor.group(1))
                    vendedores[current_vendedor]['vendaMedSimil'] = venda_valor
                    vendedores[current_vendedor]['descontoMedSimil'] = valor_desconto

            except Exception as e:
                print(f"Erro na linha: {row_str_list} | Erro: {str(e)}")
                # Para depuração mais fácil, você pode manter as linhas problemáticas
                # ou logar mais detalhes.
                continue

    # Calcula totais
    for vendedor in vendedores.values():
        if vendedor['vendedor']: # Garante que estamos processando um vendedor válido
            vendedor['totalVenda'] = (
                vendedor['vendaMedEtico'] + 
                vendedor['vendaMedGene'] + 
                vendedor['vendaMedSimil']
            )

    return [v for v in vendedores.values() if v['vendedor']]


@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'pdfFile' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    pdf_file = request.files['pdfFile']
    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "O arquivo deve ser um PDF"}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
    pdf_file.save(filepath)

    try:
        tables = camelot.read_pdf(
            filepath,
            flavor='stream',
            pages='all',
            strip_text='\n',
            edge_tol=500, # Mantido alto para agrupar colunas que podem estar muito próximas
            # Adicionar process_background=True se houver linhas que são ignoradas devido à complexidade do layout
            # process_background=True
        )

        if not tables:
            raise ValueError("Nenhuma tabela detectada no PDF. Verifique se o PDF contém tabelas reconhecíveis.")

        all_data = []
        for table in tables:
            # Imprime o DataFrame para inspeção durante a depuração
            print(f"DataFrame extraído da tabela:\n{table.df}") 
            all_data.extend(table.df.values.tolist())

        parsed_data = parse_pdf_data(all_data)

        if not parsed_data:
            raise ValueError("Nenhum dado de vendedor válido encontrado após a análise. Verifique o conteúdo do PDF e a lógica de parsing.")

        return jsonify({
            "success": True,
            "data": parsed_data
        })

    except Exception as e:
        import traceback
        print(f"Erro durante o processamento do PDF: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "error": f"Erro ao processar PDF: {str(e)}. Por favor, verifique o formato do seu PDF e a estrutura das tabelas. Detalhes: {traceback.format_exc()}",
            "details": str(e)
        }), 500

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)