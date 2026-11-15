# Decisões técnicas

Registro aqui as decisões tomadas em cada etapa do projeto, com o motivo de cada uma. O documento cresce junto com o código, e cada PR que envolve uma escolha acrescenta a sua parte.

## Dependências e qualidade do código

Separei as dependências em dois arquivos. O `requirements.txt` tem só o que a API e os scripts dos workflows usam, e é ele que vai para a imagem do contêiner. O `requirements-dev.txt` inclui o primeiro e acrescenta o que serve apenas ao desenvolvimento: o kernel do Jupyter para o notebook, o pytest e o Ruff. Com isso a imagem fica menor e não carrega ferramentas que nunca vai executar. Todas as versões estão fixadas, para que o CI, os workflows e a imagem usem exatamente os mesmos pacotes.

Para lint e formatação escolhi o Ruff, que faz os dois papéis em uma única ferramenta e roda em poucos segundos no CI. As regras ativadas cobrem erros comuns, ordem dos imports, sintaxe antiga do Python e alguns padrões que costumam esconder bugs. Deixei o notebook de exploração fora do Ruff, porque ele já foi revisado e reformatá-lo agora só mudaria a apresentação, sem ganho para a análise.

Os testes cobrem apenas o que não chama a AWS, e por isso o CI não precisa de nenhuma credencial. O primeiro teste confere que o download da base pula os arquivos que já estão na pasta, usando uma versão falsa da API do Kaggle, sem acesso à rede.

## Acesso à AWS e região

O GitHub Actions entra na AWS por OIDC, sem nenhuma chave guardada no repositório. Como o repositório é público, o papel assumido pelos workflows aceita apenas este repositório e as branches do projeto, e a permissão de IAM vale só para recursos com o prefixo `olist-voc-`. O bootstrap, que cria esse acesso, é a única parte da infraestrutura que roda pelo terminal. Todo o resto é aplicado pelos workflows.

Antes de escrever a indexação, testei os limites do Bedrock nesta conta. O Titan Text Embeddings V2, que era o modelo de embeddings previsto, aceita só 60 chamadas por minuto, com um texto por chamada. Com cerca de 40.500 documentos, a indexação levaria umas 11 horas, mais que as 6 horas que um job do GitHub Actions pode durar. A AWS não aceita pedido de aumento desse limite, e o valor é o mesmo em `us-west-2`. Por isso troquei o modelo pelo Cohere Embed Multilingual v3, também no Bedrock. O limite dele é de 20 chamadas por minuto, mas cada chamada leva até 96 textos, e a indexação cai para cerca de 25 minutos. O modelo é multilíngue, gera vetores de 1024 dimensões e trata de forma diferente o texto que vai para o índice e o texto da pergunta. O preço por token é maior que o do Titan, mas a indexação inteira continua custando poucos centavos.

Mantive tudo em `us-east-1`. Os preços dos serviços usados são os mesmos de `us-west-2`, e em `us-east-1` o Nova Micro pode ser chamado direto, com limite de 100 chamadas por minuto, sem passar por um perfil de inferência que distribui as chamadas entre regiões.

## Preparação da base

Cada avaliação com mensagem escrita vira um documento, identificado pelo `review_id`. O texto do documento junta o título e a mensagem, com um ponto entre os dois quando o título não termina em pontuação. A limpeza é mínima: tiro quebras de linha, espaços repetidos e caracteres invisíveis, e mantenho acentos, maiúsculas e todas as palavras, porque o modelo de embeddings entende a frase natural e remover um "não" inverteria o sentido da reclamação.

Os emojis são trocados por palavras apenas no texto que vira embedding, para que o modelo receba o sentido e o gestor continue vendo o comentário como o cliente escreveu. Montei a tabela a partir da contagem real na base. O mais frequente é o 👏, com 227 ocorrências, seguido de 👍, 😍, 😉 e 😆. Emojis que podem indicar tanto elogio quanto crítica, como 😂 e 🤔, ficam como estão. Os modificadores de tom de pele saem do texto do embedding, porque só mudam a cor do emoji anterior. Depois da conversão, descarto os documentos que continuam sem nenhuma letra, como "..." ou "10".

Os metadados nunca ficam vazios, porque um valor nulo quebraria os filtros da busca. A categoria vem dos produtos de todos os pedidos ligados à avaliação: uma só vira a categoria do documento, mais de uma vira `mista` e nenhuma vira `desconhecido`. A entrega tem quatro valores. `nao_entregue` são os pedidos sem data de entrega ao cliente, `no_prazo` e `atrasada` vêm da comparação com a data estimada, e `desconhecido` cobre avaliações sem pedido correspondente ou ligadas a pedidos em situações diferentes.

A preparação rodada no GitHub Actions, com a base baixada do Kaggle, chegou a 40.521 documentos: 34.399 entregues no prazo, 4.214 atrasados, 1.819 não entregues e 89 com entrega desconhecida. São 73 categorias, 528 documentos de categoria mista e 1.065 sem categoria. O notebook de exploração tinha chegado a 40.482 documentos. A diferença de 39 vem de duas regras aplicadas aqui e não lá: 21 comentários formados só por emojis ou carinhas, como "👍👍👍" e ":)", voltam para a base depois da conversão, e 18 têm uma mensagem sem letras, mas um título com conteúdo, como "Ótimo".

## Indexação

Cada documento vira um vetor de 1024 números pelo Cohere Embed Multilingual v3, no modo `search_document`. A pergunta do gestor usa o mesmo modelo no modo `search_query`, que o Cohere trata de forma diferente porque uma pergunta e um comentário que a responde são escritos de jeitos diferentes.

Os textos vão ao modelo em lotes de 96, com dois lotes ao mesmo tempo, e cada lote é gravado assim que volta. Com o limite de 20 chamadas por minuto da conta, a AWS recusa parte das chamadas, e o código espera e tenta de novo, com a espera dobrando até um teto de 60 segundos. Na primeira execução eu tinha deixado só seis tentativas, com 62 segundos de espera no total. Um lote esgotou as seis e a indexação parou em 6.720 documentos. Como cada lote já estava gravado e o workflow guardou o progresso parcial no S3, a segunda execução, com dez tentativas, recuperou esses documentos e gerou os outros 33.801 em 17 minutos. Se um lote falhar de vez, os lotes que ainda estão na fila são cancelados, para não gastar chamadas cujo resultado não seria gravado.

Os embeddings ficam num arquivo Parquet, `embeddings.parquet`, com uma linha por avaliação: o `review_id`, o vetor, o texto e os metadados. Durante a geração, cada lote vira uma parte do arquivo, e são essas partes que permitem retomar uma execução interrompida. No fim, as partes são juntadas num arquivo só, de 87 MB, guardado em `index/current/` no bucket do índice. A primeira versão gravava os vetores direto no Chroma; quando o banco vetorial mudou para o PostgreSQL, converti os vetores já gerados para Parquet uma única vez, sem chamar o Cohere de novo.

Ao lado do arquivo fica um manifesto com o modelo, as dimensões, a distância, a data, o número de documentos e a lista das 73 categorias. Os embeddings são gerados num lugar e buscados em outro, e vetores feitos com outro modelo ou outro tamanho dariam resultados sem sentido. Por isso a API confere o manifesto ao iniciar e não sobe se algo divergir. A lista de categorias também alimenta o filtro da página.

## Banco vetorial

Comparei o Chroma rodando dentro da API com outras bibliotecas do mesmo tipo (FAISS, LanceDB e Qdrant em modo local) e com os serviços gerenciados da AWS (S3 Vectors, RDS PostgreSQL com pgvector, OpenSearch e Bedrock Knowledge Bases). Para 40.521 comentários, as bibliotecas resolveriam a busca sem custo, mas o índice ocuparia a memória da API e viajaria dentro da imagem a cada publicação. O OpenSearch Serverless custaria cerca de US$ 350 por mês, e o Bedrock Knowledge Bases faria a recuperação no lugar do meu código, tirando o controle do score mínimo e do MMR, que são parte do que quero demonstrar.

Escolhi o Amazon RDS PostgreSQL com a extensão pgvector. É a opção mais difundida para busca vetorial num banco relacional, os filtros por nota, categoria e entrega viram SQL comum, e a mesma consulta devolve a distância e o vetor de cada candidato, de que o MMR precisa. O banco é uma instância `db.t4g.micro`, com 1 GB de memória e 20 GB de disco, sem endereço público e acessível só pelas tarefas do projeto. Ele liga às 8h40 e desliga às 22h, um pouco antes e depois da API, e custa cerca de US$ 0,29 por dia, US$ 0,21 da instância e US$ 0,08 do disco. A busca usa um índice HNSW com distância de cosseno. Na primeira carga, o banco recusou a área de memória compartilhada que a construção do índice em paralelo pede. Sem paralelismo e com 128 MB, o índice não cabe na memória e o pgvector o constrói em disco, em 17 minutos. Cheguei a preparar a troca para a `db.t4g.small`, de 2 GB, mas a carga só roda de novo quando os embeddings mudam, e 17 minutos não justificavam pagar quase o dobro. A calibração mudou essa conta: na micro, cada busca levou 1,3 segundo na mediana e até 3 segundos, porque o índice não cabe na memória e o banco o lê do disco a cada pergunta. Troquei para a `db.t4g.small`, que custa cerca de US$ 0,51 por dia no horário de funcionamento.

## Publicação na AWS

A página e a API ficam no mesmo endereço do CloudFront. O caminho `/` vai para um bucket privado do S3, lido só pelo CloudFront, e `/api/*` vai para um Application Load Balancer na frente de uma tarefa do ECS no Fargate, com 0,5 vCPU e 1 GB. Com um endereço só, a página chama a API sem CORS e sem domínio próprio. As chamadas à API não passam pelo cache e chegam ao ALB com os cabeçalhos e o corpo das requisições. O ALB aceita apenas a lista de endereços do CloudFront, e a tarefa aceita apenas o ALB. Sem domínio próprio, o ALB não tem certificado, então o trecho entre o CloudFront e o ALB é HTTP. Registro isso como limite conhecido.

A rede tem duas sub-redes públicas e nenhum NAT Gateway, que sozinho custaria mais do que o resto da aplicação. O banco fica nessas sub-redes sem endereço público e aceita conexões apenas das tarefas do ECS. A chave de acesso da página e a senha do banco são geradas pelo Terraform, guardadas no Parameter Store e injetadas pelo ECS na tarefa.

A publicação troca a imagem da tarefa e, a partir da etapa de horário, o agendamento troca o número de tarefas. Sem `ignore_changes` nesses dois campos, a próxima execução do Terraform desfaria as duas mudanças. O serviço nasce com zero tarefas: a API só consegue subir depois que os vetores estão no banco, e por isso quem a liga pela primeira vez é o workflow de carga.

A carga dos vetores roda numa tarefa avulsa do ECS, com a mesma imagem da API e só o comando trocado. O GitHub Actions não alcança o banco, que fica numa rede privada; a tarefa avulsa roda dentro dessa rede, lê o Parquet do S3 e grava as linhas numa transação, de modo que uma carga que falhe no meio não apaga a anterior. O índice HNSW é criado depois da carga, o que deixa a inserção bem mais rápida. Com os vetores no banco, a API não carrega o índice: no primeiro dia no ar, a tarefa usou no máximo 82 MB, 8% do 1 GB reservado.

Os testes do banco precisam de um PostgreSQL com pgvector. O CI sobe um banco desses só para os testes, e no meu computador esses testes são pulados. O CI também constrói a imagem da API a cada PR, para que um erro no Dockerfile apareça antes da publicação.

## Calibração da busca

Para escolher o score mínimo, o número de comentários e o uso da reescrita, rodei as perguntas 1 a 11 da avaliação e busquei, para cada uma, os 30 comentários mais próximos, sem corte e sem MMR, com a pergunta original e com o tema reescrito pelo Nova Micro. As duas tabelas estão em `evaluation/calibration/`: a completa, com os 30 comentários de cada busca, e o resumo, com o score em algumas posições.

A reescrita aumentou a similaridade em oito das nove perguntas que passam pela busca e trouxe comentários mais específicos. Na pergunta 1, por exemplo, a busca pela pergunta original trouxe frases genéricas como "Nunca tive problemas em receber encomendas", e a busca por "reclamações sobre entrega" trouxe entregas incompletas, demoras e produtos divergentes. A exceção foi a pergunta dos elogios, em que o tema "elogios dos clientes" puxou frases curtas como "Cliente satisfeito". Na pergunta do Pix, a reescrita baixou o score, o que é o comportamento desejado, porque não existe nenhum comentário sobre Pix. A busca usa o tema reescrito.

O score mínimo ficou em 0,58. Na pergunta do Pix, os comentários mais próximos falam de pagamento em geral, como "Você compra, paga e recebe dentro do prazo", e o maior score com o tema reescrito foi 0,572. Nas perguntas com evidência, o 15º comentário ficou entre 0,62 e 0,73. O corte em 0,58 deixa a pergunta do Pix sem nenhum comentário e mantém pelo menos 15 nas outras. A folga em relação ao Pix é pequena, de 0,008, e por isso a instrução no prompt da resposta, que manda dizer quando os comentários não respondem à pergunta, continua sendo a segunda proteção.

Depois do corte, o MMR escolhe 15 comentários. Na busca sem MMR, as posições 10 a 15 da pergunta sobre defeitos são quase todas a mesma frase ("produto com defeito", "Produto com defeito!"), e é justamente isso que o MMR troca por comentários diferentes. Quinze comentários curtos somam menos de mil tokens, então o contexto maior quase não custa nada.

Os comentários de até 10 caracteres ficaram na base. Nenhum deles apareceu entre os 15 primeiros em nenhuma das perguntas.

A pergunta 5, sobre cartões de memória falsificados, deveria testar a evidência fraca, mas a busca trouxe uns seis comentários sobre cartões falsos ou com defeito entre os dez primeiros, ao lado de outros sobre produtos falsificados em geral. A evidência fraca é medida pelas citações que a resposta usa, e vou conferir na etapa de geração se essa pergunta fica com uma ou duas citações. Se ficar com mais, troco o tema por um mais raro.
