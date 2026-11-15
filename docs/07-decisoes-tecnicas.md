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
