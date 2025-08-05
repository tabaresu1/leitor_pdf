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
        'descontoEticoPercent': 0,
        'descontoMedGene': 0,
        'descontoMedSimil': 0,
        'vendaMedGene': 0,
        'vendaMedSimil': 0,
        'qtdMedEtico': 0,      # NOVO
        'qtdMedGene': 0,       # NOVO
        'qtdMedSimil': 0,      # NOVO
        'totalVenda': 0,
        'totalQtd': 0,         # NOVO
        'metaPontos': 100000
    })

    current_vendedor = None
    idx_itens = None

    for row in raw_data:
        row_str_list = [str(x).strip() for x in row]
        row_str = '|'.join(row_str_list)

        # Detecta o índice da coluna "Itens" no cabeçalho
        if idx_itens is None and any("Itens" in x for x in row_str_list):
            idx_itens = next((i for i, x in enumerate(row_str_list) if "Itens" in x), None)
            continue

        if 'Usuário:' in row_str:
            match = re.search(r'Usuário:\s*([A-Za-zÀ-ú\s\-0-9]+)', row_str)
            if match:
                current_vendedor = match.group(1).strip()
                if 'KELLY PEREIRA' in current_vendedor.upper() and 'ALDO-37' not in current_vendedor.upper():
                    continue
                vendedores[current_vendedor]['vendedor'] = current_vendedor
            continue

        if current_vendedor and 'PRINCIPAL >' in row_str:
            try:
                categoria_match = re.search(r'PRINCIPAL > (MED ETI(?:CO|COS)?|MED GE(?:E|NE|NERICOS)?|MED SIMI(?:L|LAR|LARES)?)', row_str)
                if not categoria_match:
                    continue

                categoria_completa = categoria_match.group(1).strip()
                if 'ETI' in categoria_completa:
                    categoria_normalizada = 'MED ETICO'
                elif 'GE' in categoria_completa:
                    categoria_normalizada = 'MED GENE'
                elif 'SIMI' in categoria_completa:
                    categoria_normalizada = 'MED SIMIL'
                else:
                    continue

                venda_str = row_str_list[2]
                venda_valor = float(venda_str.replace('.', '').replace(',', '.'))

                # Extrai quantidade de itens
                qtd_valor = 0
                if idx_itens is not None and len(row_str_list) > idx_itens:
                    try:
                        qtd_str = row_str_list[idx_itens].replace('.', '').replace(',', '.')
                        qtd_valor = int(float(qtd_str))
                    except ValueError:
                        qtd_valor = 0

                valor_desconto = 0.0
                percentual_desconto = 0.0
                if len(row_str_list) > 4 and str(row_str_list[4]).strip():
                    try:
                        valor_desconto = float(str(row_str_list[4]).strip().replace('.', '').replace(',', '.'))
                    except ValueError:
                        pass

                if len(row_str_list) > 5 and str(row_str_list[5]).strip():
                    try:
                        percentual_desconto = float(str(row_str_list[5]).strip().replace(',', '.')) / 100.0
                    except ValueError:
                        pass

                if categoria_normalizada == 'MED ETICO':
                    vendedores[current_vendedor]['vendaMedEtico'] = venda_valor
                    vendedores[current_vendedor]['descontoEticoPercent'] = percentual_desconto
                    vendedores[current_vendedor]['qtdMedEtico'] = qtd_valor
                elif categoria_normalizada == 'MED GENE':
                    vendedores[current_vendedor]['vendaMedGene'] = venda_valor
                    vendedores[current_vendedor]['descontoMedGene'] = valor_desconto
                    vendedores[current_vendedor]['qtdMedGene'] = qtd_valor
                elif categoria_normalizada == 'MED SIMIL':
                    vendedores[current_vendedor]['vendaMedSimil'] = venda_valor
                    vendedores[current_vendedor]['descontoMedSimil'] = valor_desconto
                    vendedores[current_vendedor]['qtdMedSimil'] = qtd_valor

            except Exception as e:
                print(f"Erro na linha: {row_str_list} | Erro: {str(e)}")
                continue

    for vendedor in vendedores.values():
        if vendedor['vendedor']:
            vendedor['totalVenda'] = (
                vendedor['vendaMedEtico'] +
                vendedor['vendaMedGene'] +
                vendedor['vendaMedSimil']
            )
            vendedor['totalQtd'] = (
                vendedor['qtdMedEtico'] +
                vendedor['qtdMedGene'] +
                vendedor['qtdMedSimil']
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