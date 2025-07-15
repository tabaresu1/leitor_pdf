
# 💊 PharmaVision - Dashboard de Desempenho Farmacêutico

## 🌟 Visão Geral

**PharmaVision** é um sistema completo para análise estratégica de vendas em farmácias, capaz de:

- Processar automaticamente relatórios de vendas em PDF  
- Gerar métricas precisas por vendedor e categoria de medicamentos  
- Fornecer recomendações inteligentes para melhorar o desempenho  

---

## 🛠 Tecnologias Utilizadas

| Componente     | Tecnologias |
|----------------|-------------|
| **Frontend**   | ![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white) ![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?logo=tailwind-css&logoColor=white) ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black) |
| **Backend**    | ![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white) ![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white) |
| **Processamento** | ![Camelot](https://img.shields.io/badge/Camelot-FF6B6B?logo=pdf&logoColor=white) ![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas&logoColor=white) |

---

## 🚀 Como Executar

### Pré-requisitos

```bash
# Instale as dependências Python
pip install flask flask-cors camelot-py pandas
```

### Passo a Passo

1. Inicie o servidor backend:

```bash
python app.py
```

> Servidor disponível em: `http://localhost:5000`

2. Configure o frontend:

```javascript
// Em js/config.js
const API_ENDPOINT = "http://localhost:5000/upload-pdf";
```

3. Acesse o sistema:

- Abra `index.html` no navegador  
- Selecione um relatório PDF para análise  

---

## 🔍 Funcionalidades Principais

### 📊 Análise de Desempenho

Métricas por categoria:

```python
{
  "vendaMedEtico": 1500.50,
  "descontoEticoPercent": 0.07,
  "vendaMedGene": 3200.00,
  "totalVenda": 4700.50
}
```

### 💡 Recomendações Automáticas

- **Vendas altas de éticos**  
  → Ofereça genéricos como alternativa econômica

- **Descontos excessivos**  
  → Reduza gradualmente para 5% em éticos

- **Baixa performance**  
  → Treinamento específico para o vendedor

---

## 📦 Estrutura do Projeto

```text
leitor_pdf/
├── app.py                   # Toda a parte do backend
└── index.html               # Frontend do projeto
```

---

## 🛠 Customização

Ajuste os parâmetros de análise em `app.py`:

```python
# Limites para recomendações
THRESHOLDS = {
    'MAX_ETICOS': 0.25,     # Máximo de 25% de vendas em éticos
    'MAX_DESCONTO': 0.08    # Máximo de 8% de desconto
}
```

---

## 📌 Exemplo de Uso

1. Envie um relatório PDF pela interface web  
2. Analise os resultados:

- Gráficos interativos  
- Tabelas comparativas  
- Alertas de desempenho  

3. Exporte os dados para **CSV** ou **PDF**

---

## ⚠️ Solução de Problemas

**Problema:** PDF não processado  
**Solução:**

```bash
# Verifique os logs do Flask
tail -f api.log

# Atualize as dependências
pip install --upgrade camelot-py
```

---

## 📄 Licença

Projeto desenvolvido para **Grupo SP © 2025**  
Contato: [grupospsocialmedia@gmail.com](mailto:grupospsocialmedia@gmail.com)

---

> ✨ **Dica:** Para uma experiência completa, utilize com os relatórios padronizados da sua farmácia!
