# Olist VoC Intelligence Chat

Chatbot que responde perguntas sobre a experiência dos clientes da Olist com base nas avaliações reais da plataforma, mostrando quais avaliações sustentam cada resposta. A solução usa RAG (Retrieval-Augmented Generation) sobre os comentários do *Brazilian E-Commerce Public Dataset by Olist*.

Projeto desenvolvido para o Tech Challenge da Fase 4 da POSTECH (FIAP).

> Este README está em construção. A documentação detalhada de cada parte do sistema ficará na pasta `docs/`.

## Pré-requisitos

- Python 3.12
- Conta no Kaggle com um token de API

## Instalação

Crie o ambiente virtual e instale as dependências:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copie o modelo de configuração e ajuste os valores, se necessário:

```bash
cp .env.example .env
```

## Download da base

O download usa a API do Kaggle. Gere um token em **Settings > API** no site do Kaggle e salve-o em `~/.kaggle/access_token`:

```bash
mkdir -p ~/.kaggle
echo SEU_TOKEN > ~/.kaggle/access_token
chmod 600 ~/.kaggle/access_token
```

Com o ambiente virtual ativo, baixe os arquivos:

```bash
python -m scripts.download_data
```

Os cinco arquivos usados pelo projeto ficam em `data/raw/`. Essa pasta não vai para o repositório.
