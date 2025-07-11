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
        'vendaMedEtico': 0,
        'descontoEticoPercent': 0,
        'vendaMedGene': 0,
        'percentDescontoGene': 0,  # % desconto genérico
        'vendaMedSimil': 0,
        'percentDescontoSimil': 0,  # % desconto similar
        'mediaDescontoGenericosSimilares': 0,
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
                if 'KELLY PEREIRA' in current_vendedor.upper():
                    continue
                vendedores[current_vendedor]['vendedor'] = current_vendedor
            continue

        if current_vendedor and 'PRINCIPAL >' in row_str and len(row) >= 6:
            try:
                categoria = row[0].split('>')[1].strip()
                
                # Extrai porcentagem de desconto (coluna 5)
                percent_str = str(row[5]).replace('%', '').replace(',', '.').strip()
                percent_desconto = float(percent_str) / 100 if percent_str else 0

                if 'MED ETICO' in categoria:
                    vendedores[current_vendedor]['vendaMedEtico'] = float(str(row[2]).replace('.', '').replace(',', '.'))
                    vendedores[current_vendedor]['descontoEticoPercent'] = percent_desconto
                
                elif 'MED GENE' in categoria:
                    vendedores[current_vendedor]['vendaMedGene'] = float(str(row[2]).replace('.', '').replace(',', '.'))
                    vendedores[current_vendedor]['percentDescontoGene'] = percent_desconto
                
                elif 'MED SIMIL' in categoria:
                    vendedores[current_vendedor]['vendaMedSimil'] = float(str(row[2]).replace('.', '').replace(',', '.'))
                    vendedores[current_vendedor]['percentDescontoSimil'] = percent_desconto

            except Exception as e:
                print(f"Erro na linha: {row} | Erro: {str(e)}")
                continue

    # Calcula médias após processar todas as linhas
    for vendedor in vendedores.values():
        vendedor['totalVenda'] = vendedor['vendaMedEtico'] + vendedor['vendaMedGene'] + vendedor['vendaMedSimil']
        
        # Calcula média SIMPLES dos descontos (GENÉRICOS + SIMILARES)
        valores_validos = []
        if vendedor['percentDescontoGene'] > 0:
            valores_validos.append(vendedor['percentDescontoGene'])
        if vendedor['percentDescontoSimil'] > 0:
            valores_validos.append(vendedor['percentDescontoSimil'])
        
        vendedor['mediaDescontoGenericosSimilares'] = sum(valores_validos)/len(valores_validos) if valores_validos else 0

    return [v for v in vendedores.values() if v['vendedor']]  # Filtra vendedores vazios

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
            raise ValueError("Nenhum vendedor válido encontrado")

        return jsonify({
            "success": True,
            "data": parsed_data
        })

    except Exception as e:
        return jsonify({
            "error": f"Erro ao processar PDF: {str(e)}",
            "details": str(e)
        }), 500

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)