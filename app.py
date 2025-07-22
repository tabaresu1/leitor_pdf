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
                # A condição para filtrar Kelly Pereira foi mantida conforme sua solicitação.
                if 'KELLY PEREIRA' in current_vendedor.upper() and 'ALDO-37' not in current_vendedor.upper():
                    continue
                vendedores[current_vendedor]['vendedor'] = current_vendedor
            continue

        # Processa as linhas de dados se um vendedor estiver definido
        if current_vendedor and 'PRINCIPAL >' in row_str:
            try:
                # *** INÍCIO DA CORREÇÃO PARA RECONHECIMENTO DE CATEGORIAS ***
                # Usa regex para extrair a categoria de forma mais flexível,
                # reconhecendo as formas abreviadas (ex: MED ETI, MED GE, MED SIMI)
                categoria_match = re.search(r'PRINCIPAL > (MED ETI(?:CO)?|MED GE(?:NE)?|MED SIMI(?:L)?)', row_str)
                if not categoria_match:
                    continue # Pula linhas que não correspondem a uma categoria esperada

                categoria_completa = categoria_match.group(1).strip()

                # Normaliza a categoria para facilitar a lógica subsequente
                if 'ETI' in categoria_completa:
                    categoria_normalizada = 'MED ETICO'
                elif 'GE' in categoria_completa:
                    categoria_normalizada = 'MED GENE'
                elif 'SIMI' in categoria_completa:
                    categoria_normalizada = 'MED SIMIL'
                else:
                    continue # Pula se não for uma das categorias conhecidas
                # *** FIM DA CORREÇÃO PARA RECONHECIMENTO DE CATEGORIAS ***

                # A coluna de venda é sempre a terceira (índice 2)
                venda_str = row_str_list[2]
                venda_valor = float(venda_str.replace('.', '').replace(',', '.'))
                
                valor_desconto = 0.0
                percentual_desconto = 0.0
                
                # Para manter a lógica de extração de desconto como estava no seu último código,
                # usando row[4] para valor absoluto e row[5] para percentual.
                # Se o PDF de 21/07 ainda apresentar problemas aqui, será necessário uma lógica mais robusta.
                if len(row_str_list) > 4 and str(row_str_list[4]).strip():
                    try:
                        valor_desconto = float(str(row_str_list[4]).strip().replace('.', '').replace(',', '.'))
                    except ValueError:
                        # Em caso de erro na conversão (ex: célula vazia ou formatada diferente), manter 0.0
                        pass
                
                if len(row_str_list) > 5 and str(row_str_list[5]).strip():
                    try:
                        percentual_desconto = float(str(row_str_list[5]).strip().replace(',', '.')) / 100.0
                    except ValueError:
                        # Em caso de erro na conversão, manter 0.0
                        pass

                if categoria_normalizada == 'MED ETICO':
                    vendedores[current_vendedor]['vendaMedEtico'] = venda_valor
                    vendedores[current_vendedor]['descontoEticoPercent'] = percentual_desconto
                
                elif categoria_normalizada == 'MED GENE':
                    vendedores[current_vendedor]['vendaMedGene'] = venda_valor
                    vendedores[current_vendedor]['descontoMedGene'] = valor_desconto
                
                elif categoria_normalizada == 'MED SIMIL':
                    vendedores[current_vendedor]['vendaMedSimil'] = venda_valor
                    vendedores[current_vendedor]['descontoMedSimil'] = valor_desconto

            except Exception as e:
                print(f"Erro na linha: {row_str_list} | Erro: {str(e)}")
                continue

    # Calcula totais
    for vendedor in vendedores.values():
        if vendedor['vendedor']:
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
            edge_tol=500
        )

        if not tables:
            raise ValueError("Nenhuma tabela detectada")

        all_data = []
        for table in tables:
            all_data.extend(table.df.values.tolist())

        parsed_data = parse_pdf_data(all_data)

        if not parsed_data:
            raise ValueError("Nenhum vendedor válido encontrado após a análise")

        return jsonify({
            "success": True,
            "data": parsed_data
        })

    except Exception as e:
        import traceback
        print(f"Erro durante o processamento do PDF: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "error": f"Erro ao processar PDF: {str(e)}. Verifique o formato do seu PDF ou a estrutura das tabelas.",
            "details": str(e)
        }), 500

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)