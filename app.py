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
        'descontoMedGene': 0,  # Campo adicionado
        'descontoMedSimil': 0, # Campo adicionado
        'vendaMedGene': 0,
        'vendaMedSimil': 0,
        'totalVenda': 0,
        'metaPontos': 100000
    })

    current_vendedor = None

    for row in raw_data:
        row_str = '|'.join([str(x).strip() for x in row])

        if 'Usuário:' in row_str:
            match = re.search(r'Usuário:\s*([A-Za-zÀ-ú\s\-0-9]+)', row_str)
            if match:
                current_vendedor = match.group(1).strip()
                if 'KELLY PEREIRA' in current_vendedor.upper() and 'ALDO-37' not in current_vendedor.upper():
                    continue 
                vendedores[current_vendedor]['vendedor'] = current_vendedor
            continue

        if current_vendedor and 'PRINCIPAL >' in row_str and len(row) >= 5:
            try:
                categoria = row[0].split('>')[1].strip()
                venda_valor = float(str(row[2]).replace('.', '').replace(',', '.'))
                
                # Extração de desconto simplificada e robusta
                discount_column = str(row[4]).strip()
                discount_parts = discount_column.split('\n')
                
                # Valor do desconto sempre será a última parte
                discount_value = 0.0
                if discount_parts:
                    # Pega o último elemento não vazio
                    last_part = [p for p in discount_parts if p][-1]
                    discount_value = float(last_part.replace('.', '').replace(',', '.'))
                
                if 'MED ETICO' in categoria:
                    vendedores[current_vendedor]['vendaMedEtico'] = venda_valor
                    # Para éticos usamos percentual (como estava)
                    vendedores[current_vendedor]['descontoEticoPercent'] = discount_value / 100
                
                elif 'MED GENE' in categoria:
                    vendedores[current_vendedor]['vendaMedGene'] = venda_valor
                    vendedores[current_vendedor]['descontoMedGene'] = discount_value
                
                elif 'MED SIMIL' in categoria:
                    vendedores[current_vendedor]['vendaMedSimil'] = venda_valor
                    vendedores[current_vendedor]['descontoMedSimil'] = discount_value

            except Exception as e:
                print(f"Erro na linha: {row} | Erro: {str(e)}")
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
        # Imprime o erro completo para depuração no console do servidor
        import traceback
        print(f"Erro durante o processamento do PDF: {str(e)}")
        print(traceback.format_exc()) # Imprime o stack trace completo
        return jsonify({
            "error": f"Erro ao processar PDF: {str(e)}. Verifique o formato do seu PDF ou a estrutura das tabelas.",
            "details": str(e)
        }), 500

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)